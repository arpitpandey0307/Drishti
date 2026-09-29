"""Surface <-> drainage exchange (SRS Module H).

Inlet capture is a physically defined exchange between the surface water level and the
sewer head at each inlet grate (HEC-22 / Chen et al. 2007 1D-2D coupling):

  node head below ground (free inflow):
      Q = min( weir:    Cw * P * h^1.5,
               orifice: Co * Ao * sqrt(2 g h) )
  node pressurised (head above ground, submerged grate):
      Q = Co * Ao * sqrt(2 g (Hs - Hn))       if Hs > Hn  (capture)
  node head above the surface level:
      no capture; the node surcharges and its excess volume is returned to the surface
      by the 1D engine (reverse flow / inlet overflow)

Capture is also limited by the inlet's rated capacity, the ponded volume available on the
cell, and the free volume left in the node. Blockage reduces grate perimeter/area.
Sealed manholes do not capture (they can still overflow).
"""
from __future__ import annotations

import numpy as np

G = 9.81
CAPTURE_KINDS = ("inlet", "junction")


def capture(drain, h, dx, dt, cfg):
    """Surface -> node inflow (m3/s per node) for one exchange step.

    drain: Drainage1D, h: surface depth grid (m), cfg: hydraulics.yaml `exchange` block.
    """
    Cw = float(cfg.get("weir_coeff", 1.7))
    P = float(cfg.get("grate_perimeter_m", 2.0))
    Co = float(cfg.get("orifice_coeff", 0.67))
    Ao = float(cfg.get("grate_area_m2", 0.1))
    Hn = drain.head()
    q = np.zeros(drain.nN)
    free = drain.free_capacity_m3()
    for k, (i, j) in enumerate(drain.cell):
        if drain.kind[k] not in CAPTURE_KINDS:
            continue
        hs = h[i, j]
        if hs <= 1e-5:
            continue
        blk = 1.0 - 0.8 * drain.node_blockage[k]
        ground = drain.rim[k]
        Hs = ground + hs
        if Hn[k] < ground:
            qk = min(Cw * P * blk * hs ** 1.5, Co * Ao * blk * np.sqrt(2 * G * hs))
        elif Hs > Hn[k]:
            qk = Co * Ao * blk * np.sqrt(2 * G * (Hs - Hn[k]))
        else:
            qk = 0.0
        cap = drain.inlet_cap[k] * blk
        qk = min(qk, cap, hs * dx * dx / dt, free[k] / dt)
        q[k] = max(qk, 0.0)
    return q
