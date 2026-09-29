"""1D pipe/node hydraulics: Manning capacity, inlet capture, surcharge, blockage."""
import numpy as np

class DrainageState:
    def __init__(self, network, cfg, blockage=None):
        self.net = network
        self.nodes = network["nodes"]; self.edges = network["edges"]
        self.nN = len(self.nodes); self.nE = len(self.edges)
        self.inlet_cap = np.full(self.nN, float(cfg["nodes"]["inlet_capacity_m3s"]))
        r = cfg.get("uncertainty", {}).get("inlet_capacity_range_m3s", [0.02, 0.10])
        # per-node variation already encoded via blockage; keep base
        self.node_depth = np.zeros(self.nN)     # m above invert
        self.node_maxdepth = np.full(self.nN, float(cfg["nodes"]["depth_m"]))
        self.pipe_flow = np.zeros(self.nE)
        self.cap = np.array([e["capacity_m3s"] for e in self.edges])
        self.blockage = np.zeros(self.nE) if blockage is None else np.array(blockage, float)
        self.surcharge = np.zeros(self.nN, bool)
        self.overflow = np.zeros(self.nN)
        self.discharged_m3 = 0.0
        # node->cell map
        # node->cell map
        self.node_cell = [(n["i"], n["j"]) for n in self.nodes]
        self.is_outfall = np.array([n["kind"] == "outfall" for n in self.nodes])

    def step(self, dt_s, ponded, dx):
        """ponded: surface depth (m) grid.
        Returns (sink_ms, return_ms): sink removes water surface->pipes (m/s);
        return_ms puts surcharge overflow back onto the surface (m/s)."""
        eff_cap = self.cap * (1.0 - np.clip(self.blockage, 0, 0.99))
        # blockage also chokes the node's own inlet (debris over grate / barrel entrance)
        out_blk = np.zeros(self.nN)
        for e, ed in enumerate(self.net["edges"]):
            if self.blockage[e] > out_blk[ed["u"]]:
                out_blk[ed["u"]] = self.blockage[e]
        eff_inlet = self.inlet_cap * (1.0 - 0.8 * np.clip(out_blk, 0, 0.99))
        # inlet capture: limited by inlet_cap and ponded availability
        capture = np.zeros(self.nN)
        for k, (i, j) in enumerate(self.node_cell):
            if self.is_outfall[k]:
                continue
            avail = ponded[i, j] * dx * dx / max(dt_s, 1e-9)
            take = min(eff_inlet[k], avail)
            # head-limited: surcharged node takes less
            if self.surcharge[k]:
                take *= 0.3
            capture[k] = take
        # route downstream: topological-ish single pass (edges point downhill by construction)
        inflow = capture.copy()
        self.pipe_flow[:] = 0.0
        for e in range(self.nE):
            u = self.edges[e]["u"]; v = self.edges[e]["v"]
            q = min(inflow[u], eff_cap[e])
            # upstream keeps remainder as ponding pressure -> node depth rises
            self.pipe_flow[e] = q
            inflow[v] += q
            inflow[u] -= q
        # node depths: residual positive inflow accumulates
        self.node_depth = np.clip(self.node_depth + (inflow - np.where(self.is_outfall, inflow, 0)) * dt_s / 1.0, 0, None)
        self.discharged_m3 += float(inflow[self.is_outfall].sum()) * dt_s
        rim_head = self.node_depth - self.node_maxdepth
        self.surcharge = rim_head > 0
        self.overflow = np.where(self.surcharge, rim_head, 0.0)  # m of excess head
        # cap stored head at rim + return the excess to the surface this step
        ret = np.zeros_like(ponded)
        for k, (i, j) in enumerate(self.node_cell):
            if self.surcharge[k] and not self.is_outfall[k]:
                q_back = self.overflow[k] * 1.0 / max(dt_s, 1e-9)  # m3/s
                ret[i, j] += q_back / (dx * dx)  # m/s
                self.node_depth[k] = self.node_maxdepth[k]
        # drain sink grid
        sink = np.zeros_like(ponded)
        for k, (i, j) in enumerate(self.node_cell):
            sink[i, j] += capture[k] / (dx * dx)  # m/s
        return sink, ret
