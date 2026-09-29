"""1D drainage hydraulics (SRS Module G): local-inertial dynamic routing on a pipe graph.

State: node volume V (m3) and link discharge Q (m3/s, + = u -> v).
Link momentum (Bates et al. 2010 local-inertial form, as used for 1D conduits):

    Q' = (Q - g A dt dH/L) / (1 + g dt n^2 |Q| / (A R^(4/3)))

with A, R from circular-section geometry at the flow depth (full bore when pressurised).
Because flow is driven by the head difference it naturally gives backwater, reverse flow
and pressurised (surcharged) flow. Node continuity:

    dV/dt = sum(Q_in) - sum(Q_out) + lateral inflow

Node storage = manhole plan area + half of every connected pipe's plan area (the SWMM
"surface area" approach), so pipe volume is accounted for. A node whose volume exceeds its
full volume (rim) SURCHARGES: the excess leaves the node and is returned to the surface
(`overflow_m3`, mass-exact). Outfalls are boundary nodes whose level comes from
`boundary.Boundary`; pumps are links with on/off depth control.
"""
from __future__ import annotations

import numpy as np

G = 9.81


def circ_geom(y, D):
    """Flow area and hydraulic radius of a circular pipe at depth y (vectorised)."""
    y = np.clip(y, 0.0, D)
    full = y >= D * 0.999
    theta = 2.0 * np.arccos(np.clip(1.0 - 2.0 * y / np.maximum(D, 1e-9), -1.0, 1.0))
    A = D ** 2 / 8.0 * (theta - np.sin(theta))
    P = D * theta / 2.0
    A = np.where(full, np.pi * D ** 2 / 4.0, A)
    P = np.where(full, np.pi * D, P)
    R = np.where(P > 1e-9, A / np.maximum(P, 1e-9), 0.0)
    return A, R


class Drainage1D:
    def __init__(self, net, boundaries, blockage=None, pump_status=None, inlet_cap_scale=1.0):
        self.net = net
        nodes, edges = net["nodes"], net["edges"]
        self.nN, self.nE = len(nodes), len(edges)
        self.kind = np.array([n["kind"] for n in nodes])
        self.is_outfall = self.kind == "outfall"
        self.invert = np.array([n["invert_m"] for n in nodes], float)
        self.rim = np.array([n["rim_m"] for n in nodes], float)
        self.cell = [(n["i"], n["j"]) for n in nodes]
        self.u = np.array([e["u"] for e in edges], int)
        self.v = np.array([e["v"] for e in edges], int)
        self.L = np.array([e["length_m"] for e in edges], float)
        self.D = np.array([e["diameter_m"] for e in edges], float)
        self.n = np.array([e["n"] for e in edges], float)
        self.cap = np.array([e["capacity_m3s"] for e in edges], float)
        self.is_pump = np.array([e.get("kind") == "pump" for e in edges])
        # link invert at each end = node invert (no offsets in the synthetic network)
        self.zu, self.zv = self.invert[self.u], self.invert[self.v]
        # node plan area: manhole + half of each connected pipe's plan area
        area = np.array([n["area_m2"] for n in nodes], float)
        pipe_half = 0.5 * self.L * self.D * ~self.is_pump
        np.add.at(area, self.u, pipe_half)
        np.add.at(area, self.v, pipe_half)
        self.area = np.where(self.kind == "storage", [n["area_m2"] for n in nodes], area)
        self.full_depth = np.maximum(self.rim - self.invert, 0.1)
        self.V_full = self.area * self.full_depth
        self.V = np.zeros(self.nN)
        self.Q = np.zeros(self.nE)
        self.blockage = np.zeros(self.nE) if blockage is None else np.clip(np.asarray(blockage, float), 0, 0.99)
        self.boundaries = boundaries
        # inlet capacity (surface -> pipe), reduced by blockage of the node's outgoing link
        self.node_blockage = np.zeros(self.nN)
        np.maximum.at(self.node_blockage, self.u, self.blockage)
        self.inlet_cap = np.array([n.get("inlet_capacity_m3s", 0.0) for n in nodes], float) * float(inlet_cap_scale)
        # pumps
        self.pump_cfg = [e.get("pump") for e in edges]
        self.pump_on = np.zeros(self.nE, bool)
        self.pump_status = dict(pump_status or {})   # edge id -> "auto" | "on" | "off" | "failed"
        # accumulators
        self.t = 0.0
        self.discharged_m3 = 0.0
        self.boundary_in_m3 = 0.0
        self.overflow_step = np.zeros(self.nN)   # m3 overflowed during the last advance()
        self.overflow_total = np.zeros(self.nN)
        self.surcharge = np.zeros(self.nN, bool)
        self.surcharge_time_s = np.zeros(self.nN)
        self.limiter_clip_m3 = 0.0
        # stable internal step (gravity-wave CFL on the shortest pipe)
        pipes = ~self.is_pump
        c = np.sqrt(G * self.D[pipes]) if pipes.any() else np.array([1.0])
        self.dt_max = float(np.clip(0.5 * (self.L[pipes] / c).min() if pipes.any() else 1.0, 0.2, 5.0))

    # ---- state helpers
    def depth(self):
        return np.where(self.is_outfall, 0.0, self.V / self.area)

    def head(self):
        h = self.invert + self.depth()
        for k, b in self.boundaries.items():
            h[k] = b.level(self.t, self.invert[k])
        return h

    def node_volume_total(self):
        return float(self.V[~self.is_outfall].sum())

    # ---- one internal step
    def _step(self, dt, lateral):
        H = self.head()
        Hu, Hv = H[self.u], H[self.v]
        y = np.maximum(Hu, Hv) - np.maximum(self.zu, self.zv)
        A, R = circ_geom(np.maximum(y, 0.0), self.D)
        A = A * (1.0 - self.blockage)
        wet = (A > 1e-6) & ~self.is_pump
        Q = np.zeros(self.nE)
        num = self.Q - G * A * dt * (Hv - Hu) / self.L
        den = 1.0 + G * dt * self.n ** 2 * np.abs(self.Q) / np.maximum(A * np.maximum(R, 1e-6) ** (4.0 / 3.0), 1e-9)
        Q[wet] = (num / den)[wet]
        # pumps: on/off hysteresis on the wet-well (upstream node) depth
        d = self.depth()
        for e in np.where(self.is_pump)[0]:
            pc = self.pump_cfg[e]
            st = self.pump_status.get(e, self.pump_status.get(str(e), pc.get("status", "auto")))
            du = d[self.u[e]]
            if st == "auto":
                if du >= pc["on_depth_m"]:
                    self.pump_on[e] = True
                elif du <= pc["off_depth_m"]:
                    self.pump_on[e] = False
            else:
                self.pump_on[e] = st == "on"
            Q[e] = pc["capacity_m3s"] if self.pump_on[e] else 0.0
        # volume limiter: no node may export more than it holds (+ lateral this step)
        avail = np.maximum(self.V + np.maximum(lateral, 0.0) * dt, 0.0)
        out = np.zeros(self.nN)
        np.add.at(out, self.u, np.maximum(Q, 0.0) * dt)
        np.add.at(out, self.v, np.maximum(-Q, 0.0) * dt)
        scale = np.where(self.is_outfall | (out <= avail), 1.0, avail / np.maximum(out, 1e-12))
        Q = np.where(Q > 0, Q * scale[self.u], Q * scale[self.v])
        self.Q = Q
        # continuity
        net_in = lateral.copy()
        np.add.at(net_in, self.v, Q)
        np.add.at(net_in, self.u, -Q)
        dV = net_in * dt
        self.discharged_m3 += float(np.maximum(dV[self.is_outfall], 0).sum())
        self.boundary_in_m3 += float(np.maximum(-dV[self.is_outfall], 0).sum())
        self.V = np.where(self.is_outfall, 0.0, self.V + dV)
        neg = np.minimum(self.V, 0.0)
        self.limiter_clip_m3 += float(-neg.sum())
        self.V = np.maximum(self.V, 0.0)
        # surcharge: volume above rim leaves the node onto the surface
        excess = np.where(self.is_outfall, 0.0, np.maximum(self.V - self.V_full, 0.0))
        self.V -= excess
        self.overflow_step += excess
        self.surcharge = (self.V >= self.V_full * 0.999) & ~self.is_outfall
        self.surcharge_time_s += self.surcharge * dt
        self.t += dt

    def advance(self, dt, lateral_m3s):
        """Advance by dt seconds with a constant lateral inflow (m3/s per node, from the
        surface exchange). Returns overflow volume per node (m3) produced during dt."""
        self.overflow_step = np.zeros(self.nN)
        nsub = max(1, int(np.ceil(dt / self.dt_max)))
        for _ in range(nsub):
            self._step(dt / nsub, lateral_m3s)
        self.overflow_total += self.overflow_step
        return self.overflow_step

    def free_capacity_m3(self):
        return np.where(self.is_outfall, np.inf, np.maximum(self.V_full - self.V, 0.0))
