# Simulation — coupled 1D/2D urban flood digital twin (Task 1, SRS Modules D–I)

Physics engine for SIH 26085. Every drainage asset is **synthetic** (`verified=false`).

```
python -m simulation.run --total-mm 80 --duration-h 1                 # one scenario
python -m simulation.run --total-mm 80 --boundary fixed_stage:2.0     # river backwater
python -m simulation.run --total-mm 80 --pump-failed                  # pump failure
python -m simulation.run --total-mm 80 --baselines                    # B1–B5 table
python -m simulation.drainage.swmm_export --variant 0                 # EPA SWMM .inp
python -m pytest -q                                                   # tests
```

Outputs go to `outputs/runs/<name>/summary.json` (full provenance incl. config).
A 1.5 h storm runs in about 3 s on a laptop. Mass balance closes to ~1e-8.

## Modules

| SRS | Module | File |
|---|---|---|
| D | Terrain intelligence | `simulation/terrain/twin.py` |
| E | Hydrologic runoff | `simulation/surface/infiltration.py` |
| F | 2D surface hydraulics | `simulation/surface/runoff.py` |
| G | 1D drainage hydraulics | `simulation/hydraulics/network1d.py`, `simulation/drainage/network.py` |
| H | Surface–drainage exchange | `simulation/hydraulics/exchange.py` |
| I | Boundary conditions | `simulation/hydraulics/boundary.py` |
| — | Coupling loop | `simulation/hydraulics/simulate.py` |
| §7 | Baselines B1–B5 | `simulation/baselines.py` |

### D — Terrain
160×110 grid at 5 m around (28.7523, 77.4985), row 0 = north (same bounds as the web
viewers). DEM = Copernicus GLO-30 (13×20, 100 valid cells, gaps IDW-filled), bilinear
upsampled + 0.15 m smoothed micro-relief (synthetic detail). Derived: slope, priority-flood
filled DEM, depression depth, D8 flow direction + accumulation, low points. Land cover:
OSM roads (4 m half-width), sanctioned building footprints, OSM campus boundary = closed
domain. `twin.meta` records CRS, vertical datum (EGM2008), resolution and **data tier**
(Tier 1 — public/coarse) so the UI never implies metre-scale accuracy.

### E — Runoff
Per cell: rainfall → interception (open 1 mm) → infiltration (Horton or SCS-CN, chosen by
`hydraulics.yaml: infiltration.method`; ponded water also infiltrates) → depression storage
→ effective rainfall.

### F — 2D surface
Diffusive-wave storage cell (Bates & De Roo 2000): Manning face fluxes driven by water-
surface slope, 1/8-volume face limiter, buildings/outside = walls, dt = 2 s.

### G — 1D drainage
Directed graph: inlet / manhole / junction / storage / outfall nodes; pipe / pump links.
Local-inertial momentum per link on circular sections (full bore when pressurised), node
continuity with SWMM-style storage area (manhole + half pipe plan area). Head-driven, so
backwater, reverse flow and pressurised flow emerge naturally. Pumps: on/off depth
hysteresis, status `auto | on | off | failed`. Blockage reduces pipe area and inlet capture.
Network generator: inlets by accumulation/low point/road score, Dijkstra tree to the
lowest edge outfalls, Rational-method sizing (40 mm/h legacy design), inverts laid with
cover + minimum slope, pump station (sump + pump) in front of outfall 0.

### H — Exchange
At every capturing inlet: weir `Cw·P·h^1.5` / orifice `Co·Ao·√(2gh)` (min of the two) when
the node head is below ground; submerged orifice on the head difference when pressurised;
no capture when the node head is above the surface. Capped by rated inlet capacity,
ponded volume and free node volume. Surcharge excess returns to the surface cell.

### I — Boundaries
Per outfall: `free`, `fixed_stage`, `timeseries`, `tidal` (stages above outfall invert).
Set in `drainage.yaml: boundaries` or per scenario via `spec["boundary"]`.

## Mass balance

`rain + boundary inflow = infiltration + outfall discharge + surface + depression +
interception + node storage` — reported as `mass.rel_error` for every run.

## Baselines (example, 80 mm / 1 h, scored against B5)

| | CSI | MAE (m) |
|---|---|---|
| B1 rainfall threshold | 0.17 | 0.061 |
| B2 rain + DEM | 0.53 | 0.054 |
| B3 + runoff | 0.60 | 0.038 |
| B4 + drainage, no 2D routing | 0.16 | 0.070 |
| B5 full coupled | 1.00 | 0 |

These scores compare simplifications against the full model, not against observations.
Real skill needs observed flood data (SRS Module Z, Task 5).

## Known limitations
- The drainage network is synthetic, and the DEM is a 30 m DSM that includes buildings.
- The 1D engine is our own local-inertial solver. Cross-check it against EPA SWMM
  using the exported `.inp` file.
- Parameters are not calibrated. Calibration comes with data assimilation in Task 3.
