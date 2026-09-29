# 03 — Module Deep Dives — Index

This folder holds per-area inventories. Every entry: purpose, inputs/outputs, key functions/classes with `file:line`, dependencies, connections.

- `01_simulation-and-config.md` — `simulation/` (10 modules) + `config/` (5 YAML) + `api/` routing
- `02_dataset-models-space.md` — `dataset/`, `models/`, `outputs/models/`, `space/`
- `03_outputs-visualization-tools.md` — `outputs/`, `visualization/`, `tools/`, `scripts/`, `tests/`
- `04_trackA-maps-html.md` — root HTML visualizers + `index.html` + deploy configs
- `05_data-terrain-campus.md` — `data/`, `terrain/`, `kiet_terrain/`, `kiet_campus_map/`, `kiet_campuse_data/`, `random_info/`, `docs/`
- `06_legacy-empty.md` — `flood/` (dead .pyc), `drainage/` (empty), `synthetic/` (empty), `terrain/{processed,products}` (empty)

Source: 4 parallel subagent scans (backend / data-ML / formulas / root-docs) + direct `ls/du/find/git log` verification 2026-09-07. Counts: 854 files, 825 MB excl `.git`.
