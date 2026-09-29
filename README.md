# Drishti — Urban Flood Nowcasting System (SIH 26085)

Street-level flood nowcasting (0–3 h) that couples rainfall, a DEM-based 2D surface
model and a graph-based drainage network, with a web GIS dashboard and flood-safe routing.
Pilot area: KIET campus, Ghaziabad.

- **Requirements spec:** [`docs/SRS.md`](docs/SRS.md)
- **Build plan (5 tasks):** [`docs/TASKS.md`](docs/TASKS.md)

## Repository layout

| Path | What it is |
|---|---|
| `simulation/` | Physics: `terrain/` (DEM twin), `drainage/` (network graph + SWMM export), `surface/` (runoff + 2D flow), `hydraulics/` (1D engine, exchange, boundaries, coupled loop), `rainfall/`, `scenarios/`, `validation/` |
| `forecast/` | Task 2: rainfall adapters + QC, STEPS ensemble nowcast, ONNX flood surrogate, probabilistic forecast, hotspot refinement — `python -m forecast.run` ([docs](docs/forecast.md)) |
| `dataset/` | Synthetic dataset generator (HDF5), normalization, QC plots |
| `models/` | Baseline U-Net nowcaster + trainers |
| `api/` | Flood-safe routing (`route.py`) and nowcast-driven routing (`route_nowcast.py`) |
| `visualization/data_adapter/` | Exports simulation outputs to viewer bundles |
| `config/` | YAML configs (terrain, drainage, hydraulics, rainfall, simulation, forecast) |
| `data/` | GeoJSON (roads, campus), terrain overlays, `raw/rainfall/` CSVs |
| `kiet_terrain/`, `kiet_campus_map/` | DEM package and campus boundary reconstruction |
| `planner/`, `outputs/viz-demo/` | Pre-computed demo storms for the dashboards |
| `space/` | Hugging Face Space front-end |
| `scripts/`, `tools/` | Data build scripts and checks |
| `tests/` | Pytest suite |
| `docs/` | Design docs, `project/` (report, knowledge, sources), `knowledge_base/`, `notes/`, `images/` |
| `*.html` (root) | Static web apps (kept at root for Vercel/Render static hosting) |

## Web apps

```
python -m http.server 8123
```

| Page | Purpose |
|---|---|
| `dashboard/` | **Operator dashboard (all 5 tasks)** — live twin, probabilistic forecast, hotspots, drainage health + assimilation, road impact + routing, what-if/actions, validation, API/CAP/RBAC ([docs](docs/dashboard.md)) |
| `index.html` | Landing page |
| `flood_planner.html` | Nowcast depth map (0–180 min) + flood-safe routing |
| `flood_viewer.html` | Animated simulation: rain → runoff → drainage → surcharge → flooding |
| `kiet_3d_standalone.html` | 3D terrain world |
| `kiet_road_map.html`, `kiet_terrain_map.html` | 2D road / terrain maps |

## Python

```
pip install -r requirements.txt
python -m pytest tests -q
```

Run the coupled 1D/2D physics model (Task 1, see [`docs/simulation.md`](docs/simulation.md)):

```
python -m simulation.run --total-mm 80 --duration-h 1
python -m simulation.run --total-mm 80 --boundary fixed_stage:2.0 --pump-failed
python -m simulation.run --total-mm 80 --baselines
```

## Data honesty

All drainage is **synthetic** (`verified=false`), not real KIET infrastructure. Terrain is
Copernicus GLO-30 (30 m DSM, ±4 m): broad relief only. See `docs/assumptions.md` and
`docs/project/source.md`.

Sources: © OpenStreetMap contributors · Terrain © DLR/Airbus/Copernicus.
