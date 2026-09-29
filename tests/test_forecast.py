"""Task 2: observation adapters, QC, nowcast, probabilistic forecast, degradation (AC-01/07/08/12/19)."""
import os

import numpy as np
import pytest

from simulation import config as C
from forecast.grid import RegionalGrid
from forecast.motion import dense_motion, to_log, trajectories, warp
from forecast.obs import (GaugeCSVSource, MosdacDWRSource, RadarArchiveReplay, SyntheticGauges,
                          SyntheticNWP, SyntheticRadar)
from forecast.probabilistic import flood_stats, road_stats
from forecast.quality import FAULT, MISSING, STALE, SUSPECT, VALID, check_gauges, check_radar_frame
from forecast.steps import Climatology, StepsNowcaster, gauge_field, mean_field_bias
from forecast.storms import StormEvent

CFG = C.load("forecast")
GRID = RegionalGrid(CFG)
EV = StormEvent(seed=3, kind="squall")


def test_storm_is_deterministic_and_reaches_site():
    a, b = StormEvent(seed=3, kind="squall"), StormEvent(seed=3, kind="squall")
    assert np.array_equal(a.rate(GRID, 120), b.rate(GRID, 120))
    site = [float(EV.rate_at(0, 0, t)) for t in range(0, 300, 5)]
    assert max(site) > 20 and site[0] == 0


def test_adapters(tmp_path):
    r = SyntheticRadar(EV, GRID, outages=[(50, 60)])
    assert r.fetch(40).grid.shape == GRID.shape and r.fetch(40).provenance == "synthetic"
    assert r.fetch(55).status == MISSING
    # archive replay round trip, 30-min cadence -> the frame at t=45 is the t=30 one
    p = tmp_path / "arch.npz"
    RadarArchiveReplay.save(p, r, [30, 60, 90], product="imerg_replay", provenance="synthetic")
    rep = RadarArchiveReplay(p)
    o = rep.fetch(45)
    assert o.obs_time_min == 30 and rep.name == "imerg_replay"
    assert rep.fetch(10).status == MISSING
    # gauge CSV
    csv = tmp_path / "g.csv"
    csv.write_text("time_min,station_id,x_km,y_km,rain_mm\n5,A,0,0,1.2\n10,A,0,0,2.4\n10,B,3,3,0.4\n")
    g = GaugeCSVSource(csv)
    assert {p["id"] for p in g.fetch(10).points} == {"A", "B"} and len(g.fetch(5).points) == 1
    # MOSDAC stub degrades honestly
    assert MosdacDWRSource().fetch(10).status == MISSING
    assert SyntheticNWP(EV).forecast(60, [30, 60], GRID).shape == (2,) + GRID.shape


def _gauge_hist(src, times):
    hist = {}
    for k, t in enumerate(times):
        pts = {p["id"]: p for p in src.fetch(t).points}
        for gid in set(hist) | set(pts):
            hist.setdefault(gid, [(tp, None) for tp in times[:k]]).append((t, pts.get(gid)))
    return hist


def test_quality_engine_detects_every_fault_class():
    times = list(np.arange(5, 125, 5.0))
    faults = {"G1": ("frozen", 60), "G2": ("negative", 110), "G3": ("offline", 60),
              "G4": ("drift", 100, 300), "G5": ("stuck_zero", 60), "G6": ("spike", 120)}
    src = SyntheticGauges(EV, faults=faults)
    hist = _gauge_hist(src, times)
    radar_at = {gid: [float(EV.rate_at(x, y, t)) for t in times] for gid, x, y in src.st}
    radar_at["G5"] = [30.0] * len(times)           # radar clearly raining over the stuck gauge
    q = check_gauges(hist, times[-1], CFG, radar_at)
    assert q["G1"]["status"] == FAULT and "frozen" in q["G1"]["reasons"][0]
    assert q["G2"]["status"] == FAULT
    assert q["G3"]["status"] == STALE
    assert q["G4"]["status"] == SUSPECT and "clock drift" in q["G4"]["reasons"][0]
    assert q["G5"]["status"] == SUSPECT and "radar" in q["G5"]["reasons"][0]
    assert q["G6"]["status"] == SUSPECT and "spike" in q["G6"]["reasons"][0]
    assert q["G0-KIET"]["status"] == VALID
    # radar frames
    r = SyntheticRadar(EV, GRID, faults={100: "nan", 110: "frozen", 115: "spike"})
    prev = r.fetch(95).grid
    assert check_radar_frame(r.fetch(100), prev, 100, CFG) == FAULT
    o = r.fetch(110)
    assert check_radar_frame(o, r._last, 110, CFG) == FAULT
    assert check_radar_frame(r.fetch(115), r.fetch(112.5).grid, 115, CFG) in (FAULT, SUSPECT)
    late = r.fetch(90); late.obs_time_min = 60
    assert check_radar_frame(late, None, 90, CFG) == STALE


def test_optical_flow_recovers_known_motion():
    rng = np.random.default_rng(0)
    from scipy.ndimage import gaussian_filter
    f = np.exp(gaussian_filter(rng.normal(size=GRID.shape), 4) * 8); f[f < 1] = 0
    V = np.stack([np.full(GRID.shape, 1.5), np.full(GRID.shape, -2.2)])
    frames = [f, warp(f, V), warp(warp(f, V), V)]
    Ve = dense_motion([to_log(x)[0] for x in frames])
    assert abs(Ve[0][40:150, 40:150].mean() - 1.5) < 0.15
    assert abs(Ve[1][40:150, 40:150].mean() + 2.2) < 0.15
    assert np.allclose(trajectories(Ve, 2)[1][:, 96, 96], 2 * Ve[:, 96, 96], atol=0.3)


def test_gauge_bias_correction_recovers_radar_bias():
    radar = SyntheticRadar(EV, GRID, bias=0.6, noise_sigma=0.1)
    gauges = SyntheticGauges(EV, noise=0.02)
    r, g = [], []
    for t in np.arange(100, 160, 5.0):
        o = radar.fetch(t)
        for p in gauges.fetch(t).points:
            i, j = GRID.nearest_ij(p["x_km"], p["y_km"])
            r.append(o.grid[i, j]); g.append(p["rain_mm"])
    B, n, ok = mean_field_bias(r, g, 5.0, CFG)
    assert ok and n >= 4 and 1.3 < B < 2.1          # true correction 1/0.6 = 1.67
    f = gauge_field(gauges.fetch(130).points, GRID)
    assert np.isnan(f[0, 0]) and np.isfinite(f[96, 96])


def test_nowcast_ensemble_properties():
    radar = SyntheticRadar(EV, GRID)
    frames = [radar.fetch(t).grid for t in (80, 85, 90)]
    nc = StepsNowcaster(CFG, GRID)
    res = nc.run(frames, 36, members=6, seed=1, nwp=SyntheticNWP(EV).forecast(90, np.arange(5, 185, 5), GRID),
                 clim=Climatology(CFG))
    m = res["members"]
    assert m.shape == (6, 36) + GRID.shape and np.all(m >= 0)
    assert res["diag"]["guidance"] == "nwp"
    spread = [m[:, k].std(0).mean() for k in (0, 11)]
    assert spread[1] > spread[0]                          # uncertainty grows with lead
    tr = EV.rate(GRID, 120)
    c = lambda f: ((f > 1) & (tr > 1)).sum() / max(((f > 1) | (tr > 1)).sum(), 1)
    assert c(np.median(m[:, 5], 0)) > c(frames[-1])      # beats persistence at +30 min
    assert nc.blend_weight(30) == 1.0 and nc.blend_weight(180) < 0.5 and nc.blend_weight(60) >= 0.8
    assert nc.blend_weight(60, degraded=True) < nc.blend_weight(60)


def test_flood_stats_consistency():
    rng = np.random.default_rng(0)
    D = np.maximum(rng.normal(0.1, 0.08, (20, 5, 8, 8)), 0).astype(np.float32)
    D[:, :, 0, 0] = 0.0
    D[:, :2, 1, 1] = 0.0
    D[:, 2:, 1, 1] = 0.5
    st = flood_stats(D, [15, 30, 60, 120, 180])
    assert np.all(st["p10"] <= st["p50"] + 1e-6) and np.all(st["p50"] <= st["p90"] + 1e-6)
    assert st["exceed"][0.1][:, 0, 0].max() == 0 and st["exceed"][0.3][2:, 1, 1].min() == 1
    assert st["time_to_threshold_min"][1, 1] == 60 and st["p_reach_flood_depth"][1, 1] == 1
    assert np.isnan(st["time_to_threshold_min"][0, 0])
    segs = [{"id": "R-1", "name": "x", "highway": "service", "cells": (np.array([0, 1]), np.array([0, 1]))}]
    rs = road_stats(D, [15, 30, 60, 120, 180], segs)
    assert rs[0]["p_exceed"]["30cm"] == 1.0 and rs[0]["time_to_threshold_min"] == 60


MODEL = CFG["surrogate"]["model"]


@pytest.mark.skipif(not os.path.exists(MODEL), reason="surrogate not trained")
def test_run_forecast_end_to_end_and_degraded(tmp_path):
    import time
    from forecast.run import ForecastSources, context, run_forecast
    ctx = context(CFG)
    src = ForecastSources(radar=SyntheticRadar(EV, GRID), gauges=SyntheticGauges(EV), nwp=SyntheticNWP(EV), truth=EV)
    t = time.time()
    res = run_forecast(90, src, members=10, seed=1, ctx=ctx, out_dir=str(tmp_path / "ok"))
    assert time.time() - t < 60                                        # < 60 s per cycle
    f = res["forecast"]
    assert f["health"]["status"] == "OPERATIONAL" and f["health"]["rain_source_mode"] == "radar"   # AC-01
    assert f["flood"]["lead_min"][-1] == 180 and res["depth_members"].shape[:2] == (10, 14)           # AC-07
    assert res["depth_members"][:, -1].std(0).max() > 0                                              # AC-08
    assert f["flood"]["roads"] and "p_exceed" in f["flood"]["roads"][0]
    assert os.path.exists(tmp_path / "ok" / "exceedance_10cm.png")
    # radar outage -> gauge-only, flagged DEGRADED with reasons (AC-19)
    src2 = ForecastSources(radar=SyntheticRadar(EV, GRID, outages=[(70, 999)]), gauges=SyntheticGauges(EV),
                           nwp=SyntheticNWP(EV), truth=EV)
    r2 = run_forecast(90, src2, members=6, seed=1, ctx=ctx, refine=False, save=False)["forecast"]
    assert r2["health"]["status"] == "DEGRADED" and r2["health"]["rain_source_mode"] == "gauge"
    assert any("radar" in x for x in r2["health"]["reasons"]) and r2["health"]["uncertainty_inflation"] > 1
    # nothing usable -> climatology, still DEGRADED, never a normal-looking forecast
    src3 = ForecastSources(radar=MosdacDWRSource(), gauges=None, nwp=None)
    r3 = run_forecast(30, src3, members=4, seed=1, ctx=ctx, refine=False, save=False)["forecast"]
    assert r3["health"]["status"] == "DEGRADED" and r3["health"]["rain_source_mode"] == "climatology"
