"""Probabilistic flood forecast pipeline: `run_forecast(t0)` (Task 2).

  ingest (Module A) -> quality control (B) -> gauge bias correction -> source mode
  -> STEPS ensemble nowcast + NWP/climatology blending (C)
  -> twin state at t0: physics on observed rain (open loop; Task 3 adds assimilation)
  -> surrogate depth ensemble (M, global) -> probabilistic flood forecast (N)
  -> hotspots + local physics refinement (M, local) -> road impacts -> health + provenance

    python -m forecast.run --event squall --seed 3 --t0 90
    python -m forecast.run --event squall --seed 3 --t0 90 --radar-outage 60:400   # degraded
    python -m forecast.run --replay archive.npz --t0 90                              # replay

Outputs: outputs/forecasts/<id>/forecast.json, maps.npz and exceedance PNGs.
Degradation (SRS §16): radar unusable -> gauge-only rain (uncertainty inflated, forecast
flagged DEGRADED); no usable radar or gauges -> climatology/NWP only (DEGRADED).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass

import numpy as np

from simulation import config as C

from .grid import RegionalGrid
from .quality import FAULT, MISSING, STALE, SUSPECT, VALID, check_gauges, check_radar_frame, summarize
from .steps import Climatology, StepsNowcaster, gauge_field, mean_field_bias, quantile_fields

USABLE = (VALID, SUSPECT)


@dataclass
class ForecastSources:
    radar: object = None          # RainfallSource (grid)
    gauges: object = None         # RainfallSource (points)
    nwp: object = None            # NwpSource
    truth: object = None          # StormEvent (synthetic demo / verification only)

    def describe(self):
        d = {k: getattr(getattr(self, k), "name", None) for k in ("radar", "gauges", "nwp")}
        # injected outages / faults are part of the configuration (and of the forecast id)
        for k in ("radar", "gauges"):
            src = getattr(self, k)
            cfg = {a: getattr(src, a) for a in ("outages", "faults") if getattr(src, a, None)}
            if cfg:
                d[k + "_config"] = cfg
        if self.truth is not None:
            d["event"] = self.truth.describe()
        return d


class _Ctx:
    """Static objects reused across forecast cycles (twin, network, surrogate, climatology)."""

    def __init__(self, cfg=None):
        from simulation.drainage.network import generate
        from simulation.terrain.twin import Twin
        from .probabilistic import road_segments
        from .adaptive import critical_mask
        from .surrogate.infer import FloodSurrogate
        self.cfg = cfg or C.load("forecast")
        self.cf = C.load_all()
        self.grid = RegionalGrid(self.cfg)
        self.twin = Twin(self.cf["terrain"])
        self.net = generate(self.twin, self.cf["drainage"], seed=self.cf["simulation"]["dataset"]["seed"], variant=0)
        s = self.cfg["surrogate"]
        self.surrogate = FloodSurrogate(s["model"], s["meta"], self.twin)
        self.clim = Climatology(self.cfg)
        self.nowcaster = StepsNowcaster(self.cfg, self.grid)
        self.roads = road_segments(self.twin)
        self.crit = critical_mask(self.twin, self.cfg)
        self.wet = self.twin.in_domain & ~self.twin.is_building


_CTX = None


def context(cfg=None):
    global _CTX
    if _CTX is None or (cfg is not None and cfg is not _CTX.cfg):
        _CTX = _Ctx(cfg)
    return _CTX


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except Exception:
        return None


def _sha1(path):
    try:
        return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]
    except OSError:
        return None


def _to_mm_steps(rates_mmh, r0, step):
    """Rates at step ends (N, ...) + rate at t0 -> mm per step (trapezoid)."""
    prev = np.concatenate([r0[None], rates_mmh[:-1]])
    return (0.5 * (prev + rates_mmh) * step / 60.0).astype(np.float32)


def run_forecast(t0, sources, members=None, refine=True, run_spec=None, seed=0, out_dir=None, save=True,
                 ctx=None):
    """Issue a 0-180 min probabilistic flood forecast at t0 (minutes since event start)."""
    T = {}
    tt = time.time()
    ctx = ctx or context()
    cfg, grid, twin = ctx.cfg, ctx.grid, ctx.twin
    step = float(cfg["step_min"])
    n_steps = int(cfg["max_lead_min"] // step)
    run_spec = dict(run_spec or {})
    run_spec.setdefault("seed", seed)
    times = step * np.arange(1, int(round(t0 / step)) + 1)
    if len(times) == 0:
        raise ValueError("t0 must be >= one step after the event start")

    # ---------------------------------------------------------------- A + B: ingest and QC
    radar_obs, prev = [], None
    for t in times:
        o = sources.radar.fetch(t) if sources.radar is not None else None
        if o is not None:
            check_radar_frame(o, prev, t, cfg)
            if o.status in USABLE:
                prev = o.grid
        radar_obs.append(o)
    ghist, radar_at = {}, {}
    for k, t in enumerate(times):
        pts = sources.gauges.fetch(t).points if sources.gauges is not None else []
        by_id = {p["id"]: p for p in pts}
        for gid in set(ghist) | set(by_id):
            ghist.setdefault(gid, [(tp, None) for tp in times[:k]])
            ghist[gid].append((t, by_id.get(gid)))
            p = by_id.get(gid) or next((q for _, q in reversed(ghist[gid]) if q), None)
            o = radar_obs[k]
            if p is not None:
                gi, gj = grid.nearest_ij(p["x_km"], p["y_km"])
                val = float(o.grid[gi, gj]) if (o is not None and o.status in USABLE) else np.nan
            else:
                val = np.nan
            radar_at.setdefault(gid, [np.nan] * k).append(val)
    gqc = check_gauges(ghist, times[-1], cfg, radar_at)
    valid_g = [g for g, q in gqc.items() if q["status"] == VALID]
    last = radar_obs[-1]
    radar_status = last.status if last is not None else MISSING
    radar_reasons = last.reasons if last is not None else ["no radar source configured"]
    T["ingest_qc"] = round(time.time() - tt, 2)

    # ---------------------------------------------------------------- mode + bias correction
    usable = [o is not None and o.status in USABLE for o in radar_obs]
    reasons = []
    if len(usable) >= 3 and all(usable[-3:]):
        mode = "radar"
    elif len(valid_g) >= 3:
        mode, reasons = "gauge", reasons + [f"radar {radar_status}: {'; '.join(radar_reasons) or 'unusable'}",
                                            "rainfall from gauges only (IDW) — uncertainty inflated"]
    else:
        mode, reasons = "climatology", reasons + [f"radar {radar_status}", f"only {len(valid_g)} valid gauges",
                                                  "rainfall from NWP/climatology only"]
    win = int(cfg["nowcast"]["gauge_bias"]["window_min"] // step)
    r_pairs, g_pairs = [], []
    for gid in valid_g:
        for (t, p), r in list(zip(ghist[gid], radar_at[gid]))[-win:]:
            if p is not None and np.isfinite(r):
                r_pairs.append(r); g_pairs.append(p["rain_mm"])
    B, npairs, applied = mean_field_bias(r_pairs, g_pairs, step, cfg) if mode == "radar" else (1.0, 0, False)

    def field_at(k):
        o = radar_obs[k]
        if mode == "radar" and o is not None and o.status in USABLE:
            return np.nan_to_num(o.grid) * B, "radar"
        pts = [p for gid in valid_g for (t, p) in [ghist[gid][k]] if p is not None]
        if pts:
            return np.nan_to_num(gauge_field(pts, grid, step)), "gauge"
        return np.zeros(grid.shape, np.float32), "none"

    hist_fields, hist_src = zip(*[field_at(k) for k in range(len(times))])
    hist_fields = np.array(hist_fields, np.float32)
    gaps = int(sum(s == "none" for s in hist_src))
    if gaps and mode != "climatology":
        reasons.append(f"{gaps} history steps without any rain observation (treated as dry)")
    T["mode_bias"] = round(time.time() - tt, 2)

    # ---------------------------------------------------------------- C: nowcast
    motion = None
    if mode == "gauge":
        idx = [k for k, u in enumerate(usable) if u]
        age = times[-1] - times[idx[-1]] if idx else np.inf
        from .motion import dense_motion, to_log
        if len(idx) >= 3 and age <= cfg["nowcast"]["degraded"]["motion_max_age_min"] and \
                idx[-1] - idx[-3] == 2:
            motion = dense_motion([to_log(radar_obs[k].grid)[0] for k in idx[-3:]])
        else:
            motion = np.zeros((2,) + grid.shape)
            reasons.append("no recent radar motion — persistence (zero advection) assumed")
    frames = list(hist_fields[-3:]) if len(hist_fields) >= 3 else [hist_fields[0]] * (3 - len(hist_fields)) + list(hist_fields)
    leads = step * np.arange(1, n_steps + 1)
    nwp = sources.nwp.forecast(t0, leads, grid) if sources.nwp is not None else None
    nc = ctx.nowcaster.run(frames, n_steps, members=members, seed=seed, motion=motion, nwp=nwp, clim=ctx.clim,
                           degraded=mode != "radar")
    Rm = nc["members"]                                          # (M, N, ny, nx) mm/h regional
    M = Rm.shape[0]
    T["nowcast"] = round(time.time() - tt, 2)

    # ---------------------------------------------------------------- campus rain + twin state
    camp_hist_rate = grid.to_campus(hist_fields, twin)          # (H, ny, nx) mm/h at step ends
    r_start = np.zeros_like(camp_hist_rate[:1])
    rain_hist = _to_mm_steps(camp_hist_rate, r_start[0], step)
    camp_fut_rate = grid.to_campus(Rm, twin)                    # (M, N, ny, nx)
    fut = np.stack([_to_mm_steps(camp_fut_rate[m], camp_hist_rate[-1], step) for m in range(M)])
    from simulation.hydraulics.simulate import simulate
    st = simulate(twin, ctx.net, dict(run_spec, blockage_level=run_spec.get("blockage_level", 0.0)),
                  ctx.cf["hydraulics"], ctx.cf["rainfall"], rain=rain_hist)
    from .surrogate.features import HIST, LEADS
    pad = max(0, HIST - rain_hist.shape[0])
    z = lambda a: np.concatenate([np.zeros((pad,) + a.shape[1:], a.dtype), a])[-HIST:]
    depth_now = st["depth"][-1]
    T["twin_state"] = round(time.time() - tt, 2)

    # ---------------------------------------------------------------- M global + N
    from .probabilistic import flood_stats, road_stats
    D = ctx.surrogate.predict(z(rain_hist), z(st["depth"]), fut, blockage=run_spec.get("blockage_level", 0.0))
    fl = cfg["flood"]
    thr = tuple(fl["thresholds_m"])
    lead_min = [step * l for l in LEADS]
    stats = flood_stats(D, lead_min, thr, fl["flood_depth_m"])
    T["surrogate"] = round(time.time() - tt, 2)

    # ---------------------------------------------------------------- M local
    from .adaptive import detect_hotspots, refine as do_refine
    tiles = detect_hotspots(stats, twin, cfg, depth_now, ctx.crit)
    adapt = {"tiles": 0, "note": "refinement disabled"}
    if refine and tiles:
        D, adapt = do_refine(tiles, D, LEADS, rain_hist, fut, run_spec, cfg, ctx.wet)
        stats = flood_stats(D, lead_min, thr, fl["flood_depth_m"])
    elif not tiles:
        adapt = {"tiles": 0, "note": "no hotspots: surrogate forecast kept"}
    roads = road_stats(D, lead_min, ctx.roads, thr, fl["flood_depth_m"])
    T["adaptive_roads"] = round(time.time() - tt, 2)

    # ---------------------------------------------------------------- health, summary, provenance
    recent = [o.status if o is not None else MISSING for o in radar_obs[-6:]]
    if mode == "radar" and any(s != VALID for s in recent):
        reasons.append(f"radar QC in last 30 min: {recent}")
    bad_g = {g: q["status"] for g, q in gqc.items() if q["status"] != VALID}
    if bad_g:
        reasons.append(f"gauges rejected/flagged: {bad_g}")
    status = "OPERATIONAL" if mode == "radar" and not any(s in (FAULT, MISSING, STALE) for s in recent) \
        and len(valid_g) >= max(3, len(gqc) // 2) else "DEGRADED"
    cell_m2 = twin.dx ** 2
    wet = ctx.wet
    area = lambda mask: float(mask[..., wet].sum(-1) * cell_m2) if mask.ndim == 2 else (mask[..., wet].sum(-1) * cell_m2)
    fa = np.array([[area(D[m, l] >= fl["flood_depth_m"]) for l in range(len(lead_min))] for m in range(M)])
    camp_cum = fut.cumsum(1)[:, :, wet].mean(-1)                 # (M, N) mm
    rep_idx = [lead_min.index(l) for l in fl["report_leads_min"] if l in lead_min]
    fid = f"t{int(t0):04d}_" + hashlib.sha1(json.dumps([sources.describe(), t0, seed, M, run_spec],
                                                        sort_keys=True, default=str).encode()).hexdigest()[:8]
    q3 = lambda a: {"p10": round(float(np.quantile(a, 0.1)), 2), "p50": round(float(np.quantile(a, 0.5)), 2),
                    "p90": round(float(np.quantile(a, 0.9)), 2)}
    forecast = {
        "forecast_id": fid, "issued_t_min": float(t0), "horizon_min": float(cfg["max_lead_min"]),
        "sources": sources.describe(),
        "health": {"status": status, "rain_source_mode": mode, "degraded": status != "OPERATIONAL",
                   "reasons": reasons,
                   "uncertainty_inflation": cfg["nowcast"]["degraded"]["noise_factor"] if mode != "radar" else 1.0},
        "quality": summarize(radar_status, radar_reasons, gqc),
        "rainfall": {
            "mode": mode, "gauge_mean_field_bias": {"factor": round(B, 3), "pairs": npairs, "applied": applied},
            "nowcast": {k: v for k, v in nc["diag"].items()},
            "campus_cumulative_mm_by_lead": {int(leads[k - 1]): q3(camp_cum[:, k - 1]) for k in (3, 6, 12, 24, 36)},
            "climatology": ctx.clim.describe(),
            "provenance": {"observations": getattr(sources.radar, "provenance", None) or "none",
                           "corrected_field": "derived", "nowcast": "modelled",
                           "note": "radar pixels ~1 km: campus rainfall is spatially smooth at this scale"},
        },
        "flood": {
            "lead_min": lead_min, "members": M, "thresholds_m": list(thr),
            "twin_state": {"source": "physics on observed rain (open loop)", "max_depth_now_m": round(float(depth_now.max()), 3),
                           "flooded_area_now_m2": area(depth_now >= fl["flood_depth_m"]),
                           "mass_rel_error": float(st["mass"]["rel_error"])},
            "domain": {"flooded_area_m2": {int(lead_min[l]): q3(fa[:, l]) for l in range(len(lead_min))},
                       "max_expected_depth_m": {int(lead_min[l]): round(float(stats["expected"][l].max()), 3)
                                                for l in range(len(lead_min))}},
            "exceedance_area_m2": {f"{int(t * 100)}cm": {int(lead_min[l]): area(stats["exceed"][t][l] >= 0.5)
                                                         for l in rep_idx} for t in thr},
            "hotspots": tiles, "adaptive_refinement": adapt,
            "roads": roads, "velocity": "not forecast (surrogate predicts depth only; see Task-1 gaps)",
            "probability_note": "ensemble frequencies conditional on the rainfall ensemble and model; not calibrated",
            "provenance": "modelled",
        },
        "timings_s": T,
        "provenance": {
            "code_commit": _git_commit(), "config_sha1": hashlib.sha1(json.dumps(
                {"forecast": cfg, **ctx.cf}, sort_keys=True, default=str).encode()).hexdigest()[:12],
            "surrogate": {"file": cfg["surrogate"]["model"], "sha1": _sha1(cfg["surrogate"]["model"]),
                          "arch": ctx.surrogate.meta.get("arch")},
            "terrain": twin.meta, "drainage": "synthetic network variant 0 (verified=false)",
            "run_spec": run_spec, "seed": seed,
        },
    }
    T["total"] = round(time.time() - tt, 2)
    maps = {"lead_min": np.array(lead_min), "report_leads_min": np.array([lead_min[i] for i in rep_idx]),
            "expected": stats["expected"][rep_idx], "p10": stats["p10"][rep_idx], "p50": stats["p50"][rep_idx],
            "p90": stats["p90"][rep_idx], "peak_expected": stats["peak_expected"], "peak_p90": stats["peak_p90"],
            "peak_time_min": stats["peak_time_min"], "time_to_threshold_min": stats["time_to_threshold_min"],
            "duration_expected_min": stats["duration_expected_min"], "depth_now": depth_now,
            **{f"exceed_{int(t * 100)}cm": stats["exceed"][t][rep_idx] for t in thr},
            **{f"rain_{k}_mmh": v[[int(l // step) - 1 for l in maps_leads(cfg)]]
               for k, v in quantile_fields(Rm).items()}}
    if save:
        out_dir = out_dir or os.path.join("outputs", "forecasts", fid)
        os.makedirs(out_dir, exist_ok=True)
        json.dump(forecast, open(os.path.join(out_dir, "forecast.json"), "w"), indent=1, default=_json)
        np.savez_compressed(os.path.join(out_dir, "maps.npz"), **{k: np.asarray(v, np.float32) for k, v in maps.items()})
        _plot(out_dir, maps, twin, thr, forecast)
        forecast["output_dir"] = out_dir
    return {"forecast": forecast, "maps": maps, "depth_members": D, "rain_members": Rm, "stats": stats,
            "campus_rain_future": fut, "campus_rain_hist": rain_hist}


def maps_leads(cfg):
    return [l for l in cfg["flood"]["report_leads_min"] if l <= cfg["max_lead_min"]]


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def _plot(out_dir, maps, twin, thr, fc):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    dom = twin.in_domain
    leads = maps["report_leads_min"]
    for t in thr:
        key = f"exceed_{int(t * 100)}cm"
        fig, ax = plt.subplots(1, len(leads), figsize=(3.2 * len(leads), 3.0), constrained_layout=True)
        for a, l, P in zip(np.atleast_1d(ax), leads, maps[key]):
            im = a.imshow(np.where(dom, P, np.nan), vmin=0, vmax=1, cmap="Blues")
            a.imshow(np.where(twin.is_building, 1.0, np.nan), cmap="Greys", vmin=0, vmax=2, alpha=0.6)
            a.set_title(f"+{int(l)} min"); a.set_xticks([]); a.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.8, label=f"P(depth > {int(t * 100)} cm)")
        h = fc["health"]
        fig.suptitle(f"{fc['forecast_id']}  [{h['status']} / rain: {h['rain_source_mode']}]  modelled")
        fig.savefig(os.path.join(out_dir, f"exceedance_{int(t * 100)}cm.png"), dpi=90)
        plt.close(fig)


# ------------------------------------------------------------------------------------ CLI
def build_sources(a, cfg):
    from .obs import GaugeCSVSource, RadarArchiveReplay, SyntheticGauges, SyntheticNWP, SyntheticRadar
    from .storms import StormEvent
    grid = RegionalGrid(cfg)
    ev = StormEvent(seed=a.seed, kind=a.event, intensity=a.intensity) if a.event else None
    outages = [tuple(float(v) for v in a.radar_outage.split(":"))] if a.radar_outage else []
    gfaults = {}
    for f in a.gauge_fault or []:
        gid, kind, t = f.split(":")[:3]
        extra = f.split(":")[3:]
        gfaults[gid] = (kind, float(t), *[float(e) for e in extra])
    radar = RadarArchiveReplay(a.replay) if a.replay else (SyntheticRadar(ev, grid, outages=outages) if ev else None)
    gauges = GaugeCSVSource(a.gauge_csv) if a.gauge_csv else (SyntheticGauges(ev, faults=gfaults) if ev else None)
    nwp = SyntheticNWP(ev) if (ev and not a.no_nwp) else None
    return ForecastSources(radar=radar, gauges=gauges, nwp=nwp, truth=ev)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="squall", help="synthetic event kind: squall | convective | stratiform")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--intensity", type=float, default=1.0)
    ap.add_argument("--t0", type=float, default=90.0)
    ap.add_argument("--members", type=int, default=None)
    ap.add_argument("--radar-outage", default=None, help="from:to minutes")
    ap.add_argument("--gauge-fault", action="append", help="ID:kind:t_from[:extra], e.g. G3:frozen:40")
    ap.add_argument("--no-nwp", action="store_true")
    ap.add_argument("--no-refine", action="store_true")
    ap.add_argument("--blockage", type=float, default=0.0)
    ap.add_argument("--replay", default=None, help="radar archive .npz (RadarArchiveReplay)")
    ap.add_argument("--gauge-csv", default=None)
    a = ap.parse_args()
    cfg = C.load("forecast")
    src = build_sources(a, cfg)
    res = run_forecast(a.t0, src, members=a.members, refine=not a.no_refine,
                       run_spec={"blockage_level": a.blockage}, seed=a.seed)
    f = res["forecast"]
    print(json.dumps({"id": f["forecast_id"], "health": f["health"], "timings_s": f["timings_s"],
                      "flooded_area_m2": {k: v for k, v in f["flood"]["domain"]["flooded_area_m2"].items()
                                          if k in (15, 30, 60, 120, 180)},
                      "hotspots": [{k: h[k] for k in ("reasons", "p_exceed_20cm_max", "early_warning",
                                                      "time_to_threshold_min")} for h in f["flood"]["hotspots"]],
                      "top_roads": [{k: r[k] for k in ("id", "name", "expected_peak_m", "p_exceed",
                                                       "time_to_threshold_min")} for r in f["flood"]["roads"][:5]],
                      "output_dir": f.get("output_dir")}, indent=1, default=_json))


if __name__ == "__main__":
    main()
