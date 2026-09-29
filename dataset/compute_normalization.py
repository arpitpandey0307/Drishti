"""Compute normalization statistics from TRAIN split ONLY.

Reads outputs/datasets/kiet_flood_train.h5, accumulates per-channel
mean/std with Welford's algorithm (streaming, low RAM), writes
outputs/datasets/normalization_train.json.

Never include val/test/ood frames -- that would leak the evaluation
distribution into training preprocessing.
"""
from __future__ import annotations
import json
import numpy as np
import h5py

STATIC_KEYS = {"dem": "static.dem", "slope": "static.slope",
               "imperv": "static.imperv", "manning": "static.manning"}


class Welford:
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0

    def update(self, x):
        x = np.asarray(x, dtype=np.float64).ravel()
        # subsample huge grids for speed (deterministic stride)
        if x.size > 20000:
            x = x[::x.size // 20000]
        for v in x:
            self.n += 1
            d = v - self.mean
            self.mean += d / self.n
            self.M2 += d * (v - self.mean)

    @property
    def std(self):
        return float(np.sqrt(self.M2 / max(self.n - 1, 1)))


def compute(train_path="outputs/datasets/kiet_flood_train.h5",
            out_path="outputs/datasets/normalization_train.json",
            max_scenarios=None):
    stats = {}
    for k in list(STATIC_KEYS.values()) + ["static.flow_accum_log",
                                           "dyn.rain", "dyn.depth", "dyn.velocity",
                                           "node.node_depth", "pipe.pipe_flow"]:
        stats[k] = Welford()
    with h5py.File(train_path, "r") as f:
        sids = [k for k in f.keys() if k not in (
            "dem", "manning", "imperv", "in_domain", "is_road", "is_building",
            "X", "Y", "slope", "flow_accum", "low_points")]
        if max_scenarios:
            sids = sids[:max_scenarios]
        fa = np.log1p(np.maximum(np.asarray(f["flow_accum"][:], dtype=np.float64), 0))
        stats["static.flow_accum_log"].update(fa[f["in_domain"][:] == 1])
        for h5_key, flat_key in STATIC_KEYS.items():
            arr = np.asarray(f[h5_key][:], dtype=np.float64)
            stats[flat_key].update(arr[f["in_domain"][:] == 1])
        for i, sid in enumerate(sids):
            g = f[sid]
            stats["dyn.rain"].update(np.asarray(g["rain"]))
            stats["dyn.depth"].update(np.asarray(g["depth"]))
            stats["dyn.velocity"].update(np.asarray(g["velocity"]))
            stats["node.node_depth"].update(np.asarray(g["node_depth"]))
            stats["pipe.pipe_flow"].update(np.asarray(g["pipe_flow"]))
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(sids)}", flush=True)
    norm = {k: {"mean": float(w.mean), "std": float(w.std), "n": int(w.n)}
            for k, w in stats.items()}
    json.dump(norm, open(out_path, "w"), indent=1)
    print(f"wrote {out_path} from {len(sids)} train scenarios")
    for k, v in norm.items():
        print(f"  {k}: mean={v['mean']:.5g} std={v['std']:.5g}")
    return norm


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="outputs/datasets/kiet_flood_train.h5")
    ap.add_argument("--out", default="outputs/datasets/normalization_train.json")
    a = ap.parse_args()
    compute(a.train, a.out)
