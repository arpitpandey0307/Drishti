"""SRS §7 baseline experiments B1-B5: which components materially improve prediction.

  B1  rainfall threshold only          (flood everywhere if rain intensity > threshold)
  B2  rainfall + DEM                   (surface routing, no infiltration, no drainage)
  B3  rainfall + DEM + runoff          (+ interception / infiltration / depression)
  B4  rainfall + runoff + 1D drainage  (no 2D lateral routing: water ponds where it falls)
  B5  full coupled 1D/2D model         (reference)
B6/B7 (assimilation / adaptive forecasting) arrive with SRS Tasks 3 and 2.
"""
from __future__ import annotations

import numpy as np

from .hydraulics.simulate import simulate

CONFIGS = {
    "B2": {"infiltration": False, "drainage": False, "surface_routing": True},
    "B3": {"infiltration": True, "drainage": False, "surface_routing": True},
    "B4": {"infiltration": True, "drainage": True, "surface_routing": False},
    "B5": {"infiltration": True, "drainage": True, "surface_routing": True},
}


def b1_threshold(res, twin, thr_mmh=30.0, h_flood=0.05):
    """Rainfall-threshold baseline: whole domain flagged when peak intensity > thr."""
    dt_h = 5.0 / 60.0
    peak = float(res["rain"].max(axis=0)[twin.in_domain].max() / dt_h)
    return np.where(twin.in_domain, h_flood if peak > thr_mmh else 0.0, 0.0)


def flood_scores(pred_maxd, ref_maxd, mask, thr=0.05):
    p, r = (pred_maxd >= thr) & mask, (ref_maxd >= thr) & mask
    tp, fp, fn = (p & r).sum(), (p & ~r).sum(), (~p & r).sum()
    return {
        "csi": float(tp / max(tp + fp + fn, 1)),
        "iou": float(tp / max((p | r).sum(), 1)),
        "precision": float(tp / max(tp + fp, 1)), "recall": float(tp / max(tp + fn, 1)),
        "false_alarm_ratio": float(fp / max(tp + fp, 1)),
        "depth_mae_m": float(np.abs(pred_maxd - ref_maxd)[mask].mean()),
    }


def run_all(twin, net, spec, hyd_cfg, rain_cfg, reference=None):
    """Run B2-B5 for one scenario and score each against `reference` max-depth
    (defaults to B5, i.e. how much each simplification departs from the full model)."""
    out = {name: simulate(twin, net, spec, hyd_cfg, rain_cfg, components=c) for name, c in CONFIGS.items()}
    ref = out["B5"]["max_depth"] if reference is None else reference
    mask = twin.in_domain & ~twin.is_building
    scores = {"B1": flood_scores(b1_threshold(out["B5"], twin), ref, mask)}
    for name, r in out.items():
        scores[name] = flood_scores(r["max_depth"], ref, mask)
    return scores, out
