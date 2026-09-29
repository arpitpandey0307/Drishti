"""ML-ready dataset API for KIET flood nowcasting (dataset v1.0+).

Design:
- Scenario-level splits live in separate HDF5 files (train/val/test/ood) --
  frames from one storm NEVER leak across splits.
- Static inputs (DEM, slope, flow-accum, low-points, imperviousness, roughness,
  buildings, roads, domain mask) are separated from dynamic inputs
  (rainfall[t,x,y], previous depth, velocity, drainage state).
- Temporal windows: history Broswe (default 6 steps = 30 min) -> future
  targets at configurable lead times (default 5..180 min in 5-min steps).
- Drainage graph: edge_index + per-pipe attrs (capacity, blockage, diameter,
  slope, length) and per-node attrs (ground/rim/invert, kind, surcharge).
- Normalization statistics MUST come from TRAIN only
  (see compute_normalization.py -> normalization_train.json).
- numpy-first; torch Dataset/DataLoader wrappers activate automatically when
  torch is installed (it is NOT required).

Generalization: nothing here is KIET-specific beyond grid size -- static
channels + graph topology are inputs, so synthetic cities can be added later.
"""
from __future__ import annotations
import os, json
import numpy as np

STATIC_CHANNELS = ["dem", "slope", "flow_accum_log", "low_points", "imperv",
                   "manning", "is_road", "is_building", "in_domain"]
DYNAMIC_CHANNELS = ["rain", "depth", "velocity"]
LEAD_STEPS_DEFAULT = [1, 2, 4, 6, 8, 12, 18, 24, 36]  # x5min = 5..180 min
FLOOD_THRESHOLD_M = 0.05


def _open(path):
    import h5py
    return h5py.File(path, "r")


class FloodWindows:
    """Index of all valid (scenario, t0) windows for one split file.

    A window is valid if t0 >= hist_len-1 (full history) and
    t0 + max(lead_steps) < T (all targets observable).
    """

    def __init__(self, h5_path, hist_len=6, lead_steps=None, flood_threshold=FLOOD_THRESHOLD_M):
        self.h5_path = h5_path
        self.hist_len = int(hist_len)
        self.lead_steps = list(lead_steps or LEAD_STEPS_DEFAULT)
        self.hthr = float(flood_threshold)
        self._index = []  # (scenario_id, t0, T)
        with _open(h5_path) as f:
            for sid in f.keys():
                if not sid[0].isalpha() or sid in (
                        "dem", "manning", "imperv", "in_domain", "is_road",
                        "is_building", "X", "Y", "slope", "flow_accum", "low_points"):
                    continue
                try:
                    T = f[sid]["depth"].shape[0]
                except Exception:
                    continue
                t_min = self.hist_len - 1
                t_max = T - max(self.lead_steps) - 1
                for t0 in range(t_min, t_max + 1):
                    self._index.append((sid, t0, T))
        self._index = np.array(self._index, dtype=object)

    def __len__(self):
        return len(self._index)

    def _static(self, f):
        chans = []
        fa = np.asarray(f["flow_accum"][:], dtype=np.float32)
        for c in STATIC_CHANNELS:
            if c == "flow_accum_log":
                chans.append(np.log1p(np.maximum(fa, 0)).astype(np.float32))
            elif c in ("is_road", "is_building", "in_domain", "low_points"):
                chans.append(np.asarray(f[c][:], dtype=np.float32))
            else:
                chans.append(np.asarray(f[c][:], dtype=np.float32))
        return np.stack(chans)  # (C, H, W)

    def _graph(self, f, sid):
        g = f[sid]
        spec = json.loads(g.attrs["spec"])
        nodes = spec.get("_nodes", None)  # not stored; rebuilt from networks file if needed
        cap = np.asarray(g["pipe_capacity"][:], dtype=np.float32)
        blk = np.asarray(g["blockage"][:], dtype=np.float32)
        return {"pipe_capacity": cap, "blockage": blk,
                "pipe_flow_hist": None}  # flows sliced per-window in get()

    def get(self, idx, norm=None):
        """Returns dict(sample). norm: dict from normalization_train.json (or None)."""
        sid, t0, T = self._index[idx]
        t0 = int(t0)
        H = self.hist_len
        with _open(self.h5_path) as f:
            g = f[sid]
            static = self._static(f)
            hist = []
            for c in DYNAMIC_CHANNELS:
                hist.append(np.asarray(g[c][t0 - H + 1:t0 + 1], dtype=np.float32))
            hist = np.stack(hist)  # (3, H, Y, X)
            depth = np.asarray(g["depth"][:], dtype=np.float32)
            rain = np.asarray(g["rain"][:], dtype=np.float32)
            vel = np.asarray(g["velocity"][:], dtype=np.float32)
            node_depth = np.asarray(g["node_depth"][:], dtype=np.float32)
            pipe_flow = np.asarray(g["pipe_flow"][:], dtype=np.float32)
            cap = np.asarray(g["pipe_capacity"][:], dtype=np.float32)
            blk = np.asarray(g["blockage"][:], dtype=np.float32)
            sur = np.asarray(g["surcharge"][:]).astype(np.float32)
            spec = json.loads(g.attrs["spec"])
        L = self.lead_steps
        fut_depth = np.stack([depth[t0 + l] for l in L])          # (L, Y, X)
        fut_mask = (fut_depth >= self.hthr).astype(np.float32)
        fut_rain = np.stack([rain[t0 + l] for l in L])
        max_depth = depth[t0 + 1:t0 + max(L) + 1].max(axis=0)
        ever_flood = (depth[t0 + 1:t0 + max(L) + 1] >= self.hthr).any(axis=0).astype(np.float32)
        ttf_full = np.asarray(g_target_ttf(depth, t0, self.hthr), dtype=np.float32)
        node_t = node_depth[t0]
        pipe_t = pipe_flow[t0]
        sample = {
            "scenario_id": sid, "t0": t0,
            "static": static,                       # (C, Y, X)
            "dynamic_hist": hist,                   # (3, H, Y, X) rain/depth/vel
            "future_rain": fut_rain,                # (L, Y, X)
            "node_depth_t": node_t,                 # (N,)
            "pipe_flow_t": pipe_t,                  # (E,)
            "pipe_capacity": cap, "blockage": blk, "surcharge": sur,
            "target_depth": fut_depth,              # (L, Y, X) PRIMARY
            "target_mask": fut_mask,                # (L, Y, X) PRIMARY
            "target_max_depth": max_depth,          # (Y, X) SECONDARY
            "target_ever_flood": ever_flood,        # (Y, X) SECONDARY
            "target_ttf_min": ttf_full,             # (Y, X) SECONDARY (NaN where never)
            "target_vel": np.stack([vel[t0 + l] for l in L]),
            "lead_min": np.array(L, dtype=np.float32) * 5.0,
            "spec": spec,
        }
        if norm:
            sample = apply_norm(sample, norm)
        return sample


def g_target_ttf(depth, t0, hthr):
    """Minutes from t0 until first flooding at each cell (NaN if never within view)."""
    fut = depth[t0 + 1:] >= hthr
    anyf = fut.any(axis=0)
    first = np.argmax(fut, axis=0).astype(np.float32)
    out = np.full(depth.shape[1:], np.nan, dtype=np.float32)
    out[anyf] = (first[anyf] + 1) * 5.0
    return out


def apply_norm(sample, norm):
    s = dict(sample)
    def _n(arr, key):
        if key in norm:
            m, sd = norm[key]["mean"], norm[key]["std"]
            return (arr - m) / (sd if sd and sd > 0 else 1.0)
        return arr
    s["static"] = s["static"].copy()
    for i, c in enumerate(STATIC_CHANNELS):
        s["static"][i] = _n(s["static"][i], f"static.{c}")
    s["dynamic_hist"] = s["dynamic_hist"].copy()
    for i, c in enumerate(DYNAMIC_CHANNELS):
        s["dynamic_hist"][i] = _n(s["dynamic_hist"][i], f"dyn.{c}")
    s["future_rain"] = _n(s["future_rain"], "dyn.rain")
    s["node_depth_t"] = _n(s["node_depth_t"], "node.node_depth")
    s["pipe_flow_t"] = _n(s["pipe_flow_t"], "pipe.pipe_flow")
    return s


def numpy_batches(windows, batch_size=8, shuffle=True, seed=0, norm=None):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(windows))
    if shuffle:
        rng.shuffle(idx)
    for b in range(0, len(idx), batch_size):
        samples = [windows.get(i, norm) for i in idx[b:b + batch_size]]
        yield collate(samples)


def collate(samples):
    out = {}
    for k in ["static", "dynamic_hist", "future_rain", "node_depth_t", "pipe_flow_t",
              "pipe_capacity", "blockage", "surcharge",
              "target_depth", "target_mask", "target_max_depth",
              "target_ever_flood", "target_ttf_min", "target_vel", "lead_min"]:
        try:
            out[k] = np.stack([s[k] for s in samples])
        except ValueError:  # ragged graph dims (N/E differ) -> keep as list
            out[k] = [s[k] for s in samples]
    out["scenario_id"] = [s["scenario_id"] for s in samples]
    return out


def torch_dataset(windows, norm=None):
    """torch.utils.data.Dataset wrapper (requires torch installed)."""
    import torch
    from torch.utils.data import Dataset as _D

    class _TD(_D):
        def __len__(self):
            return len(windows)

        def __getitem__(self, i):
            s = windows.get(i, norm)
            t = {}
            for k, v in s.items():
                if isinstance(v, np.ndarray):
                    t[k] = torch.from_numpy(np.nan_to_num(v, nan=-1.0))
                else:
                    t[k] = v
            return t

    return _TD()
