# Hydraulics — equations and parameters

## Surface (per cell, per 2 s substep)

Inter-face discharge (Manning, wide channel):

```
h_flow = max(ws1,ws2) − max(z1,z2),  S = min(|Δws|/dx, 0.05)
q = h_flow^(5/3)/n · √S · dx,  direction = sign(Δws)
q_face ≤ 0.125 · h_upwind · dx²/dt   (explicit stability, conservative)
h += dt·(R−I)/3.6e6 − dt·(sink−return) + dt·Qnet/dx²
```

Sources: Bates & De Roo (2000) LISFLOOD-FP; HEC-RAS DWE reference;
UPFLOOD diffusive-wave urban model (2017). See `source.md`.

## Infiltration (Horton defaults, mm/h)

| class | f0 | fc | k |
|---|---|---|---|
| road | 5 | 1 | 2.0 |
| open | 35 | 8 | 2.5 |
| building | 0 | 0 | — |

Literature-typical, NOT calibrated to KIET soils.

## Pipes

`Qcap = (1/n)·(πD²/4)·(D/4)^(2/3)·√S`, n=0.013 concrete (Chow 1959).
Inlet ≤ 0.02–0.10 m³/s × (1−0.8·blockage). Node 1 m² × 1.5 m deep.
Surcharge returns to surface same step. Outfalls free.

## Rainfall

Temporal {uniform, peaked, front/back-loaded, multi-peak} × spatial
{uniform, gaussian cell, moving cell (2–10 m/s), gradient, multi-cell},
5-min steps, totals 10–150 mm / 1–6 h (local CSV: max 114.6 mm/day, p99 ≈ 37 mm).
