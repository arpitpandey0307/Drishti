"""Rainfall scenario generator: temporal x spatial. Seeded, reproducible."""
from __future__ import annotations
import numpy as np

def temporal_profile(kind, nt, rng):
    t = np.linspace(0, 1, nt)
    if kind == "uniform":
        p = np.ones(nt)
    elif kind == "peaked":      # SCS-like triangular, peak mid
        p = 1 - np.abs(t - 0.5) * 2 * 0.85
    elif kind == "front_loaded":
        p = np.exp(-3 * t) + 0.15
    elif kind == "back_loaded":
        p = np.exp(-3 * (1 - t)) + 0.15
    elif kind == "multi_peak":
        p = 0.6 + 0.4 * np.sin(2 * np.pi * (2 + rng.integers(1, 3)) * t + rng.uniform(0, 6.28)) ** 2 * 2
    else:
        p = np.ones(nt)
    return np.clip(p, 0.05, None)

def spatial_field(kind, X, Y, rng, cfg, spec=None):
    ny, nx = X.shape
    spec = spec or {}
    sig_lo, sig_hi = cfg["gaussian_cell"]["sigma_m"]
    sig = float(spec.get("storm_sigma_m", rng.uniform(sig_lo, sig_hi)))
    sig = min(max(sig, 10.0), 400.0)
    cx0, cy0 = spec.get("storm_center_xy", (None, None))
    def _cxy():
        if cx0 is not None:
            return float(cx0), float(cy0)
        return rng.uniform(X.min(), X.max()), rng.uniform(Y.min(), Y.max())
    if kind == "uniform":
        return np.ones((ny, nx))
    if kind == "gradient":
        ang = rng.uniform(0, 2 * np.pi)
        g = X * np.cos(ang) + Y * np.sin(ang)
        g = (g - g.min()) / (g.max() - g.min() + 1e-9)
        return 0.4 + 1.2 * g
    if kind == "gaussian_cell":
        cx, cy = _cxy()
        s = sig
        return 0.15 + 2.2 * np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * s * s))
    if kind == "multi_cell":
        f = np.full((ny, nx), 0.15)
        for _ in range(rng.integers(2, 4)):
            cx, cy = _cxy()
            s = sig
            f += 1.4 * np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * s * s))
        return f
    if kind == "moving_cell":
        # returned as base; motion applied in generate() per timestep
        cx, cy = _cxy()
        s = sig
        return ("moving", cx, cy, s)
    return np.ones((ny, nx))

def generate(spec, X, Y, cfg):
    rng = np.random.default_rng(spec["seed"])
    dur_h = spec["duration_h"]; total = spec["total_mm"]
    dt_min = cfg.get("timestep_min", 5)
    nt = max(2, int(dur_h * 60 / dt_min))
    tp = temporal_profile(spec["temporal"], nt, rng)
    sp = spatial_field(spec["spatial"], X, Y, rng, cfg, spec)
    rain = np.zeros((nt,) + X.shape)
    if isinstance(sp, tuple):  # moving cell
        _, cx, cy, s = sp
        if "storm_dir_deg" in spec:
            ang = np.deg2rad(float(spec["storm_dir_deg"]))
        else:
            ang = rng.uniform(0, 2 * np.pi)
        if "storm_speed_mps" in spec:
            spd = float(spec["storm_speed_mps"])
        else:
            spd = rng.uniform(*cfg["moving_cell"]["speed_mps"])
        vx, vy = np.cos(ang) * spd, np.sin(ang) * spd
        t0 = 0.0
        for k in range(nt):
            t = k * dt_min * 60
            mx, my = cx + vx * (t - t0 - dur_h * 3600 / 2), cy + vy * (t - t0 - dur_h * 3600 / 2)
            rain[k] = 0.1 + 2.4 * np.exp(-((X - mx) ** 2 + (Y - my) ** 2) / (2 * s * s))
    else:
        for k in range(nt):
            rain[k] = sp * tp[k]
    # normalise to total_mm mean over domain
    mean_per_step = rain.mean(axis=(1, 2), keepdims=True) if False else None
    cur_mean = rain.mean()
    rain = rain / max(cur_mean, 1e-9) * (total / nt)
    # rain[k] is mm per step; convert convenience intensity
    return {"rain_mm_per_step": rain.astype(np.float32), "dt_min": dt_min, "nt": nt,
            "spec": spec}

def random_spec(rng, cfg):
    return {"temporal": str(rng.choice(cfg["temporal_profiles"])),
            "spatial": str(rng.choice(cfg["spatial_patterns"])),
            "duration_h": float(rng.uniform(*cfg["duration_h"].values()) if isinstance(cfg["duration_h"], dict) else rng.uniform(cfg["duration_h"]["min"], cfg["duration_h"]["max"])),
            "total_mm": float(rng.uniform(cfg["total_mm"]["min"], cfg["total_mm"]["max"]))}
