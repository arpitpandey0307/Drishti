# Simulation — KIET urban-flood digital twin

Physics-based, ML-training-data generator for SIH 26085. NOT an engineering design tool.

## Domain

- Fine grid 160×110 @ 5 m in a local equirectangular projection about
  (28.7523, 77.4985), documented as UTM 43N / EPSG:32643 (sub-metre error at campus scale).
- DEM: `data/terrain_grid.json` (Copernicus GLO-30 30 m DSM, 13×20, 100 valid cells,
  214.68–231.31 m) bilinearly upsampled + 0.15 m seeded micro-relief.
  Sub-30 m detail is SYNTHETIC (`verified=false`).
- Boundary: `kiet_terrain/campus_osm.geojson` (OSM way 835252667, ~83k m², primary).
  The screenshot-traced boundary in `data/campus.geojson` (~16.9k m²) is kept as an alternate.
- Landcover: buildings (blocked walls) from `data/campus_accurate.geojson`;
  roads (4 m half-width, n=0.015, impervious) from `data/roads.geojson`;
  open (n=0.045, 35% impervious).

## Governing equations

Surface (diffusive-wave storage cell, Bates & De Roo 2000; HEC-RAS DWE form):

- `V = −R^(2/3)/(n·|∇zs|^½)·∇zs`, wide-channel `R≈h_flow`
- `∂h/∂t + ∇·(hu) = R − I − Qd`, explicit, dt=2 s
- Face flux capped at 1/8 upwind-cell volume; water-surface slope capped at 0.05
  (DSM-noise guard); buildings/outside-domain are no-flow walls.
- Closed domain boundary (no run-on/runoff across campus edge) — conservative for ponding.

Infiltration: Horton `f = fc + (f0−fc)e^(−kt)` per class + depression storage
(road 1 mm, open 2.5 mm). SCS-CN incremental option in code (not default).

Pipes: Manning full-flow `Qcap = (1/n)·A·R^(2/3)·√S`; inlet capture ≤ inlet capacity
and ponded availability; node storage 1 m² × depth; surcharge overflow RETURNED to
the surface (mass-exact); blockage scales capacity AND inlet capture; outfalls free discharge.

## Proven conservation

`rain = infiltration + depression + ponding + outfall discharge + node storage`
to ~1e-8 relative (see `docs/validation.md`).

## Run

```
python3 -m dataset.generator.run --split test      # 10 scenarios (default from config)
python3 -m pytest tests/test_simulator.py -q       # 8 physics/graph tests
```
