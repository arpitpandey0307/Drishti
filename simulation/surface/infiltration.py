"""Hydrologic runoff engine (SRS Module E), per grid cell:

    rainfall -> interception -> infiltration -> depression storage -> effective rainfall

Infiltration methods (EPA SWMM formulations, see docs/project/source.md):
  horton   f = fc + (f0 - fc) exp(-k t)   (t = time since wetting, per land-cover class)
  scs_cn   incremental SCS Curve Number (Akan & Houghtalen); rain-rate limited
Ponded surface water on pervious cells also infiltrates up to the remaining capacity.
All volumes are tracked so the coupled model can close its mass balance.
"""
from __future__ import annotations

import numpy as np

CLASSES = ("road", "open", "building")


def _by_class(cls, table, key=None, default=0.0):
    vals = [(table.get(c, {}) if key else table.get(c, default)) for c in CLASSES]
    if key:
        vals = [v.get(key, default) if isinstance(v, dict) else default for v in vals]
    return np.choose(np.clip(cls, 0, 2), np.array(vals, float))


class RunoffModel:
    """cell_class: 0 road, 1 open, 2 building/outside. wet: cells that receive rain."""

    def __init__(self, hyd_cfg, cell_class, wet, dep_scale=1.0, infiltration=True):
        inf = hyd_cfg["infiltration"]
        self.method = inf.get("method", "horton")
        self.enabled = infiltration
        self.wet = wet
        cls = cell_class
        self.interc_max = _by_class(cls, inf.get("interception_mm", {"road": 0.0, "open": 1.0, "building": 0.0})) * wet
        self.dep_max = _by_class(cls, inf["depression_mm"]) * float(dep_scale) * wet
        hz = inf["horton"]
        self.f0 = _by_class(cls, hz, "f0_mmh")
        self.fc = _by_class(cls, hz, "fc_mmh")
        self.k = _by_class(cls, hz, "k_per_h", 2.0)
        cn = _by_class(cls, inf["scs_cn"], default=98.0)
        self.S = 25400.0 / np.maximum(cn, 1.0) - 254.0        # potential retention (mm)
        self.P = np.zeros(cls.shape)                           # cumulative rain (mm), SCS-CN
        self.t_wet_h = np.zeros(cls.shape)                     # Horton wetting time
        self.interc = np.zeros(cls.shape)                      # mm stored
        self.dep = np.zeros(cls.shape)                         # mm stored
        self.infil_total_mm = np.zeros(cls.shape)

    def capacity_mmh(self, dt_h, rain_mmh):
        if not self.enabled:
            return np.zeros_like(rain_mmh)
        if self.method == "scs_cn":
            P0 = self.P
            P1 = P0 + rain_mmh * dt_h
            F = lambda P: P - np.where(P > 0.2 * self.S, (P - 0.2 * self.S) ** 2 / (P + 0.8 * self.S), 0.0)
            self.P = P1
            # rain-limited incremental loss; allow a small continuing capacity (fc) for ponding
            return np.maximum((F(P1) - F(P0)) / max(dt_h, 1e-9), 0.0) + self.fc
        self.t_wet_h += dt_h
        return self.fc + (self.f0 - self.fc) * np.exp(-self.k * self.t_wet_h)

    def step(self, dt_s, rain_mmh, h):
        """Returns (effective rain mm/h onto the surface, ponded water infiltrated (m) per cell)."""
        dt_h = dt_s / 3600.0
        rain_mm = np.where(self.wet, rain_mmh, 0.0) * dt_h
        # interception
        to_i = np.minimum(np.maximum(self.interc_max - self.interc, 0.0), rain_mm)
        self.interc += to_i
        r = rain_mm - to_i
        # infiltration (rain first, then ponded water)
        cap_mm = self.capacity_mmh(dt_h, rain_mmh) * dt_h * self.wet
        f_rain = np.minimum(cap_mm, r)
        r = r - f_rain
        f_pond_m = np.minimum((cap_mm - f_rain) / 1000.0, h) * (self.f0 > 0) if self.enabled else np.zeros_like(h)
        self.infil_total_mm += f_rain + f_pond_m * 1000.0
        # depression storage
        to_d = np.minimum(np.maximum(self.dep_max - self.dep, 0.0), r)
        self.dep += to_d
        r = r - to_d
        return r / dt_h, f_pond_m
