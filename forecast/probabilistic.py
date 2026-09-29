"""Probabilistic flood forecast (SRS Module N) from a depth ensemble.

Input: depth members D (M, L, ny, nx) at leads `lead_min` (minutes after t0).
Per cell and per road segment: expected depth, P10 / P50 / P90, peak depth and peak time,
time to threshold, P(depth > 10 / 20 / 30 cm) and flood duration. Probabilities are ensemble
frequencies, i.e. conditional on the rainfall ensemble and the model (stated in outputs).
"""
from __future__ import annotations

import json
import warnings

import numpy as np


def _lead_weights(lead_min):
    """Minutes represented by each lead (midpoint rule on the irregular lead grid)."""
    t = np.asarray(lead_min, float)
    edges = np.concatenate([[0.0], (t[:-1] + t[1:]) / 2, [t[-1]]])
    return np.diff(edges)


def first_crossing(D, lead_min, thr):
    """(M, ...) minutes to first depth >= thr per member (nan if never)."""
    hit = D >= thr
    any_ = hit.any(1)
    k = np.argmax(hit, axis=1)
    return np.where(any_, np.asarray(lead_min, float)[k], np.nan)


def flood_stats(D, lead_min, thresholds=(0.1, 0.2, 0.3), flood_depth=0.1):
    D = np.asarray(D, np.float32)
    lead = np.asarray(lead_min, float)
    q = np.quantile(D, [0.1, 0.5, 0.9], axis=0)
    peak = D.max(1)                                       # (M, ny, nx)
    pq = np.quantile(peak, [0.1, 0.5, 0.9], axis=0)
    wet_peak = peak >= 0.01
    peak_t = np.where(wet_peak, lead[np.argmax(D, axis=1)], np.nan)
    ttt = first_crossing(D, lead, flood_depth)
    w = _lead_weights(lead)[None, :, None, None]
    dur = ((D >= flood_depth) * w).sum(1)                 # (M, ny, nx) minutes
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = {
            "lead_min": lead,
            "expected": D.mean(0), "p10": q[0], "p50": q[1], "p90": q[2],
            "peak_expected": peak.mean(0), "peak_p10": pq[0], "peak_p50": pq[1], "peak_p90": pq[2],
            "peak_time_min": np.nanmedian(np.where(wet_peak, peak_t, np.nan), axis=0)
            if wet_peak.any() else np.full(D.shape[2:], np.nan),
            "time_to_threshold_min": np.nanmedian(ttt, axis=0) if np.isfinite(ttt).any()
            else np.full(D.shape[2:], np.nan),
            "p_reach_flood_depth": np.isfinite(ttt).mean(0),
            "duration_expected_min": dur.mean(0),
            "exceed": {float(t): (D >= t).mean(0) for t in thresholds},          # (L, ny, nx)
            "p_exceed_any": {float(t): (peak >= t).mean(0) for t in thresholds},  # (ny, nx)
            "flood_depth_m": flood_depth, "members": D.shape[0],
        }
    return out


# ----------------------------------------------------------------- road segments
def road_segments(twin, path="data/roads.geojson", step_m=2.0):
    """Rasterise drivable road features onto the twin: [{id, name, highway, cells: (i, j)}]."""
    segs = []
    wet = twin.in_domain & ~twin.is_building
    for n, f in enumerate(json.load(open(path, encoding="utf-8"))["features"]):
        p, g = f["properties"], f["geometry"]
        if p.get("highway") in ("footway", "steps", "path"):
            continue
        lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        cells = set()
        for line in lines:
            xy = np.array([twin.ll_to_xy(la, lo) for lo, la in line], float)
            for a, b in zip(xy[:-1], xy[1:]):
                k = max(int(np.hypot(*(b - a)) / step_m), 1)
                pts = a + (b - a) * np.linspace(0, 1, k + 1)[:, None]
                ii, jj = twin.xy_to_ij(pts[:, 0], pts[:, 1])
                ok = (ii >= 0) & (ii < twin.ny) & (jj >= 0) & (jj < twin.nx)
                for i, j in zip(ii[ok], jj[ok]):
                    if wet[i, j]:
                        cells.add((int(i), int(j)))
        if cells:
            ij = np.array(sorted(cells))
            segs.append({"id": f"R-{p.get('osm_id') or n}", "name": p.get("name") or "",
                         "highway": p.get("highway") or "", "cells": (ij[:, 0], ij[:, 1])})
    return segs


def road_stats(D, lead_min, segs, thresholds=(0.1, 0.2, 0.3), flood_depth=0.1):
    """Per road segment, using the worst cell on the segment in each member at each lead."""
    lead = np.asarray(lead_min, float)
    w = _lead_weights(lead)
    rows = []
    for s in segs:
        S = D[:, :, s["cells"][0], s["cells"][1]].max(-1)            # (M, L)
        peak = S.max(1)
        ttt = first_crossing(S[..., None], lead, flood_depth)[:, 0]
        wet = peak >= 0.01
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            rows.append({
                "id": s["id"], "name": s["name"], "highway": s["highway"], "n_cells": int(len(s["cells"][0])),
                "expected_peak_m": round(float(peak.mean()), 3),
                "peak_p10_m": round(float(np.quantile(peak, 0.1)), 3),
                "peak_p90_m": round(float(np.quantile(peak, 0.9)), 3),
                "peak_time_min": float(np.median(lead[np.argmax(S[wet], 1)])) if wet.any() else None,
                "time_to_threshold_min": float(np.nanmedian(ttt)) if np.isfinite(ttt).any() else None,
                "p_exceed": {f"{int(t * 100)}cm": round(float((peak >= t).mean()), 2) for t in thresholds},
                "duration_expected_min": round(float(((S >= flood_depth) * w).sum(1).mean()), 1),
                "expected_by_lead_m": [round(float(v), 3) for v in S.mean(0)],
            })
    rows.sort(key=lambda r: -r["expected_peak_m"])
    return rows
