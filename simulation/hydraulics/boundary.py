"""Downstream boundary conditions for outfalls (SRS Module I).

A boundary returns the water level (m, same datum as the DEM) at an outfall at time t.
Stages are given relative to the outfall invert, so configs stay site-independent.

  free          free discharge (level = invert; water leaves unhindered)
  fixed_stage   constant receiving-water level       {stage_m}
  timeseries    piecewise-linear level vs time       {times_min: [...], stages_m: [...]}
  tidal         sinusoidal tide / river oscillation   {mean_m, amplitude_m, period_h, phase_h}

A level above the connected pipe crown causes backwater; a level above the upstream node
head causes reverse flow into the network (e.g. river/nala backflow).
"""
from __future__ import annotations

import math

import numpy as np

KINDS = ("free", "fixed_stage", "timeseries", "tidal")


class Boundary:
    def __init__(self, spec=None):
        spec = dict(spec or {"type": "free"})
        self.kind = spec.get("type", "free")
        if self.kind not in KINDS:
            raise ValueError(f"unknown boundary type {self.kind!r}; expected one of {KINDS}")
        self.spec = spec

    def stage(self, t_s):
        """Stage above outfall invert (m) at time t_s (seconds from simulation start)."""
        s = self.spec
        if self.kind == "free":
            return 0.0
        if self.kind == "fixed_stage":
            return float(s["stage_m"])
        if self.kind == "timeseries":
            return float(np.interp(t_s / 60.0, s["times_min"], s["stages_m"]))
        # tidal
        per = float(s["period_h"]) * 3600.0
        return float(s.get("mean_m", 0.0) + s["amplitude_m"]
                     * math.sin(2 * math.pi * (t_s + float(s.get("phase_h", 0.0)) * 3600.0) / per))

    def level(self, t_s, invert_m):
        return invert_m + max(self.stage(t_s), 0.0)

    def describe(self):
        return dict(self.spec, type=self.kind)


def for_outfalls(net, cfg_boundaries=None, spec_boundary=None):
    """Boundary per outfall node id. Priority: scenario spec > config per-outfall > config default."""
    cfg_boundaries = cfg_boundaries or {}
    default = cfg_boundaries.get("default", {"type": "free"})
    per = cfg_boundaries.get("outfalls", {}) or {}
    out = {}
    for nd in net["nodes"]:
        if nd["kind"] == "outfall":
            b = spec_boundary or per.get(nd["id"]) or per.get(str(nd["id"])) or default
            out[nd["id"]] = Boundary(b)
    return out
