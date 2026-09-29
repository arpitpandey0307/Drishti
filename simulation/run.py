"""Run one coupled 1D/2D scenario from the command line.

  python -m simulation.run --total-mm 80 --duration-h 1 --blockage 0.5
  python -m simulation.run --boundary fixed_stage:2.0 --pump-failed
  python -m simulation.run --baselines          # B1-B5 comparison table

Writes outputs/runs/<name>/summary.json (+ result.npz with --save-grids).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time

import numpy as np

from simulation import config as C
from simulation.drainage.network import generate
from simulation.hydraulics.simulate import simulate
from simulation.terrain.twin import Twin
from simulation.validation.checks import check_mass, check_surface


def _boundary(arg):
    if not arg:
        return None
    kind, _, val = arg.partition(":")
    if kind == "fixed_stage":
        return {"type": "fixed_stage", "stage_m": float(val)}
    if kind == "tidal":
        mean, amp, per = (float(x) for x in val.split(","))
        return {"type": "tidal", "mean_m": mean, "amplitude_m": amp, "period_h": per}
    return {"type": kind}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default=None)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--variant", type=int, default=0, help="synthetic network variant")
    ap.add_argument("--total-mm", type=float, default=60.0)
    ap.add_argument("--duration-h", type=float, default=1.0)
    ap.add_argument("--temporal", default="peaked")
    ap.add_argument("--spatial", default="uniform")
    ap.add_argument("--recession-h", type=float, default=0.5)
    ap.add_argument("--blockage", type=float, default=0.0)
    ap.add_argument("--blockage-mode", default="pipe_uniform")
    ap.add_argument("--boundary", default=None, help="free | fixed_stage:<m> | tidal:<mean>,<amp>,<period_h>")
    ap.add_argument("--pump-failed", action="store_true")
    ap.add_argument("--baselines", action="store_true")
    ap.add_argument("--save-grids", action="store_true")
    a = ap.parse_args()

    cf = C.load_all()
    twin = Twin(cf["terrain"])
    net = generate(twin, cf["drainage"], seed=cf["simulation"]["dataset"]["seed"], variant=a.variant)
    spec = {"seed": a.seed, "temporal": a.temporal, "spatial": a.spatial, "duration_h": a.duration_h,
            "total_mm": a.total_mm, "recession_h": a.recession_h, "network_variant": a.variant,
            "blockage_level": a.blockage, "blockage_mode": a.blockage_mode}
    if a.boundary:
        spec["boundary"] = _boundary(a.boundary)
    if a.pump_failed:
        spec["pump_status"] = {e["id"]: "failed" for e in net["edges"] if e.get("kind") == "pump"}
    name = a.name or hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:10]
    out_dir = os.path.join("outputs", "runs", name)
    os.makedirs(out_dir, exist_ok=True)

    if a.baselines:
        from simulation.baselines import run_all
        scores, _ = run_all(twin, net, spec, cf["hydraulics"], cf["rainfall"])
        print(f"{'':4s} {'CSI':>6s} {'IoU':>6s} {'prec':>6s} {'recall':>6s} {'MAE_m':>7s}  (vs full model B5)")
        for k, s in scores.items():
            print(f"{k:4s} {s['csi']:6.3f} {s['iou']:6.3f} {s['precision']:6.3f} {s['recall']:6.3f} {s['depth_mae_m']:7.3f}")
        json.dump(scores, open(os.path.join(out_dir, "baselines.json"), "w"), indent=1)
        return

    t0 = time.time()
    res = simulate(twin, net, spec, cf["hydraulics"], cf["rainfall"])
    err, ok = check_mass(res, tol=1e-4)
    summary = {
        "spec": spec, "runtime_s": round(time.time() - t0, 2), "terrain": twin.meta,
        "network": {"nodes": len(net["nodes"]), "links": len(net["edges"]), "provenance": "synthetic"},
        "mass": res["mass"], "mass_check_ok": bool(ok), "surface_errors": check_surface(res, twin),
        "max_depth_m": float(res["max_depth"].max()),
        "flooded_area_m2": float((res["max_depth"] >= 0.05)[twin.in_domain].sum() * twin.dx ** 2),
        "surcharged_nodes": [int(k) for k in np.where(res["surcharge_time_s"] > 0)[0]],
        "boundaries": res["boundaries"],
        "provenance": {"code": "simulation/hydraulics/simulate.py",
                       "simulator_version": "2.0-coupled-1d2d", "config": cf},
    }
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w"), indent=1, default=float)
    if a.save_grids:
        np.savez_compressed(os.path.join(out_dir, "result.npz"),
                            **{k: v for k, v in res.items() if isinstance(v, np.ndarray)})
    print(json.dumps({k: summary[k] for k in ("runtime_s", "max_depth_m", "flooded_area_m2",
                                               "surcharged_nodes", "mass_check_ok")}, indent=1))
    print("mass rel error:", f"{res['mass']['rel_error']:.2e}", "->", out_dir)


if __name__ == "__main__":
    main()
