"""Coupled surface + drainage simulation loop (clean version)."""
import numpy as np, yaml
from ..surface.runoff import step_surface
from ..hydraulics.pipes import DrainageState
from ..rainfall.generator import generate as gen_rain

def apply_blockage(dst, level, mode, rng):
    b = np.zeros(dst.nE)
    if level and level > 0:
        if mode == "pipe_uniform":
            b[:] = level
        elif mode == "inlet_subset":
            idx = rng.choice(dst.nE, size=max(1, int(dst.nE * min(level + 0.15, 1.0))), replace=False)
            b[idx] = min(0.95, level + 0.2)
        else:
            for e, ed in enumerate(dst.net["edges"]):
                v = dst.net["nodes"][ed["v"]]
                b[e] = min(0.95, level + 0.25) if v["kind"] == "outfall" else level * 0.4
    return b

def simulate(twin, network, spec, hydro_cfg, rain_cfg, out_every=1,
             dem=None, manning=None, imperv_open=None,
             inlet_cap_scale=1.0, dep_scale=1.0):
    """Coupled surface + drainage loop.

    Optional per-scenario overrides (dataset v1.0 uncertainty, all recorded in
    spec; physics untouched):
      dem: elevation grid override (base twin.dem + stored delta)
      manning: roughness grid override
      imperv_open: open-space impervious fraction (metadata; infiltration class map rebuilt)
      inlet_cap_scale: multiplier on node inlet capacity (drainage efficiency)
      dep_scale: multiplier on depression storage
    Recession: spec may carry recession_h (dry tail, no rain) so drain-down
    dynamics are captured. nt_out covers rain + recession steps.
    """
    rng = np.random.default_rng(int(spec["seed"]) + 999)
    rain = gen_rain(spec, twin.X, twin.Y, rain_cfg)
    R = rain["rain_mm_per_step"]
    wet = twin.in_domain & (~twin.is_building)
    # rescale so the SPEC total (mm) is the mean over wet cells (rooftops excluded)
    wetmean = float(R.mean(axis=(1, 2), where=np.broadcast_to(wet, R.shape)).mean()) if wet.any() else 1.0
    R = R / max(wetmean * R.shape[0], 1e-9) * float(spec["total_mm"])
    nt = rain["nt"]
    dt = float(rain_cfg.get("timestep_min", 5)) * 60.0
    # optional dry recession tail (zeros appended AFTER normalisation so totals stay exact)
    rec_h = float(spec.get("recession_h", 0.0) or 0.0)
    n_rec = int(round(rec_h * 3600.0 / dt))
    dem_use = twin.dem if dem is None else dem
    man_use = twin.manning if manning is None else manning
    if imperv_open is not None:
        pass  # recorded in spec for ML inputs; class map below uses twin masks
    sdt = float(hydro_cfg["surface"].get("dt_fixed_s", 2.0))
    sub = max(1, int(round(dt / sdt))); sdt = dt / sub
    dcfg = yaml.safe_load(open("config/drainage.yaml"))
    dcfg["nodes"]["inlet_capacity_m3s"] = float(dcfg["nodes"]["inlet_capacity_m3s"]) * float(inlet_cap_scale)
    dst = DrainageState(network, dcfg, None)
    dst.blockage = apply_blockage(dst, spec.get("blockage_level", 0.0),
                                  spec.get("blockage_mode", "pipe_uniform"), rng)
    cls = np.where(twin.is_road, 0, np.where(twin.is_open, 1, 2))
    hz = hydro_cfg["infiltration"]["horton"]
    f0 = np.where(cls == 0, hz["road"]["f0_mmh"], np.where(cls == 1, hz["open"]["f0_mmh"], 0.0))
    fc = np.where(cls == 0, hz["road"]["fc_mmh"], np.where(cls == 1, hz["open"]["fc_mmh"], 0.0))
    kk = 2.2
    dep = hydro_cfg["infiltration"]["depression_mm"]
    dep_grid = np.where(cls == 0, dep["road"], np.where(cls == 1, dep["open"], 0.0)) * float(dep_scale)
    dep_store = np.zeros_like(dem_use)
    h = np.zeros_like(dem_use)
    blocked = (~twin.in_domain) | twin.is_building  # walls: no flow, no ponding (rooftops ignored, see assumptions)
    wetfrac = float(wet.mean())
    H, V, ND, PF = [], [], [], []
    t_h = 0.0
    hthr = float(hydro_cfg["surface"].get("h_flood_m", 0.05))
    ttf = np.full_like(dem_use, np.nan); maxd = np.zeros_like(dem_use)
    rain_tot_mm = 0.0; infil_tot_mm = 0.0; drain_tot_mm = 0.0
    cell_area = twin.dx ** 2
    R_ext = np.concatenate([R, np.zeros((n_rec,) + R.shape[1:], dtype=R.dtype)]) if n_rec else R
    nt_out = nt + n_rec
    for k in range(nt_out):
        rmm_step = R_ext[k]  # mm per dt (zeros during recession tail)
        rmmh = rmm_step * 3600.0 / dt
        for _ in range(sub):
            t_h += sdt / 3600.0
            cap = fc + (f0 - fc) * np.exp(-kk * t_h)
            fim = np.minimum(cap, rmmh)
            need = np.maximum(dep_grid - dep_store, 0)
            to_dep = np.minimum(need * 3600.0 / sdt, np.maximum(rmmh - fim, 0))
            dep_store += to_dep * sdt / 3600.0
            eff = np.maximum(rmmh - fim, 0) - to_dep
            eff = np.where(wet, np.maximum(eff, 0), 0.0)  # no ponding on rooftops/outside
            rain_tot_mm += float(np.where(wet, rmmh, 0).mean()) * sdt / 3600.0 / max(wetfrac, 1e-9)
            infil_tot_mm += float(np.where(wet, fim, 0).mean()) * sdt / 3600.0 / max(wetfrac, 1e-9)
            sink, ret = dst.step(sdt, h, twin.dx)
            drain_tot_mm += float((sink - ret).mean()) * sdt * 1000.0 / max(wetfrac, 1e-9)  # NET surface->pipe
            h, vel, _ = step_surface(h, dem_use, man_use, eff, np.zeros_like(h), sink - ret, twin.dx, sdt, blocked=blocked)
            h[blocked] = 0.0
            assert np.all(np.isfinite(h)), "NaN/Inf in surface depth"
            assert (h >= -1e-9).all(), "negative depth"
        maxd = np.maximum(maxd, h)
        ttf[np.isnan(ttf) & (h >= hthr)] = (k + 1) * dt / 60.0
        if k % out_every == 0:
            H.append(h.astype(np.float32).copy()); V.append(vel.astype(np.float32).copy())
            ND.append(dst.node_depth.copy().astype(np.float32))
            PF.append(dst.pipe_flow.copy().astype(np.float32))
    return {"rain": R_ext.astype(np.float32), "depth": np.stack(H), "velocity": np.stack(V),
            "flooded": (np.stack(H) >= hthr),
            "node_depth": np.stack(ND), "pipe_flow": np.stack(PF),
            "pipe_capacity": np.array([e["capacity_m3s"] for e in network["edges"]], dtype=np.float32),
            "surcharge": dst.surcharge.copy(), "overflow": dst.overflow.copy(),
            "time_to_flood_min": ttf.astype(np.float32), "max_depth": maxd.astype(np.float32),
            "blockage": dst.blockage.copy(), "rain_spec": spec,
            "mass": {"rain_mm": rain_tot_mm, "infil_mm": infil_tot_mm, "drain_mm": drain_tot_mm,
                     "discharged_mm": dst.discharged_m3 / max(wet.sum(), 1) / (twin.dx ** 2) * 1000.0,
                     "node_stored_mm": float(dst.node_depth.sum() * 1.0) / max(wet.sum(), 1) / (twin.dx ** 2) * 1000.0,
                     "depression_mm": float(dep_store[wet].mean()) if wet.any() else 0.0,
                     "ponded_mm": float(h[wet].mean() * 1000.0) if wet.any() else 0.0,
                     "maxd_mm": float(maxd.max() * 1000.0)}}
