"""Coupled 1D/2D urban flood simulation (SRS Modules E-I).

Per surface step (operator splitting, every transfer mass-exact):
  1. runoff engine: rain -> interception -> infiltration -> depression -> effective rain
  2. exchange: surface -> inlet capture (weir/orifice), removed from the surface cells
  3. 1D drainage: local-inertial pipe routing, pumps, outfall boundaries (sub-stepped)
  4. surcharge overflow volumes returned onto the node cells
  5. 2D surface: diffusive-wave storage-cell routing of effective rain over the DEM

`components` switches parts off for the SRS baseline experiments (B2-B5).
The model runs on the bounding box of the domain for speed; outputs are full-grid.
"""
from __future__ import annotations

import numpy as np

from simulation import config as C
from ..rainfall.generator import generate as gen_rain
from ..surface.infiltration import RunoffModel
from ..surface.runoff import step_surface
from .boundary import for_outfalls
from .exchange import capture
from .network1d import Drainage1D

DEFAULT_COMPONENTS = {"infiltration": True, "drainage": True, "surface_routing": True}


def apply_blockage(nE, edges, nodes, level, mode, rng):
    b = np.zeros(nE)
    if level and level > 0:
        if mode == "pipe_uniform":
            b[:] = level
        elif mode == "inlet_subset":
            idx = rng.choice(nE, size=max(1, int(nE * min(level + 0.15, 1.0))), replace=False)
            b[idx] = min(0.95, level + 0.2)
        else:  # outfall_restricted
            for e, ed in enumerate(edges):
                b[e] = min(0.95, level + 0.25) if nodes[ed["v"]]["kind"] == "outfall" else level * 0.4
    for e, ed in enumerate(edges):  # pumps are not blocked by debris
        if ed.get("kind") == "pump":
            b[e] = 0.0
    return b


def _bbox(mask, pad=2):
    ii, jj = np.where(mask)
    return (slice(max(ii.min() - pad, 0), ii.max() + pad + 1),
            slice(max(jj.min() - pad, 0), jj.max() + pad + 1))


def simulate(twin, network, spec, hydro_cfg, rain_cfg, out_every=1,
             dem=None, manning=None, imperv_open=None,
             inlet_cap_scale=1.0, dep_scale=1.0, components=None, drainage_cfg=None):
    """Run one scenario. Optional overrides (dataset v1.0 uncertainty, recorded in spec):
    dem / manning grids, inlet_cap_scale, dep_scale. `imperv_open` is metadata only.
    spec keys: seed, temporal, spatial, duration_h, total_mm, blockage_level, blockage_mode,
    optional recession_h, boundary {type,...}, pump_status {edge_id: auto|on|off|failed}.
    """
    comp = dict(DEFAULT_COMPONENTS, **(components or {}))
    dcfg = drainage_cfg or C.load("drainage")
    exch_cfg = dict(hydro_cfg.get("exchange", {}))
    exch_cfg.setdefault("weir_coeff", hydro_cfg.get("pipes", {}).get("inlet_weir_c", 1.7))
    rng = np.random.default_rng(int(spec["seed"]) + 999)

    # ---- rainfall (mm per output step), normalised so spec total = mean over wet cells
    rain = gen_rain(spec, twin.X, twin.Y, rain_cfg)
    R = rain["rain_mm_per_step"]
    wet_full = twin.in_domain & ~twin.is_building
    wetmean = float(R.mean(axis=(1, 2), where=np.broadcast_to(wet_full, R.shape)).mean())
    R = R / max(wetmean * R.shape[0], 1e-9) * float(spec["total_mm"])
    nt = rain["nt"]
    dt = float(rain_cfg.get("timestep_min", 5)) * 60.0
    n_rec = int(round(float(spec.get("recession_h", 0.0) or 0.0) * 3600.0 / dt))
    R_ext = np.concatenate([R, np.zeros((n_rec,) + R.shape[1:], R.dtype)]) if n_rec else R
    nt_out = nt + n_rec

    # ---- crop to the domain bounding box
    bi, bj = _bbox(wet_full)
    oi, oj = bi.start, bj.start
    dem_use = (twin.dem if dem is None else dem)[bi, bj]
    man_use = (twin.manning if manning is None else manning)[bi, bj]
    wet = wet_full[bi, bj]
    blocked = ~wet
    cls = twin.cell_class[bi, bj]
    dx = twin.dx
    cell_area = dx * dx

    # ---- engines
    runoff = RunoffModel(hydro_cfg, cls, wet, dep_scale=dep_scale, infiltration=comp["infiltration"])
    nodes = [dict(n, i=n["i"] - oi, j=n["j"] - oj) for n in network["nodes"]]
    net_local = dict(network, nodes=nodes)
    blk = apply_blockage(len(network["edges"]), network["edges"], network["nodes"],
                         spec.get("blockage_level", 0.0), spec.get("blockage_mode", "pipe_uniform"), rng)
    bnds = for_outfalls(network, dcfg.get("boundaries"), spec.get("boundary"))
    dr = Drainage1D(net_local, bnds, blockage=blk, pump_status=spec.get("pump_status"),
                    inlet_cap_scale=inlet_cap_scale)

    sdt = float(hydro_cfg["surface"].get("dt_fixed_s", 2.0))
    sub = max(1, int(round(dt / sdt)))
    sdt = dt / sub
    hthr = float(hydro_cfg["surface"].get("h_flood_m", 0.05))
    h = np.zeros_like(dem_use)
    vel = np.zeros_like(dem_use)
    maxd = np.zeros_like(dem_use)
    ttf = np.full_like(dem_use, np.nan)
    vol = {"rain": 0.0, "capture": 0.0, "overflow": 0.0, "clip": 0.0}
    H, V, ND, NH, PF, EX, OV = [], [], [], [], [], [], []
    ex_acc = np.zeros(dr.nN)
    ov_acc = np.zeros(dr.nN)
    zeros = np.zeros_like(h)

    for k in range(nt_out):
        rmmh = np.where(wet, R_ext[k][bi, bj], 0.0) * 3600.0 / dt
        for _ in range(sub):
            vol["rain"] += float(rmmh.sum()) * sdt / 3.6e6 * cell_area
            eff, f_pond = runoff.step(sdt, rmmh, h)
            h = h - f_pond
            if comp["drainage"]:
                q_in = capture(dr, h, dx, sdt, exch_cfg)
                for kk in np.nonzero(q_in)[0]:
                    i, j = dr.cell[kk]
                    h[i, j] -= q_in[kk] * sdt / cell_area
                vol["capture"] += float(q_in.sum()) * sdt
                ex_acc += q_in * sdt
                over = dr.advance(sdt, q_in)
                for kk in np.nonzero(over)[0]:
                    i, j = dr.cell[kk]
                    h[i, j] += over[kk] / cell_area
                vol["overflow"] += float(over.sum())
                ov_acc += over
            if comp["surface_routing"]:
                h_before = h.sum()
                h2, vel, _ = step_surface(h, dem_use, man_use, eff, zeros, zeros, dx, sdt, blocked=blocked)
                vol["clip"] += float((h2.sum() - h_before) - (eff * wet).sum() * sdt / 3.6e6) * cell_area
                h = h2
            else:
                h = h + eff * sdt / 3.6e6
            h[blocked] = 0.0
            if not np.all(np.isfinite(h)):
                raise FloatingPointError("NaN/Inf in surface depth")
        maxd = np.maximum(maxd, h)
        ttf[np.isnan(ttf) & (h >= hthr)] = (k + 1) * dt / 60.0
        if k % out_every == 0:
            H.append(h.astype(np.float32)); V.append(vel.astype(np.float32))
            ND.append(dr.depth().astype(np.float32)); NH.append(dr.head().astype(np.float32))
            PF.append(dr.Q.astype(np.float32))
            EX.append((ex_acc / dt).astype(np.float32)); OV.append(ov_acc.astype(np.float32))
            ex_acc = np.zeros(dr.nN); ov_acc = np.zeros(dr.nN)

    # ---- back to the full grid
    def full(a, fill=0.0):
        out = np.full(a.shape[:-2] + twin.dem.shape, fill, dtype=a.dtype)
        out[..., bi, bj] = a
        return out

    depth = full(np.stack(H))
    wet_cells = max(int(wet.sum()), 1)
    to_mm = lambda m3: m3 / (wet_cells * cell_area) * 1000.0
    stores = {
        "surface": float(h[wet].sum()) * cell_area,
        "depression": float(runoff.dep.sum()) / 1000.0 * cell_area,
        "interception": float(runoff.interc.sum()) / 1000.0 * cell_area,
        "infiltration": float(runoff.infil_total_mm.sum()) / 1000.0 * cell_area,
        "nodes": dr.node_volume_total(),
    }
    inflow = vol["rain"] + dr.boundary_in_m3
    outflow = stores["infiltration"] + dr.discharged_m3
    stored = stores["surface"] + stores["depression"] + stores["interception"] + stores["nodes"]
    mass_err = (inflow - outflow - stored) / max(inflow, 1e-9)
    return {
        "rain": R_ext.astype(np.float32), "depth": depth, "velocity": full(np.stack(V)),
        "flooded": depth >= hthr,
        "node_depth": np.stack(ND), "node_head": np.stack(NH), "pipe_flow": np.stack(PF),
        "node_capture_m3s": np.stack(EX), "node_overflow_m3": np.stack(OV),
        "pipe_capacity": np.array([e["capacity_m3s"] for e in network["edges"]], np.float32),
        "surcharge": dr.surcharge.copy(), "surcharge_time_s": dr.surcharge_time_s.copy(),
        "overflow": dr.overflow_total.copy(),
        "time_to_flood_min": full(ttf.astype(np.float32), np.nan),
        "max_depth": full(maxd.astype(np.float32)), "blockage": blk, "rain_spec": spec,
        "boundaries": {str(k): b.describe() for k, b in bnds.items()},
        "components": comp,
        "mass": {
            "rain_mm": to_mm(vol["rain"]), "boundary_in_mm": to_mm(dr.boundary_in_m3),
            "infil_mm": to_mm(stores["infiltration"]), "interception_mm": to_mm(stores["interception"]),
            "depression_mm": to_mm(stores["depression"]), "ponded_mm": to_mm(stores["surface"]),
            "node_stored_mm": to_mm(stores["nodes"]), "discharged_mm": to_mm(dr.discharged_m3),
            "drain_mm": to_mm(vol["capture"] - vol["overflow"]),
            "capture_mm": to_mm(vol["capture"]), "overflow_mm": to_mm(vol["overflow"]),
            "maxd_mm": float(maxd.max() * 1000.0),
            "rel_error": float(mass_err), "surface_clip_m3": vol["clip"],
            "limiter_clip_m3": dr.limiter_clip_m3,
        },
    }
