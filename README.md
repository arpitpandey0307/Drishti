# Drishti
Interactive 2D + 3D maps of the KIET campus (roads, buildings, real terrain).
## Open the maps (double-click, no server needed)
- `kiet_3d_standalone.html` — 3D terrain world (roads, buildings, contours, click-for-elevation)
- Or serve the folder: `python3 -m http.server 8123` → http://localhost:8123/kiet_3d_standalone.html
- 2D: `kiet_road_map.html` (roads), `kiet_terrain_map.html` (roads + terrain)

## Data
- `data/` — GeoJSON + terrain overlays used by the maps
- `kiet_campus_map/` — campus boundary reconstruction from screenshot
- `kiet_terrain/` — Copernicus GLO-30 DEM package (raw 30m tile + derivatives)
- `report.md` — full experiment/build log

Sources: © OpenStreetMap contributors · Terrain © DLR/Airbus/Copernicus.
Terrain is 30m DSM ±4m — broad relief only, not survey-grade.

## Flood digital twin (SIH 26085) — physics simulator + synthetic-data generator

Modular surface (diffusive-wave storage cell, Bates & De Roo 2000) + synthetic
drainage (Manning pipes, surcharge, blockage) + rainfall scenarios → HDF5 datasets
for training a future flood-nowcasting model. Mass conserved to ~1e-8.

```
pip install --break-system-packages h5py pyyaml matplotlib scipy  # (numpy stock)
python3 -m dataset.generator.run --split test     # 10 scenarios -> outputs/datasets/
python3 -m pytest tests/test_simulator.py -q      # 8 physics/graph tests
```

Layout: `simulation/` (terrain/surface/drainage/hydraulics/rainfall/scenarios/validation),
`dataset/generator/`, `config/*.yaml`, `tests/`, `docs/{simulation,drainage,hydraulics,assumptions,validation}.md`,
`source.md` (every external source), `outputs/` (datasets/figures/geojson).

**All drainage is SYNTHETIC (`verified=false`) — never real KIET infrastructure.**
See `docs/assumptions.md` and `source.md`.

## Flood viewer (watch RAIN → RUNOFF → DRAINAGE → SURCHARGE → FLOODING)

```
python3 -m http.server 8123
# open http://localhost:8123/flood_viewer.html
```

Zero-dependency browser app animating real simulated outputs (10 test scenarios):
play/pause/reset, timeline scrub, speed, 6 layer toggles, click inspector
(cells/nodes/pipes), live metrics, surcharge alarms, depth legend 0–50+ cm.
Bundles: `python3 -m visualization.data_adapter.export_viz --split test`
(→ `outputs/viz/`); verify: `python3 -m visualization.data_adapter.validate_viz`.
See `docs/viewer.md`. Preview: `preview_flood_viewer_surcharge.png`.
