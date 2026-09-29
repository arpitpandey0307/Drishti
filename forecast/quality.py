"""Observation quality engine (SRS Module B).

Every observation gets VALID | SUSPECT | STALE | MISSING | FAULT plus machine-readable
reasons. Checks: impossible values, spikes, frozen sensors, clock drift, missing intervals,
stale data and gauge-vs-radar contradictions. Only VALID data drive the nowcast; SUSPECT data
are reported (and excluded from bias correction); FAULT / MISSING / STALE are rejected.
"""
from __future__ import annotations

import numpy as np

VALID, SUSPECT, STALE, MISSING, FAULT = "VALID", "SUSPECT", "STALE", "MISSING", "FAULT"
_RANK = {VALID: 0, SUSPECT: 1, STALE: 2, MISSING: 3, FAULT: 4}


def worst(*statuses):
    return max(statuses, key=_RANK.get)


def check_radar_frame(obs, prev_grid, t_now, cfg):
    """QC one radar Observation in place; returns its status."""
    q = cfg["quality"]
    if obs.grid is None:
        obs.status = MISSING
        return obs.status
    g = obs.grid
    reasons, st = [], VALID
    age = t_now - (obs.obs_time_min if obs.obs_time_min is not None else -np.inf)
    if age > q["radar_stale_min"]:
        st, reasons = worst(st, STALE), reasons + [f"age {age:.0f} min"]
    cov = float(np.isfinite(g).mean())
    if cov < 0.5:
        st, reasons = worst(st, FAULT), reasons + [f"coverage {cov:.0%}"]
    elif cov < q["radar_min_coverage"]:
        st, reasons = worst(st, SUSPECT), reasons + [f"coverage {cov:.0%}"]
    fin = g[np.isfinite(g)]
    if fin.size and (fin.min() < 0 or fin.max() > q["radar_max_mmh"]):
        st, reasons = worst(st, FAULT), reasons + ["impossible rain rate"]
    if prev_grid is not None and fin.size:
        pm, cm = float(np.nanmean(prev_grid)), float(np.nanmean(g))
        if np.array_equal(np.nan_to_num(prev_grid), np.nan_to_num(g)) and cm > 0:
            st, reasons = worst(st, FAULT), reasons + ["frozen frame (identical to previous)"]
        elif cm > q["radar_jump_factor"] * max(pm, 0.05) and cm > 1.0:
            st, reasons = worst(st, SUSPECT), reasons + [f"domain-mean jump x{cm / max(pm, 0.05):.0f}"]
    obs.status, obs.reasons = st, obs.reasons + reasons
    return st


def check_gauges(history, t_now, cfg, radar_at=None, step_min=5.0):
    """QC every gauge from its report history.

    history : {gauge_id: [(t_requested, point_dict or None), ...]} oldest first, one entry per
              polling step (None = no report received).
    radar_at: {gauge_id: [radar rate mm/h at the gauge pixel per step]} aligned with history,
              for contradiction checks (optional).
    Returns {gauge_id: {"status", "reasons", "value_mm"}} for the latest step.
    """
    q = cfg["quality"]
    out = {}
    for gid, hist in history.items():
        reasons, st = [], VALID
        latest = hist[-1][1] if hist else None
        reported = [(t, p) for t, p in hist if p is not None]
        if latest is None:
            if not reported:
                out[gid] = {"status": MISSING, "reasons": ["no reports"], "value_mm": None}
                continue
            age = t_now - reported[-1][1]["t_min"]
            st = STALE if age > q["gauge_stale_min"] else MISSING
            out[gid] = {"status": st, "reasons": [f"last report {age:.0f} min ago"], "value_mm": None}
            continue
        v = latest["rain_mm"]
        if v is None or not np.isfinite(v):
            out[gid] = {"status": MISSING, "reasons": ["empty value"], "value_mm": None}
            continue
        # impossible value
        if v < 0 or v > q["gauge_max_mm_per_5min"]:
            st, reasons = worst(st, FAULT), reasons + [f"impossible value {v} mm"]
        # clock drift: report time vs polling time / cadence
        drift_s = abs(latest["t_min"] - hist[-1][0]) * 60.0
        if drift_s > q["clock_tolerance_s"]:
            st, reasons = worst(st, SUSPECT), reasons + [f"clock drift {drift_s:.0f} s"]
        vals = np.array([p["rain_mm"] if p is not None else np.nan for _, p in hist], float)
        # frozen: identical non-zero value repeated
        n = int(q["gauge_frozen_steps"])
        if len(vals) >= n and v > 0 and np.all(vals[-n:] == v):
            st, reasons = worst(st, FAULT), reasons + [f"frozen at {v} mm for {n} reports"]
        # spike: large isolated value not corroborated by neighbours in time or by radar
        if v >= q["gauge_spike_mm"]:
            prev = vals[-2] if len(vals) >= 2 and np.isfinite(vals[-2]) else 0.0
            rad = (radar_at or {}).get(gid)
            rad_mm = rad[-1] * step_min / 60.0 if rad is not None and len(rad) else None
            ref = max(prev, rad_mm if rad_mm is not None else 0.0, 0.2)
            if v > q["gauge_spike_ratio"] * ref:
                st, reasons = worst(st, SUSPECT), reasons + [f"spike {v} mm (ref {ref:.1f} mm)"]
        # contradiction with radar over the last k steps
        rad = (radar_at or {}).get(gid)
        k = int(q["contradiction_steps"])
        if rad is not None and len(rad) >= k and len(vals) >= k:
            r_mmh = np.asarray(rad[-k:], float)
            g_mmh = vals[-k:] * 60.0 / step_min
            if np.all(np.isfinite(r_mmh)) and np.all(np.isfinite(g_mmh)):
                if np.all(g_mmh == 0) and np.all(r_mmh > q["contradiction_mmh"]):
                    st, reasons = worst(st, SUSPECT), reasons + ["reports 0 while radar shows rain"]
                elif np.all(r_mmh == 0) and np.all(g_mmh > q["contradiction_mmh"]):
                    st, reasons = worst(st, SUSPECT), reasons + ["reports rain while radar shows none"]
        out[gid] = {"status": st, "reasons": reasons, "value_mm": float(v)}
    return out


def summarize(radar_status, radar_reasons, gauge_qc):
    """Compact per-source status table for the health card / forecast JSON."""
    counts = {s: 0 for s in _RANK}
    for g in gauge_qc.values():
        counts[g["status"]] += 1
    return {
        "radar": {"status": radar_status, "reasons": radar_reasons},
        "gauges": {gid: {"status": g["status"], "reasons": g["reasons"]} for gid, g in gauge_qc.items()},
        "gauge_counts": counts,
    }
