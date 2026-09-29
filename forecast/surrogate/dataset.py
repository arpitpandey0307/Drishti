"""Regenerate the surrogate training set with the Task-1 coupled 1D/2D physics.

    python -m forecast.surrogate.dataset --n 260 --ood 30 --workers 12

Each scenario is a 6 h run (72 x 5-min steps) of network variant 0 with one of three rain
families, so the surrogate sees the kind of rainfall the nowcast will feed it:
  storm     regional synthetic storm (squall / convective / stratiform) sampled on campus
  pattern   legacy spec generator (uniform / cells / moving / gradient) at a random start
  pulses    1-3 random pulses with a gentle gradient (ensemble-member-like shapes, abrupt stops)
Blockage 0 / 0.1 / 0.25 / 0.5 in-distribution. OOD: 1.8-2.5x storm intensity and blockage 0.75.
Stored per scenario as float16 on the domain crop: outputs/datasets/v2/<split>/s####.npz.
Splits are by scenario (80 / 10 / 10), never by window.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Pool

import numpy as np

from .features import CROP

T_STEPS = 72
OUT = os.path.join("outputs", "datasets", "v2")
_W = {}


def _init():
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from simulation import config as C
    from simulation.drainage.network import generate
    from simulation.terrain.twin import Twin
    cf = C.load_all()
    tw = Twin(cf["terrain"])
    _W.update(cf=cf, twin=tw, net=generate(tw, cf["drainage"], seed=cf["simulation"]["dataset"]["seed"], variant=0))


def sample_spec(i, ood=False):
    rng = np.random.default_rng((26085, i, int(ood)))
    fam = str(rng.choice(["storm", "pattern", "pulses"], p=[0.45, 0.35, 0.20]))
    if ood:
        fam = "storm"
    spec = {"id": i, "family": fam, "ood": ood,
            "blockage": float(0.75 if ood and rng.random() < 0.5 else rng.choice([0.0, 0.1, 0.25, 0.5]))}
    if fam == "storm":
        spec.update(kind=str(rng.choice(["squall", "convective", "stratiform"], p=[0.45, 0.3, 0.25])),
                    seed=int(rng.integers(1e6)),
                    intensity=float(rng.uniform(1.8, 2.5) if ood else rng.uniform(0.6, 1.6)),
                    arrival_min=float(rng.uniform(40, 220)), miss_km=float(rng.normal(0, 3)))
    elif fam == "pattern":
        spec.update(seed=int(rng.integers(1e6)),
                    temporal=str(rng.choice(["uniform", "peaked", "front_loaded", "back_loaded", "multi_peak"])),
                    spatial=str(rng.choice(["uniform", "gaussian_cell", "moving_cell", "gradient", "multi_cell"])),
                    duration_h=float(rng.uniform(0.5, 3.0)), total_mm=float(rng.uniform(10, 120)),
                    start_step=int(rng.integers(0, 30)))
    else:
        spec.update(pulses=[(int(rng.integers(0, 60)), int(rng.integers(3, 24)), float(rng.uniform(10, 90)))
                            for _ in range(int(rng.integers(1, 4)))],
                    grad=float(rng.uniform(0, 0.5)), ang=float(rng.uniform(0, 2 * np.pi)))
    return spec


def make_rain(spec, twin, rain_cfg):
    """(T_STEPS, ny, nx) rain mm per 5-min step."""
    T = T_STEPS
    if spec["family"] == "storm":
        from forecast.storms import StormEvent
        ev = StormEvent(seed=spec["seed"], kind=spec["kind"], intensity=spec["intensity"],
                        arrival_min=spec["arrival_min"], miss_km=spec["miss_km"])
        return ev.campus_rain(twin, 5.0 * np.arange(1, T + 1))
    R = np.zeros((T,) + twin.dem.shape, np.float32)
    if spec["family"] == "pattern":
        from simulation.rainfall.generator import generate as gen
        g = gen({k: spec[k] for k in ("seed", "temporal", "spatial", "duration_h", "total_mm")},
                twin.X, twin.Y, rain_cfg)["rain_mm_per_step"]
        s = spec["start_step"]
        n = min(g.shape[0], T - s)
        R[s:s + n] = g[:n]
        return R
    field = 1 + spec["grad"] * (twin.X * np.cos(spec["ang"]) + twin.Y * np.sin(spec["ang"])) / 400.0
    for start, dur, peak in spec["pulses"]:
        t = np.arange(dur)
        shape = np.sin(np.pi * (t + 0.5) / dur)
        for k in range(dur):
            if start + k < T:
                R[start + k] += peak * shape[k] * 5 / 60 * field
    return np.maximum(R, 0).astype(np.float32)


def run_one(args):
    spec, split, out_dir = args
    path = os.path.join(out_dir, split, f"s{spec['id']:04d}.npz")
    if os.path.exists(path):          # resumable: keep finished scenarios
        z = np.load(path)
        return {"id": spec["id"], "split": split, "family": spec["family"], "runtime_s": None,
                "rain_mm": None, "max_depth_m": float(z["depth"].max()), "mass_rel_error": None}
    from simulation.hydraulics.simulate import simulate
    tw, cf = _W["twin"], _W["cf"]
    rain = make_rain(spec, tw, cf["rainfall"])
    t = time.time()
    res = simulate(tw, _W["net"], {"seed": int(spec["id"]), "blockage_level": spec["blockage"],
                                   "blockage_mode": "pipe_uniform", "recession_h": 0.0},
                   cf["hydraulics"], cf["rainfall"], rain=rain)
    c = CROP
    tmp = path[:-4] + ".part.npz"
    np.savez_compressed(tmp, rain=rain[:, c[0], c[1]].astype(np.float16),
                        depth=res["depth"][:, c[0], c[1]].astype(np.float16),
                        blockage=np.float32(spec["blockage"]), spec=json.dumps(spec))
    os.replace(tmp, path)
    return {"id": spec["id"], "split": split, "family": spec["family"], "runtime_s": round(time.time() - t, 1),
            "rain_mm": float(rain.sum(0)[tw.in_domain].mean()), "max_depth_m": float(res["max_depth"].max()),
            "mass_rel_error": float(res["mass"]["rel_error"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=260)
    ap.add_argument("--ood", type=int, default=30)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    for s in ("train", "val", "test", "ood"):
        os.makedirs(os.path.join(a.out, s), exist_ok=True)
    jobs = []
    for i in range(a.n):
        split = "train" if i % 10 < 8 else ("val" if i % 10 == 8 else "test")
        jobs.append((sample_spec(i), split, a.out))
    for i in range(a.n, a.n + a.ood):
        jobs.append((sample_spec(i, ood=True), "ood", a.out))
    t = time.time()
    with Pool(a.workers, initializer=_init) as p:
        rows = []
        for k, r in enumerate(p.imap_unordered(run_one, jobs)):
            rows.append(r)
            if k % 20 == 0:
                print(f"{k + 1}/{len(jobs)}  {time.time() - t:.0f}s  last: {r}", flush=True)
    manifest = {"n": a.n, "ood": a.ood, "t_steps": T_STEPS, "crop": [[CROP[0].start, CROP[0].stop],
                [CROP[1].start, CROP[1].stop]], "simulator": "simulation.hydraulics.simulate (Task-1 coupled 1D/2D)",
                "network_variant": 0, "provenance": "synthetic", "scenarios": sorted(rows, key=lambda r: r["id"]),
                "wall_s": round(time.time() - t, 1)}
    json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    print("done", len(rows), "scenarios in", round(time.time() - t), "s")


if __name__ == "__main__":
    main()
