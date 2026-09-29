"""Adapter: simulation H5 output -> visualization bundles.

Reads outputs/datasets/kiet_flood_{split}.h5 + kiet_networks_{split}.json,
writes outputs/viz/<scenario_id>/meta.json + frame_*.json.
Quantization is documented in meta; validation script checks error bounds.
Does NOT touch the physics engine.
"""
from __future__ import annotations
import os, json, base64
import numpy as np
import h5py

NODE_MAXDEPTH_M = 1.5  # must match config/drainage.yaml nodes.depth_m
FLOOD_THRESH_M = 0.05


def _qi(x, scale):
    return np.round(np.asarray(x) * scale).astype(np.int32)


D16 = np.int16
D32 = np.int32

def _b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def _q16(x, scale):
    v = np.round(np.asarray(x) * scale)
    assert np.all((v >= -32000) & (v <= 32000)), "int16 overflow"
    return v.astype(D16)


def export_split(split="test", h5_path=None, net_path=None, out_root="outputs/viz", max_scenarios=None):
    if split == "v1demo":
        h5_path = "outputs/datasets/v1/kiet_flood_test.h5"
        net_path = "outputs/datasets/v1/kiet_networks_v1.json"
        max_scenarios = 2 if max_scenarios is None else max_scenarios
    h5_path = h5_path or f"outputs/datasets/kiet_flood_{split}.h5"
    net_path = net_path or f"outputs/datasets/kiet_networks_{split}.json"
    f = h5py.File(h5_path, "r")
    nets = json.load(open(net_path))
    dem = f["dem"][:]
    ny, nx = dem.shape
    in_dom = f["in_domain"][:].astype(bool)
    is_road = f["is_road"][:].astype(bool)
    is_bld = f["is_building"][:].astype(bool)
    # landcover class: 0 outside, 1 open, 2 road, 3 building
    lc = np.zeros((ny, nx), np.uint8)
    lc[in_dom & ~(is_road | is_bld)] = 1
    lc[is_road] = 2
    lc[is_bld] = 3
    # low points: top-decile accumulation proxy via max_depth? No — recompute cheap:
    # use deepest-ponding cells of the highest-rain scenario as proxy? NO faking.
    # Instead: rank by DEM (lowest 10% in-domain non-building cells).
    cand = np.where(in_dom & ~is_bld, dem, np.inf)
    thr = np.percentile(cand[np.isfinite(cand)], 10)
    low = (cand <= thr)
    lats = (f["Y"][:] / 111320.0 + 28.7523).tolist() if "Y" in f else None
    if split == "v1demo":
        cands = [k for k in f.keys() if k.startswith("test_v1_")]
        scored = []
        for sid in cands:
            spec = json.loads(f[sid].attrs["spec"])
            scored.append((spec["total_mm"], spec.get("blockage_level", 0), sid))
        scored.sort()
        heavy = scored[-1][2]  # max rain
        mid = next((s for _, b, s in reversed(scored) if b >= 0.5 and s != heavy), scored[len(scored) // 2][2])
        sids, prefix = [heavy, mid][: (max_scenarios or 2)], "v1demo"
    else:
        sids = [k for k in f.keys() if k.startswith("scenario")]
        prefix = split
    index = []
    try:
        old = json.load(open(os.path.join(out_root, "index.json")))
        index = [e for e in old if e.get("dir") not in {f"{prefix}_{s}" for s in sids}]
    except (FileNotFoundError, json.JSONDecodeError):
        index = []
    for sid in sorted(sids):
        g = f[sid]
        spec = json.loads(g.attrs["spec"])
        net = nets[spec["network_variant"]]
        T = g["depth"].shape[0]
        out_dir = os.path.join(out_root, f"{prefix}_{sid}")
        os.makedirs(out_dir, exist_ok=True)
        # adjacency for inspector (in/out edge lists per node)
        in_e = {n["id"]: [] for n in net["nodes"]}
        out_e = {n["id"]: [] for n in net["nodes"]}
        for e in net["edges"]:
            out_e[e["u"]].append(e["id"])
            in_e[e["v"]].append(e["id"])
        # per-frame summary metrics — computed from the QUANTIZED grids so the
        # viewer (which only sees quantized data) reproduces them exactly.
        depth_q = np.round(g["depth"][:] * 1000.0).astype(np.int32)
        rain = g["rain"][:]
        frames = []
        for k in range(T):
            fl = int(((depth_q[k] >= 50) & in_dom).sum())
            frames.append({
                "t_min": (k + 1) * 5,
                "rain_mean_mm": float(rain[k][in_dom].mean()),
                "rain_max_mm": float(rain[k].max()),
                "flood_cells": fl,
                "flood_m2": fl * 25.0,
                "maxd_m": float(depth_q[k].max() / 1000.0),
            })
        meta = {
            "scenario": sid, "split": split, "spec": spec,
            "ny": ny, "nx": nx, "dx_m": 5.0, "dt_min": 5, "T": T,
            "duration_h": spec["duration_h"], "total_mm": spec["total_mm"],
            "x_min": float(f["X"][:].min()), "x_max": float(f["X"][:].max()),
            "y_min": float(f["Y"][:].min()), "y_max": float(f["Y"][:].max()),
            "centre_lat": 28.7523, "centre_lon": 77.4985,
            "flood_threshold_m": FLOOD_THRESH_M,
            "node_maxdepth_m": NODE_MAXDEPTH_M,
            "mass": json.loads(g.attrs["mass"]),
            "mass_err": float(g.attrs["mass_err"]),
            "network_variant": spec["network_variant"],
            "network_note": "SYNTHETIC / inferred — not verified infrastructure",
            "dem_cm": {"b64i16": _b64(_q16(dem, 100.0))},
            "landcover": {"b64u8": base64.b64encode(np.ascontiguousarray(lc).tobytes()).decode("ascii")},
            "low_points": {"b64u8": base64.b64encode(np.ascontiguousarray(low.astype(np.uint8)).tobytes()).decode("ascii")},
            "max_depth_mm": {"b64i16": _b64(_q16(g["max_depth"][:], 1000.0))},
            "time_to_flood_min": {"b64i16": _b64(_q16(np.where(
                np.isfinite(g["time_to_flood_min"][:]),
                g["time_to_flood_min"][:], -1), 1.0))},
            "nodes": [{**n, "in_edges": in_e[n["id"]], "out_edges": out_e[n["id"]]}
                      for n in net["nodes"]],
            "edges": net["edges"],
            "blockage": g["blockage"][:].tolist(),
            "pipe_capacity": g["pipe_capacity"][:].tolist(),
            "surcharge_final_ids": [int(i) for i in np.where(g["surcharge"][:])[0]],
            "overflow_final_mm": (np.asarray(g["overflow"][:], float) * 1000.0).tolist(),
            "quant": {"rain_dmm": "i16 0.1mm", "depth_mm": "i16 mm", "vel_cms": "i16 cm/s", "node_mm": "i16 mm", "pipe_e5": "i32 1e-5 m3/s", "dem_cm": "i16 cm", "ttf": "i16 min, -1=never"},
            "frames": frames,
        }
        json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"))
        nd = g["node_depth"][:]
        pf = g["pipe_flow"][:]
        vel = g["velocity"][:]
        for k in range(T):
            frame = {
                "k": k, "t_min": (k + 1) * 5,
                "rain_dmm": {"b64i16": _b64(_q16(rain[k], 10.0))},
                "depth_mm": {"b64i16": _b64(depth_q[k].astype(np.int16))},
                "vel_cms": {"b64i16": _b64(_q16(np.clip(vel[k], 0, 3), 100.0))},
                "node_mm": {"b64i16": _b64(_q16(nd[k], 1000.0))},
                "pipe_e5": {"b64i32": _b64(_qi(pf[k], 1e5))},
            }
            json.dump(frame, open(os.path.join(out_dir, f"frame_{k:03d}.json"), "w"))
        index.append({"id": f"{prefix}_{sid}", "dir": f"{prefix}_{sid}",
                      "total_mm": spec["total_mm"], "duration_h": spec["duration_h"],
                      "temporal": spec["temporal"], "spatial": spec["spatial"],
                      "blockage": spec["blockage_level"], "T": T,
                      "maxd_m": float(g["max_depth"][:].max())})
        print(f"exported {split}_{sid}: T={T}")
    json.dump(index, open(os.path.join(out_root, "index.json"), "w"))
    print("index written:", len(index), "scenarios")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--max", type=int, default=None)
    a = ap.parse_args()
    export_split(a.split, max_scenarios=a.max)
