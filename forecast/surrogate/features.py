"""Input features of the flood surrogate — shared by dataset, training and inference so the
three can never drift apart.

Input  (C = 9 static + 2*HIST history + L future + 1 = 36 channels) on the domain crop:
  static : dem (z-score), slope, log flow accumulation, low points, imperviousness, Manning n,
           is_road, is_building, in_domain
  history: rain rate (mm/h) and surface depth (m) for the last HIST steps (t0-HIST+1 .. t0)
  future : cumulative rainfall (mm) from t0 to t0+lead for every lead — the only place the
           rainfall forecast enters, so each ensemble member is one forward pass
  blockage: drainage blockage level (constant plane)
Output: surface depth (m) at each lead.

Velocity is deliberately not an input: the Task-1 velocity output is a crude proxy.
"""
from __future__ import annotations

import numpy as np

HIST = 6
LEADS = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18, 21, 24, 30, 36]      # 5-min steps -> 5 ... 180 min
LEAD_MIN = [5 * l for l in LEADS]
N_FUT = max(LEADS)
CROP = (slice(11, 87), slice(28, 132))                          # campus domain bbox (+pad)
STATIC = ["dem", "slope", "flow_accum_log", "low_points", "imperv", "manning",
          "is_road", "is_building", "in_domain"]
SCALE = {"rain_mmh": 50.0, "depth_m": 0.2, "cum_mm": 50.0}
N_CH = len(STATIC) + 2 * HIST + len(LEADS) + 1
IDX_DEPTH_NOW = len(STATIC) + 2 * HIST - 1                      # last depth-history channel
IDX_WET = (STATIC.index("in_domain"), STATIC.index("is_building"))


def static_stack(twin):
    c = CROP
    dom = twin.in_domain
    dem = twin.dem
    mu, sd = float(dem[dom].mean()), float(dem[dom].std() + 1e-6)
    layers = {
        "dem": np.where(dom, (dem - mu) / sd, 0.0),
        "slope": np.clip(twin.slope, 0, 0.2) / 0.05,
        "flow_accum_log": np.log1p(twin.accum) / 5.0,
        "low_points": twin.low_points.astype(float),
        "imperv": twin.imperv.astype(float),
        "manning": twin.manning / 0.05,
        "is_road": twin.is_road.astype(float),
        "is_building": twin.is_building.astype(float),
        "in_domain": dom.astype(float),
    }
    return np.stack([layers[k][c] for k in STATIC]).astype(np.float32)


def build_inputs(static, rain_hist_mm, depth_hist, fut_rain_mm, blockage=0.0, step_min=5.0):
    """Assemble surrogate inputs on the crop.

    rain_hist_mm : (HIST, ny, nx) mm per step, full or cropped grid
    depth_hist   : (HIST, ny, nx) m
    fut_rain_mm  : (N_FUT, ny, nx) or (M, N_FUT, ny, nx) mm per step after t0
    Returns (M, N_CH, h, w) float32."""
    crop = lambda a: a[..., CROP[0], CROP[1]] if a.shape[-2:] != static.shape[-2:] else a
    rh, dh, fr = crop(np.asarray(rain_hist_mm, np.float32)), crop(np.asarray(depth_hist, np.float32)), \
        crop(np.asarray(fut_rain_mm, np.float32))
    if fr.ndim == 3:
        fr = fr[None]
    M = fr.shape[0]
    cum = np.cumsum(fr, axis=1)[:, [l - 1 for l in LEADS]] / SCALE["cum_mm"]
    hist = np.concatenate([rh * (60.0 / step_min) / SCALE["rain_mmh"], dh / SCALE["depth_m"]])
    fixed = np.concatenate([static, hist])
    x = np.empty((M, N_CH) + static.shape[-2:], np.float32)
    x[:, :fixed.shape[0]] = fixed
    x[:, fixed.shape[0]:fixed.shape[0] + len(LEADS)] = cum
    x[:, -1] = float(blockage)
    return x


def uncrop(pred, shape, fill=0.0):
    """(..., h, w) crop -> (..., ny, nx) full twin grid."""
    out = np.full(pred.shape[:-2] + tuple(shape), fill, np.float32)
    out[..., CROP[0], CROP[1]] = pred
    return out
