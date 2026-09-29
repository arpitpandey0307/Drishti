"""Verify a forecast against the synthetic truth (twin experiment; SRS Module Z preview).

    python -m forecast.verify --event squall --seed 3 --t0 90 [--compare-refine]

Truth = the hidden StormEvent rainfall and the full coupled physics driven by it.
Reports, per lead:
  rain   CSI (1 mm/h) of the ensemble median vs persistence, MAE, spread/skill ratio, CRPS
  flood  RMSE and CSI (10 cm) of the expected depth, Brier score of P(depth > 10 cm),
         P10-P90 interval coverage, and early-warning skill for cells that cross 10 cm
         after t0 (AC-12: flagged at t0 with P >= 0.5 before the crossing).
These numbers score the system against its own synthetic truth, not against observations.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

from simulation import config as C

from .run import build_sources, context, run_forecast, _json


def crps_ensemble(ens, obs):
    """Mean CRPS of an ensemble (M, ...) against obs (...)."""
    ens = np.asarray(ens, float)
    t1 = np.abs(ens - obs[None]).mean(0)
    s = np.sort(ens, axis=0)
    M = s.shape[0]
    w = (2 * np.arange(1, M + 1) - M - 1)[(slice(None),) + (None,) * (s.ndim - 1)]
    t2 = (w * s).sum(0) / (M * M)
    return float((t1 - t2).mean())


def csi(p, o):
    return float((p & o).sum() / max((p | o).sum(), 1))


def verify(t0, sources, res, ctx, refine_res=None):
    ev, cfg, grid, twin = sources.truth, ctx.cfg, ctx.grid, ctx.twin
    step = float(cfg["step_min"])
    Rm = res["rain_members"]
    leads = step * np.arange(1, Rm.shape[1] + 1)
    last_obs = ev.rate(grid, t0) * 1.0
    rain = []
    for l in (15, 30, 60, 120, 180):
        k = int(l // step) - 1
        tr = ev.rate(grid, t0 + l)
        med = np.median(Rm[:, k], 0)
        mean = Rm[:, k].mean(0)
        rain.append({"lead_min": l, "csi_1mmh": round(csi(med >= 1, tr >= 1), 3),
                     "csi_1mmh_persistence": round(csi(last_obs >= 1, tr >= 1), 3),
                     "mae_mmh": round(float(np.abs(mean - tr).mean()), 3),
                     "mae_persistence_mmh": round(float(np.abs(last_obs - tr).mean()), 3),
                     "spread_skill": round(float(Rm[:, k].std(0).mean() / max(np.abs(mean - tr).mean(), 1e-6)), 2),
                     "crps_mmh": round(crps_ensemble(Rm[:, k], tr), 3)})
    # truth flood: physics on the true (fine-scale) rainfall
    from simulation.hydraulics.simulate import simulate
    from .surrogate.features import LEADS
    H = int(round(t0 / step))
    times = step * np.arange(1, H + max(LEADS) + 1)
    true_rain = ev.campus_rain(twin, times, step)
    tr = simulate(twin, ctx.net, dict(res["forecast"]["provenance"]["run_spec"]), ctx.cf["hydraulics"],
                  ctx.cf["rainfall"], rain=true_rain)
    truth = tr["depth"][[H - 1 + l for l in LEADS]]
    truth_now = tr["depth"][H - 1]
    wet = ctx.wet
    fd = cfg["flood"]["flood_depth_m"]

    def flood_scores(D, st):
        rows = []
        for i, l in enumerate(st["lead_min"]):
            t_, e = truth[i][wet], st["expected"][i][wet]
            P = st["exceed"][0.1][i][wet]
            o = t_ >= 0.1
            act = (t_ > 0.01) | (st["p90"][i][wet] > 0.01)
            cov = ((t_ >= st["p10"][i][wet]) & (t_ <= st["p90"][i][wet]))[act].mean() if act.any() else np.nan
            rows.append({"lead_min": int(l), "rmse_m": round(float(np.sqrt(((e - t_) ** 2).mean())), 4),
                         "csi_10cm": round(csi(e >= 0.1, o), 3), "csi_10cm_p50": round(csi(st["p50"][i][wet] >= 0.1, o), 3),
                         "brier_10cm": round(float(((P - o) ** 2).mean()), 4),
                         "p10_p90_coverage": round(float(cov), 3) if np.isfinite(cov) else None,
                         "truth_flooded_m2": float(o.sum() * twin.dx ** 2)})
        # AC-12 early warning: cells dry now that truly flood later
        future_hit = (truth >= fd).any(0) & (truth_now < fd) & wet
        flagged = (st["p_reach_flood_depth"] >= 0.5) & (truth_now < fd) & wet
        first = np.argmax(truth >= fd, axis=0)
        lead_arr = np.asarray(st["lead_min"], float)
        ew = {"cells_crossing_after_t0": int(future_hit.sum()),
              "flagged_before_crossing": int((flagged & future_hit).sum()),
              "hit_rate": round(float((flagged & future_hit).sum() / max(future_hit.sum(), 1)), 3),
              "false_alarm_ratio": round(float((flagged & ~future_hit).sum() / max(flagged.sum(), 1)), 3),
              "median_warning_lead_min": float(np.median(lead_arr[first[flagged & future_hit]]))
              if (flagged & future_hit).any() else None}
        return rows, ew

    flood, ew = flood_scores(res["depth_members"], res["stats"])
    out = {"forecast_id": res["forecast"]["forecast_id"], "t0": t0, "event": ev.describe(),
           "health": res["forecast"]["health"], "rain": rain, "flood": flood, "early_warning": ew,
           "truth": {"max_depth_m": float(truth.max()), "mass_rel_error": float(tr["mass"]["rel_error"]),
                     "true_campus_rain_after_t0_mm": float(true_rain[H:].sum(0)[wet].mean())},
           "note": "twin experiment: scored against synthetic truth, not observations"}
    if refine_res is not None:
        f2, ew2 = flood_scores(refine_res["depth_members"], refine_res["stats"])
        out["surrogate_only"] = {"flood": f2, "early_warning": ew2}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default="squall")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--intensity", type=float, default=1.0)
    ap.add_argument("--t0", type=float, default=90.0)
    ap.add_argument("--members", type=int, default=None)
    ap.add_argument("--radar-outage", default=None)
    ap.add_argument("--gauge-fault", action="append")
    ap.add_argument("--no-nwp", action="store_true")
    ap.add_argument("--replay", default=None)
    ap.add_argument("--gauge-csv", default=None)
    ap.add_argument("--blockage", type=float, default=0.0)
    ap.add_argument("--compare-refine", action="store_true", help="also score the surrogate-only forecast")
    a = ap.parse_args()
    cfg = C.load("forecast")
    src = build_sources(a, cfg)
    ctx = context(cfg)
    spec = {"blockage_level": a.blockage}
    res = run_forecast(a.t0, src, members=a.members, run_spec=spec, seed=a.seed, ctx=ctx)
    base = run_forecast(a.t0, src, members=a.members, run_spec=spec, seed=a.seed, ctx=ctx, refine=False,
                        save=False) if a.compare_refine else None
    v = verify(a.t0, src, res, ctx, base)
    path = os.path.join(res["forecast"]["output_dir"], "verification.json")
    json.dump(v, open(path, "w"), indent=1, default=_json)
    print("health:", v["health"]["status"], v["health"]["rain_source_mode"])
    print(f"{'lead':>5} {'CSI rain':>9} {'persist':>8} {'CRPS':>6} | {'RMSE m':>7} {'CSI10':>6} {'Brier':>6} {'cover':>6}")
    fl = {r["lead_min"]: r for r in v["flood"]}
    for r in v["rain"]:
        f = fl.get(r["lead_min"], {})
        print(f"{r['lead_min']:5d} {r['csi_1mmh']:9.3f} {r['csi_1mmh_persistence']:8.3f} {r['crps_mmh']:6.2f} | "
              f"{f.get('rmse_m', float('nan')):7.4f} {f.get('csi_10cm', float('nan')):6.3f} "
              f"{f.get('brier_10cm', float('nan')):6.4f} {f.get('p10_p90_coverage') or float('nan'):6.3f}")
    print("early warning (AC-12):", v["early_warning"])
    if base is not None:
        print("surrogate only early warning:", v["surrogate_only"]["early_warning"])
    print("->", path)


if __name__ == "__main__":
    main()
