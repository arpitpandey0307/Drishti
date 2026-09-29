"""Synthetic regional storm events (the hidden "truth" for Level-1 demonstration, SRS §11).

A storm is a set of convective cells (elliptical Gaussians with a growth / mature / decay
life cycle) plus an optional stratiform shield, all carried by a steering wind and modulated
by an advected log-normal texture (so optical flow has features to track). The rain rate is
an analytic function of (x, y, t), so it can be evaluated on the radar grid, at gauges or
directly on the campus grid — and the future is known exactly for verification.

Everything produced here is labelled `synthetic`.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

KINDS = ("squall", "convective", "stratiform")


class StormEvent:
    def __init__(self, seed=0, kind="squall", intensity=1.0, speed_mps=None, direction_deg=None,
                 arrival_min=None, miss_km=None, texture_sigma=0.35):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        rng = np.random.default_rng(seed)
        self.seed, self.kind, self.intensity = seed, kind, float(intensity)
        spd = float(speed_mps if speed_mps is not None else rng.uniform(5.0, 11.0))
        ang = np.deg2rad(float(direction_deg if direction_deg is not None else rng.uniform(0, 360)))
        self.u, self.v = spd * np.cos(ang) * 0.06, spd * np.sin(ang) * 0.06   # km/min
        arr = float(arrival_min if arrival_min is not None else rng.uniform(80, 150))
        miss = float(miss_km if miss_km is not None else rng.normal(0, 4))
        ex, ey = np.cos(ang), np.sin(ang)            # along-track unit vector
        px, py = -ey, ex                             # cross-track
        self.cells = []

        def add(off_along, off_cross, peak, sx, sy, t_peak, life, du=0.0, dv=0.0):
            # position at t=0 so the cell reaches (off_along, off_cross) at time `arr`
            xc = off_along * ex + (off_cross + miss) * px
            yc = off_along * ey + (off_cross + miss) * py
            u, v = self.u + du, self.v + dv
            self.cells.append(dict(x0=xc - u * arr, y0=yc - v * arr, u=u, v=v, peak=peak * self.intensity,
                                   sx=sx, sy=sy, theta=ang, t_peak=t_peak, life=life))

        if kind == "squall":
            for k in range(int(rng.integers(6, 10))):
                add(rng.normal(0, 2), (k - 4) * rng.uniform(6, 9), rng.uniform(30, 65),
                    rng.uniform(2.5, 4.5), rng.uniform(4, 7), arr + rng.normal(0, 25), rng.uniform(50, 90),
                    *rng.normal(0, 0.05, 2))
            # trailing stratiform shield
            add(-25, 0, rng.uniform(6, 12), 18, 45, arr + 40, 120)
        elif kind == "convective":
            for _ in range(int(rng.integers(4, 8))):
                add(rng.normal(0, 12), rng.normal(0, 12), rng.uniform(30, 70),
                    rng.uniform(2, 4), rng.uniform(2, 4), arr + rng.normal(0, 35), rng.uniform(30, 60),
                    *rng.normal(0, 0.08, 2))
        else:  # stratiform
            add(0, 0, rng.uniform(8, 18), 30, 60, arr, 150)
            for _ in range(3):
                add(rng.normal(0, 15), rng.normal(0, 20), rng.uniform(15, 30), 6, 10,
                    arr + rng.normal(0, 40), 80)
        # texture: 512 km periodic log-normal field, advected with the steering wind
        self.tex_n, self.tex_dx = 512, 1.0
        z = gaussian_filter(rng.normal(size=(self.tex_n, self.tex_n)), 3.0, mode="wrap")
        z = z / (z.std() + 1e-9) * texture_sigma
        self.texture = np.exp(z - texture_sigma ** 2 / 2)

    def describe(self):
        return {"kind": self.kind, "seed": self.seed, "intensity": self.intensity,
                "steering_kmh": [round(self.u * 60, 1), round(self.v * 60, 1)],
                "n_cells": len(self.cells), "provenance": "synthetic"}

    def rate_at(self, x_km, y_km, t_min):
        """True rain rate (mm/h) at km coordinates (arrays broadcastable) and time t_min."""
        x, y = np.asarray(x_km, float), np.asarray(y_km, float)
        r = np.zeros(np.broadcast(x, y).shape)
        for c in self.cells:
            life = np.exp(-0.5 * ((t_min - c["t_peak"]) / c["life"]) ** 2)
            if life < 1e-3:
                continue
            dx, dy = x - (c["x0"] + c["u"] * t_min), y - (c["y0"] + c["v"] * t_min)
            ct, st = np.cos(c["theta"]), np.sin(c["theta"])
            a, b = dx * ct + dy * st, -dx * st + dy * ct       # along / cross track
            r += c["peak"] * life * np.exp(-0.5 * ((a / c["sx"]) ** 2 + (b / c["sy"]) ** 2))
        # advected texture (periodic)
        ti = ((-(y - self.v * t_min)) / self.tex_dx) % self.tex_n
        tj = ((x - self.u * t_min) / self.tex_dx) % self.tex_n
        tex = map_coordinates(self.texture, np.stack([np.ravel(ti * np.ones_like(r)),
                                                      np.ravel(tj * np.ones_like(r))]),
                              order=1, mode="grid-wrap").reshape(r.shape)
        out = r * tex
        return np.where(out < 0.1, 0.0, out)

    def rate(self, grid, t_min):
        return self.rate_at(grid.X, grid.Y, t_min)

    def campus_rain(self, twin, times_min, step_min=5.0):
        """Rain on the campus twin grid as mm per step (T, ny, nx), averaged over each step."""
        X, Y = twin.X / 1000.0, twin.Y / 1000.0
        out = []
        for t in times_min:
            sub = [self.rate_at(X, Y, t - step_min + s) for s in (step_min / 4, step_min * 3 / 4)]
            out.append(np.mean(sub, axis=0) * step_min / 60.0)
        return np.array(out, np.float32)
