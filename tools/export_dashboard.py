"""Export the operator dashboard data bundle (dashboard/data/*.json) from real model runs.

    python -m tools.export_dashboard            # ~2-3 min on a laptop

Everything the dashboard shows comes from this bundle:
  - Task 1 physics: baseline storm run (depth frames, drainage node states), baselines B1-B5
  - Task 2 forecast: run_forecast at t0 (radar OK) and a degraded cycle (radar outage + faulty gauge)
  - Task 3 twin experiment: hidden-blockage truth, virtual sensors with noise + one faulty
    sensor, open loop vs per-sensor Kalman-assimilated node levels, residual anomaly ranking
  - Task 4 what-if / action runs: rain +20 %, 50 % capacity loss, pump failure, downstream
    +0.5 m, drain clearance and pump actions — each a full coupled-physics run
All inputs are synthetic (SRS §11 Level 1) and labelled as such in the bundle.
"""
from __future__ import annotations

import base64
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from forecast.surrogate.features import CROP

OUT = os.path.join("dashboard", "data")
EVENT = dict(seed=3, kind="squall")
T0 = 115.0
CYCLES = [90.0, 115.0, 140.0]      # forecast issue times replayed in the dashboard
T_END = 300.0                       # simulate 0-300 min
_W = {}


def b64(a, scale, dtype=np.uint8):
    """Quantise array (clip to dtype range) and base64 it."""
    info = np.iinfo(dtype)
    q = np.clip(np.nan_to_num(np.asarray(a, float), nan=info.max) * scale, 0, info.max).round().astype(dtype)
    return base64.b64encode(q.tobytes()).decode()


def crop(a):
    return np.asarray(a)[..., CROP[0], CROP[1]]


def _init():
    from simulation import config as C
    from simulation.drainage.network import generate
    from simulation.terrain.twin import Twin
    cf = C.load_all()
    tw = Twin(cf["terrain"])
    _W.update(cf=cf, twin=tw, net=generate(tw, cf["drainage"], seed=cf["simulation"]["dataset"]["seed"], variant=0))


def _run(job):
    name, rain, spec, comp = job
    from simulation.hydraulics.simulate import simulate
    t = time.time()
    r = simulate(_W["twin"], _W["net"], spec, _W["cf"]["hydraulics"], _W["cf"]["rainfall"], rain=rain,
                 components=comp)
    keep = {k: r[k] for k in ("depth", "max_depth", "node_depth", "node_head", "pipe_flow", "surcharge_time_s",
                              "node_overflow_m3", "time_to_flood_min", "pipe_capacity")}
    keep["mass"] = r["mass"]
    keep["runtime_s"] = round(time.time() - t, 1)
    return name, keep


def main():
    t_all = time.time()
    os.makedirs(OUT, exist_ok=True)
    from simulation import config as C
    from forecast.run import ForecastSources, context, run_forecast
    from forecast.obs import SyntheticGauges, SyntheticNWP, SyntheticRadar
    from forecast.storms import StormEvent
    from forecast.surrogate.features import LEAD_MIN

    ctx = context()
    twin, net, grid = ctx.twin, ctx.net, ctx.grid
    ev = StormEvent(**EVENT)
    step = 5.0
    times = step * np.arange(1, int(T_END / step) + 1)
    rain = ev.campus_rain(twin, times, step)
    pump_ids = [e["id"] for e in net["edges"] if e.get("kind") == "pump"]
    # hidden truth for the twin experiment: two trunk pipes (largest upstream catchment) 85 % blocked
    pipes = [e for e in net["edges"] if e.get("kind") == "pipe" and net["nodes"][e["v"]]["kind"] != "outfall"]
    pipes.sort(key=lambda e: -net["nodes"][e["u"]]["catchment_area_m2"])
    hidden = {int(pipes[1]["id"]): 0.85, int(pipes[4]["id"]): 0.85}
    base = {"seed": 1, "blockage_level": 0.0, "blockage_mode": "pipe_uniform"}
    full = {"infiltration": True, "drainage": True, "surface_routing": True}
    jobs = [
        ("baseline", rain, base, full),
        ("rain_plus20", rain * 1.2, base, full),
        ("capacity_minus50", rain, dict(base, blockage_level=0.5), full),
        ("pump_failure", rain, dict(base, pump_status={pid: "failed" for pid in pump_ids}), full),
        ("downstream_plus20", rain, dict(base, boundary={"type": "fixed_stage", "stage_m": 2.0}), full),
        ("state_blocked40", rain, dict(base, blockage_level=0.4), full),
        ("act_pump_on", rain, dict(base, blockage_level=0.4, pump_status={pid: "on" for pid in pump_ids}), full),
        ("act_clear", rain, dict(base, blockage_level=0.0), full),
        ("act_clear_pump", rain, dict(base, blockage_level=0.0, pump_status={pid: "on" for pid in pump_ids}), full),
        ("twin_truth", rain, dict(base, seed=11, blockage_edges=hidden), full),
        ("B2", rain, base, {"infiltration": False, "drainage": False, "surface_routing": True}),
        ("B3", rain, base, {"infiltration": True, "drainage": False, "surface_routing": True}),
        ("B4", rain, base, {"infiltration": True, "drainage": True, "surface_routing": False}),
    ]
    print("physics runs:", len(jobs), flush=True)
    with ProcessPoolExecutor(max_workers=6, initializer=_init) as ex:
        runs = dict(ex.map(_run, jobs))
    print("physics done", round(time.time() - t_all), "s", flush=True)

    # ------------------------------------------------------------------ forecast cycles (Task 2)
    src = ForecastSources(radar=SyntheticRadar(ev, grid), gauges=SyntheticGauges(ev), nwp=SyntheticNWP(ev), truth=ev)
    src_d = ForecastSources(radar=SyntheticRadar(ev, grid, outages=[(80, 999)]),
                            gauges=SyntheticGauges(ev, faults={"G3": ("frozen", 60)}), nwp=SyntheticNWP(ev), truth=ev)
    cycles = {}
    for t0 in CYCLES:
        cycles[t0] = (run_forecast(t0, src, members=20, seed=3, ctx=ctx, save=False),
                      run_forecast(t0, src_d, members=20, seed=3, ctx=ctx, save=False, refine=False))
        print("forecast cycle", t0, "done", round(time.time() - t_all), "s", flush=True)
    fc = cycles[T0][0]
    wet = ctx.wet
    k0 = int(T0 / step) - 1
    # ------------------------------------------------------------------ grid.json
    i0, i1, j0, j1 = CROP[0].start, CROP[0].stop, CROP[1].start, CROP[1].stop
    half = twin.dx / 2
    lat_n = float(twin.lat[i0, 0] + half / 111320.0); lat_s = float(twin.lat[i1 - 1, 0] - half / 111320.0)
    mlon = twin.m_per_deg_lon
    lon_w = float(twin.lon[0, j0] - half / mlon); lon_e = float(twin.lon[0, j1 - 1] + half / mlon)
    dem = crop(twin.dem)
    dmin = float(dem[crop(twin.in_domain)].min())
    gridj = {
        "ny": i1 - i0, "nx": j1 - j0, "dx_m": twin.dx, "crop_offset": [i0, j0], "bounds": [[lat_s, lon_w], [lat_n, lon_e]],
        "domain": b64(crop(twin.in_domain), 1), "building": b64(crop(twin.is_building), 1),
        "road": b64(crop(twin.is_road), 1), "low_points": b64(crop(twin.low_points), 1),
        "dem_min": dmin, "dem": b64(crop(twin.dem) - dmin, 20),            # 5 cm steps
        "imperv": b64(crop(twin.imperv), 100), "accum_log": b64(np.log1p(crop(twin.accum)), 20),
        "terrain": twin.meta,
    }
    json.dump(gridj, open(os.path.join(OUT, "grid.json"), "w"), default=_j)

    # ------------------------------------------------------------------ network + live (Task 1 physics)
    B = runs["baseline"]
    nodes = [{k: n[k] for k in ("id", "kind", "lat", "lon", "rim_m", "invert_m", "depth_m", "inlet_capacity_m3s",
                               "catchment_area_m2", "confidence")} for n in net["nodes"]]
    edges = [{k: e.get(k) for k in ("id", "u", "v", "kind", "length_m", "diameter_m", "capacity_m3s", "confidence")}
             for e in net["edges"]]
    live = {
        "times_min": times.tolist(), "t0_index": k0,
        "rain_mmh": [round(float(r[wet].mean() * 12), 2) for r in rain],
        "depth_cm": [b64(crop(d), 100) for d in B["depth"]],                  # 1 cm steps (uint8, <=2.55 m)
        "node_fill": np.clip(B["node_depth"] / np.array([max(n["depth_m"], 0.1) for n in net["nodes"]]), 0, 2)
        .round(3).tolist(),                                                  # (T, nodes) fraction of pipe depth
        "pipe_util": np.clip(np.abs(B["pipe_flow"]) / np.maximum(B["pipe_capacity"], 1e-6), 0, 3).round(3).tolist(),
        "surcharge_min": (B["surcharge_time_s"] / 60).round(1).tolist(),
        "overflow_m3": B["node_overflow_m3"].sum(0).round(2).tolist(),
        "mass_rel_error": float(B["mass"]["rel_error"]), "runtime_s": B["runtime_s"],
        "event": ev.describe(),
    }
    json.dump({"nodes": nodes, "edges": edges, "live": live, "provenance": "synthetic network (verified=false)"},
              open(os.path.join(OUT, "network.json"), "w"), default=_j)

    # ------------------------------------------------------------------ forecast (Task 2)
    def pack_fc(res):
        st, f = res["stats"], res["forecast"]
        D = res["depth_members"]
        fut = res["campus_rain_future"]
        cum = fut.cumsum(1)[:, :, wet].mean(-1)                       # (M, 36)
        Rm = res["rain_members"]
        rq = np.quantile(Rm[:, [2, 5, 11, 23, 35]], [0.1, 0.5, 0.9], axis=1)   # (3, 5, ny, nx)
        sub = lambda a: a[..., 48:144:2, 48:144:2]                    # 96 km window, 2 km pixels
        return {
            "forecast": f,
            "lead_min": LEAD_MIN,
            "expected_cm": [b64(crop(x), 100) for x in st["expected"]],
            "p10_cm": [b64(crop(x), 100) for x in st["p10"]],
            "p50_cm": [b64(crop(x), 100) for x in st["p50"]],
            "p90_cm": [b64(crop(x), 100) for x in st["p90"]],
            "exceed": {str(int(t * 100)): [b64(crop(x), 100) for x in st["exceed"][t]] for t in st["exceed"]},
            "peak_cm": b64(crop(st["peak_expected"]), 100), "peak_p90_cm": b64(crop(st["peak_p90"]), 100),
            "peak_time_min": b64(crop(st["peak_time_min"]), 1),
            "ttt_min": b64(crop(st["time_to_threshold_min"]), 1),
            "p_reach": b64(crop(st["p_reach_flood_depth"]), 100),
            "duration_min": b64(crop(st["duration_expected_min"]), 1),
            "depth_now_cm": b64(crop(res["maps"]["depth_now"]), 100),
            "members_domain_cm": [[round(float(D[m, l][wet].mean() * 100), 2) for l in range(D.shape[1])]
                                  for m in range(D.shape[0])],
            "member_cell_cm": None,
            "rain_cum_mm": cum.round(2).tolist(),
            "rain_hist_mmh": [round(float(r[wet].mean() * 12), 2) for r in res["campus_rain_hist"]],
            "radar": {"leads": [15, 30, 60, 120, 180], "n": 48, "km": 2,
                      "p50": [b64(sub(x), 2) for x in rq[1]], "p90": [b64(sub(x), 2) for x in rq[2]]},
        }

    for t0, (fo, fdg) in cycles.items():
        fcj = {"t0_min": t0, "ok": pack_fc(fo), "degraded": pack_fc(fdg)}
        # per-member cell depths for the location chart (uint8 cm on crop)
        fcj["ok"]["members_cm"] = [[b64(crop(fo["depth_members"][m, l]), 100) for l in range(len(LEAD_MIN))]
                                   for m in range(0, 20, 4)]
        json.dump(fcj, open(os.path.join(OUT, f"forecast_{int(t0)}.json"), "w"), default=_j)
    json.dump({"cycles": [int(t) for t in CYCLES], "default": int(T0)}, open(os.path.join(OUT, "forecast_index.json"), "w"))
    if os.path.exists(os.path.join(OUT, "forecast.json")):
        os.remove(os.path.join(OUT, "forecast.json"))

    # ------------------------------------------------------------------ twin experiment (Task 3)
    truth = runs["twin_truth"]
    ol = runs["baseline"]
    rng = np.random.default_rng(5)
    blocked_edges = sorted(hidden)
    # sensors: most informative manholes/junctions + nodes just upstream of blocked pipes
    cand = [n["id"] for n in net["nodes"] if n["kind"] in ("junction", "inlet", "storage")]
    up = [net["edges"][e]["u"] for e in blocked_edges]
    diff = np.abs(truth["node_depth"] - ol["node_depth"]).max(0)
    sensors = list(dict.fromkeys([n for n in sorted(cand, key=lambda n: -diff[n])[:4]] +
                                 sorted(cand, key=lambda n: -ol["node_depth"][:, n].max())[:6]))[:9]
    faulty = sensors[-1]
    T = len(times)
    sig = 0.03
    obs = truth["node_depth"][:, sensors] + rng.normal(0, sig, (T, len(sensors)))
    obs[:, -1] = np.where(np.arange(T) > 30, obs[30, -1], obs[:, -1])          # stuck sensor from t=155
    obs = np.maximum(obs, 0)
    # per-sensor Kalman filter on the open-loop trajectory (bias state), fault isolation by innovation
    xa = np.zeros((T, len(sensors))); bias = np.zeros(len(sensors)); P = np.full(len(sensors), 0.05)
    trust = np.ones(len(sensors)); innov_hist = []
    q, R = 0.002, sig ** 2
    for k in range(T):
        xf = ol["node_depth"][k, sensors] + bias
        P = P + q
        inn = obs[k] - xf
        # fault check: stuck value while the model moves -> degrade trust
        if k > 3:
            flat = np.abs(obs[k] - obs[k - 3]) < 1e-9
            moving = np.abs(ol["node_depth"][k, sensors] - ol["node_depth"][k - 3, sensors]) > 0.02
            trust = np.where(flat & moving, np.maximum(trust - 0.25, 0), np.minimum(trust + 0.02, 1))
        K = P / (P + R / np.maximum(trust, 1e-3))
        bias = bias + K * inn * (trust > 0.3)
        P = (1 - K) * P
        xa[k] = np.maximum(ol["node_depth"][k, sensors] + bias, 0)
        innov_hist.append(inn)
    innov = np.array(innov_hist)
    rmse = lambda a: float(np.sqrt(((a - truth["node_depth"][:, sensors][:, :-1]) ** 2).mean()))
    anomalies = []
    for s_i, n in enumerate(sensors):
        r = (obs - ol["node_depth"][:, sensors])[20:, s_i]          # open-loop residual (expected vs observed)
        z = float(r.mean() / (r.std() + sig))
        node = net["nodes"][n]
        down = [e for e in net["edges"] if e["u"] == n]
        if n == faulty:
            anomalies.append({"asset": f"S-{n}", "node": n, "cause": "sensor anomaly (stuck value)", "likelihood": 0.92,
                              "evidence": "reading constant for 20+ min while modelled level changes; trust score "
                                          f"{trust[s_i]:.2f}", "action": "inspect / recalibrate water-level sensor",
                              "severity": "medium"})
        elif (z > 1.0 or r.mean() > 0.15) and down:
            e = down[0]
            est = float(np.clip(1 - (ol["node_depth"][:, n].max() + 1e-3) / (truth["node_depth"][:, n].max() + 1e-3) + 0.5,
                                0.1, 0.95))
            anomalies.append({"asset": f"P-{e['id']}", "node": n, "cause": "pipe obstruction / inlet blockage",
                              "likelihood": round(float(min(0.95, 0.5 + 0.15 * z)), 2),
                              "evidence": f"observed level {r.mean() * 100:+.0f} cm above expected (z={z:.1f}) under "
                                          "the same rainfall and free outfall",
                              "estimated_blockage": round(est, 2),
                              "action": f"CCTV / rodding of pipe P-{e['id']} downstream of node N-{n}",
                              "severity": "high" if z > 2.5 else "medium", "true_blocked": bool(e["id"] in blocked_edges)})
        elif z < -1.5:
            anomalies.append({"asset": f"N-{n}", "node": n, "cause": "parameter error (lower level than modelled)",
                              "likelihood": 0.5, "evidence": f"level {r.mean() * 100:+.0f} cm vs expected",
                              "action": "review inlet capacity / roughness", "severity": "low"})
    anomalies.sort(key=lambda a: -a["likelihood"])
    twinj = {
        "sensors": [{"id": f"S-{n}", "node": n, "lat": net["nodes"][n]["lat"], "lon": net["nodes"][n]["lon"],
                     "trust": round(float(trust[s]), 2), "status": "FAULT" if trust[s] < 0.3 else "VALID"}
                    for s, n in enumerate(sensors)],
        "times_min": times.tolist(),
        "truth": truth["node_depth"][:, sensors].round(3).T.tolist(),
        "open_loop": ol["node_depth"][:, sensors].round(3).T.tolist(),
        "observed": obs.round(3).T.tolist(), "assimilated": xa.round(3).T.tolist(),
        "rmse": {"open_loop_m": round(rmse(ol["node_depth"][:, sensors][:, :-1]), 4),
                 "assimilated_m": round(rmse(xa[:, :-1]), 4)},
        "blocked_edges_truth": blocked_edges, "anomalies": anomalies,
        "surface": {"truth_flooded_m2": float((truth["max_depth"] >= 0.1)[wet].sum() * 25),
                    "open_loop_flooded_m2": float((ol["max_depth"] >= 0.1)[wet].sum() * 25)},
        "method": "per-sensor Kalman bias update on the open-loop physics trajectory; innovation-based fault "
                  "isolation; residual z-score anomaly ranking",
        "provenance": "synthetic twin experiment (hidden blockage truth, virtual sensors)",
    }
    json.dump(twinj, open(os.path.join(OUT, "twin.json"), "w"), default=_j)

    # ------------------------------------------------------------------ scenarios + actions (Task 4)
    def summ(r):
        md = r["max_depth"]
        return {"max_depth_cm": b64(crop(md), 100), "flooded_m2": float((md >= 0.1)[wet].sum() * 25),
                "severe_m2": float((md >= 0.3)[wet].sum() * 25), "peak_depth_m": round(float(md.max()), 3),
                "surcharged_nodes": int((r["surcharge_time_s"] > 0).sum()),
                "overflow_m3": round(float(r["node_overflow_m3"].sum()), 1),
                "depth_series_cm": [b64(crop(d), 100) for d in r["depth"][::3]],
                "mass_rel_error": float(r["mass"]["rel_error"]), "runtime_s": r["runtime_s"]}

    scen = {k: summ(runs[k]) for k in ("baseline", "rain_plus20", "capacity_minus50", "pump_failure",
                                       "downstream_plus20", "state_blocked40", "act_pump_on", "act_clear",
                                       "act_clear_pump")}
    # baselines table (Task 1 SRS §7) scored against B5
    from simulation.baselines import flood_scores
    mask = twin.in_domain & ~twin.is_building
    ref = runs["baseline"]["max_depth"]
    peak = float(rain.max(axis=0)[wet].max() * 12)
    b1 = np.where(twin.in_domain, 0.05 if peak > 30 else 0.0, 0.0)
    bench = {"B1": flood_scores(b1, ref, mask)}
    for k in ("B2", "B3", "B4"):
        bench[k] = flood_scores(runs[k]["max_depth"], ref, mask)
    bench["B5"] = flood_scores(ref, ref, mask)
    json.dump({"scenarios": scen, "baselines": bench, "series_every_min": 15,
               "provenance": "modelled (Task-1 coupled physics, synthetic storm)"},
              open(os.path.join(OUT, "scenarios.json"), "w"), default=_j)

    # ------------------------------------------------------------------ verification (Task 2 / 5)
    from forecast.verify import verify
    by_cycle = {int(t0): verify(t0, src, fo, ctx) for t0, (fo, _) in cycles.items()}
    v = by_cycle[int(T0)]
    meta = json.load(open("forecast/models/surrogate_v2.json"))
    json.dump({"verification": v, "by_cycle": by_cycle, "surrogate": {"metrics": meta["metrics"], "arch": meta["arch"],
                                                "params": meta["params"], "training": {k: meta["training"][k]
                                                                                       for k in ("epochs", "train_windows", "wall_s")}},
               "generated_s": round(time.time() - t_all, 1)},
              open(os.path.join(OUT, "validation.json"), "w"), default=_j)
    print("bundle written to", OUT, "in", round(time.time() - t_all), "s")
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


def _j(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


if __name__ == "__main__":
    main()
