"""Adaptive fidelity engine (SRS Module M, local level).

  fast global screen (surrogate ensemble)
    -> hotspot detection on tiles: high risk OR high uncertainty OR critical-asset adjacent
    -> high-fidelity rerun: the full Task-1 coupled 1D/2D physics for representative members
       (rain-rank quantiles, default P50 and P90) — these runs also carry the true drainage
       state (blockage, pump status, outfall boundary) that the surrogate only sees coarsely
    -> refined forecast: inside hotspot tiles, representative members are replaced by physics
       and every other member receives the physics-minus-surrogate correction of the nearest
       representative (by future-rain rank). Outside hotspots the surrogate is kept.
"""
from __future__ import annotations

import csv
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

_P = {}


def critical_mask(twin, cfg, path="data/blocks_centroids.csv"):
    """Wet cells within `critical_radius_m` of campus building (block) centroids: building access."""
    r = float(cfg["adaptive"]["critical_radius_m"])
    m = np.zeros(twin.dem.shape, bool)
    if not os.path.exists(path):
        return m
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            x, y = twin.ll_to_xy(float(row["lat"]), float(row["lon"]))
            m |= np.hypot(twin.X - x, twin.Y - y) <= r
    return m & twin.in_domain & ~twin.is_building


def detect_hotspots(stats, twin, cfg, depth_now, crit=None):
    a = cfg["adaptive"]
    T = int(a["tile"])
    wet = twin.in_domain & ~twin.is_building
    p20 = stats["p_exceed_any"][0.2]
    p10 = stats["p_exceed_any"][0.1]
    spread = stats["peak_p90"] - stats["peak_p10"]
    crit = critical_mask(twin, cfg) if crit is None else crit
    fd = stats["flood_depth_m"]
    tiles = []
    for i0 in range(0, twin.ny, T):
        for j0 in range(0, twin.nx, T):
            sl = (slice(i0, i0 + T), slice(j0, j0 + T))
            w = wet[sl]
            if not w.any():
                continue
            risk, unc = float(p20[sl][w].max()), float(spread[sl][w].max())
            near_crit = bool((crit[sl] & w).any())
            crit_sig = near_crit and float(p10[sl][w].max()) >= 0.1
            reasons = [r for r, ok in (("high risk", risk >= a["risk_p"]), ("high uncertainty", unc >= a["spread_m"]),
                                       ("critical-asset adjacent", crit_sig)) if ok]
            if not reasons:
                continue
            ttt = stats["time_to_threshold_min"][sl][w]
            now_max = float(depth_now[sl][w].max())
            tiles.append({
                "i0": i0, "i1": min(i0 + T, twin.ny), "j0": j0, "j1": min(j0 + T, twin.nx),
                "reasons": reasons, "score": round(risk + unc + 0.25 * crit_sig, 3),
                "p_exceed_20cm_max": round(risk, 2), "peak_spread_m": round(unc, 3),
                "max_depth_now_m": round(now_max, 3),
                "early_warning": now_max < fd and float(p10[sl][w].max()) >= 0.5,   # AC-12
                "time_to_threshold_min": float(np.nanmin(ttt)) if np.isfinite(ttt).any() else None,
                "centre_latlon": [float(twin.lat[(i0 + min(i0 + T, twin.ny)) // 2, 0]),
                                  float(twin.lon[0, (j0 + min(j0 + T, twin.nx)) // 2])],
            })
    tiles.sort(key=lambda t: -t["score"])
    return tiles[: int(a["max_tiles"])]


def _init():
    from simulation import config as C
    from simulation.drainage.network import generate
    from simulation.terrain.twin import Twin
    cf = C.load_all()
    tw = Twin(cf["terrain"])
    _P.update(cf=cf, twin=tw, net=generate(tw, cf["drainage"], seed=cf["simulation"]["dataset"]["seed"], variant=0))


def _physics(args):
    rain, run_spec = args
    from simulation.hydraulics.simulate import simulate
    r = simulate(_P["twin"], _P["net"], run_spec, _P["cf"]["hydraulics"], _P["cf"]["rainfall"], rain=rain)
    return r["depth"], float(r["mass"]["rel_error"])


def run_physics(rains, run_spec, workers=2):
    """Full coupled physics for several rain inputs (parallel processes, sequential fallback)."""
    jobs = [(r, run_spec) for r in rains]
    try:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs)), initializer=_init) as ex:
            return list(ex.map(_physics, jobs))
    except Exception:
        if not _P:
            _init()
        return [_physics(j) for j in jobs]


def refine(tiles, D, lead_steps, rain_hist, fut, run_spec, cfg, wet_mean, workers=2):
    """Refine surrogate members D (M, L, ny, nx) inside hotspot tiles with physics.

    rain_hist: (H, ny, nx) mm/step from event start to t0; fut: (M, N, ny, nx) member rain.
    Returns (D_refined, report)."""
    if not tiles:
        return D, {"tiles": 0, "note": "no hotspots: surrogate forecast kept"}
    t = time.time()
    M = D.shape[0]
    tot = np.array([float(f.sum(0)[wet_mean].mean()) for f in fut])
    order = np.argsort(tot)
    reps = list(dict.fromkeys(int(order[min(int(q * M), M - 1)]) for q in cfg["adaptive"]["representative_quantiles"]))
    H = rain_hist.shape[0]
    rains = [np.concatenate([rain_hist, fut[m][: max(lead_steps)]]) for m in reps]
    phys = run_physics(rains, run_spec, workers)
    mask = np.zeros(D.shape[2:], bool)
    for tl in tiles:
        mask[tl["i0"]:tl["i1"], tl["j0"]:tl["j1"]] = True
    D = D.copy()
    corr = {}
    for m, (depth, _) in zip(reps, phys):
        P = depth[[H - 1 + l for l in lead_steps]]
        corr[m] = np.where(mask, P - D[m], 0.0)
    rank = {int(m): k for k, m in enumerate(order)}
    for m in range(M):
        near = min(reps, key=lambda r: abs(rank[r] - rank[m]))
        D[m] = np.where(mask, np.maximum(D[m] + corr[near], 0.0), D[m])
    wet_tiles = mask & wet_mean
    report = {
        "tiles": len(tiles), "representative_members": reps,
        "representative_quantiles": cfg["adaptive"]["representative_quantiles"][:len(reps)],
        "representative_rain_mm": [round(float(tot[m]), 1) for m in reps],
        "mean_abs_correction_m": round(float(np.mean([np.abs(c[:, wet_tiles]).mean() for c in corr.values()])), 4),
        "max_abs_correction_m": round(float(max(np.abs(c).max() for c in corr.values())), 3),
        "physics_mass_rel_error": [p[1] for p in phys],
        "physics_runtime_s": round(time.time() - t, 1),
        "provenance": "modelled (Task-1 coupled 1D/2D physics)",
    }
    return D, report
