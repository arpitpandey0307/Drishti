# Drishti — Project Knowledge Dump — Master Index

**Repo:** `/home/devdevil/development/drishti`
**Dump created:** 2026-09-07 (UTC 2026-09-06 per task clock)
**Method:** full filesystem scan + `git log --oneline --graph --all` (33 commits) + read of every `.py/.yaml/.md/.html` + artifact listing
**Rule obeyed:** no existing code modified; only READ + CREATE in `project_knowledge_dump/`

## 1-page executive summary

**Drishti** is two projects in one repo, both centred on the KIET Ghaziabad campus (28.7523N, 77.4985E):

- **Track A — Campus maps (done, deployed):** Interactive 2D (Leaflet 1.9.4) + 3D (Three.js 0.160) maps of KIET — roads from OSM Overpass (199 features), buildings from OSM + sanctioned Rev6 GDA plan (affine A–Z, 3–5 m, UNVERIFIED), terrain from Copernicus GLO-30 DSM 30 m (±4 m, DSM≠earth, 13×20=260 cells, 100 valid, 214.68–231.31 m). Pages: `kiet_road_map.html`, `kiet_terrain_map.html`, `kiet_3d_standalone.html` (293 KB self-contained), `kiet_3d_terrain.html`. Landing `index.html` (6 cards). Live on Vercel `https://drishti-sand.vercel.app` + Render `https://drishti-cl8r.onrender.com`.
- **Track B — Flood digital twin + ML nowcaster (SIH 26085, done through baseline + hosted demo):** Modular physics simulator (`simulation/`: diffusive-wave storage-cell surface à la Bates & De Roo 2000, synthetic Manning-pipe drainage DAG with surcharge + 0–90% blockage, Horton infiltration inline k=2.2, 5-min rain × 150×2-s substeps, mass conserved ~1e-8 typical) on a 160×110 @5 m grid (~800×550 m, EPSG:32643 calc / EPSG:4326 store) → stratified v1.0 dataset (360 scenarios: 324 prod + 36 OOD-plan → 358 valid + 2 quarantined; 515 MB HDF5; 227/49/48 train/val/test + 34 OOD; windows 2692/542/606 train/val/test + 1861 OOD, 6-hist → 9 leads 5–180 min) → `BaselineUNet` (in 36 ch = 9 static + 18 hist + 9 future-rain → 9 depth maps, base=32, 476,297 params, loss MSE+0.2·BCE, Adam 1e-3, val RMSE +30 min 0.048 m / +180 min 0.049 m on 100/49-scenario scale-up) → ONNX single-file export (ORT-vs-torch maxdiff 3e-07) hosted on free HF static Space `Aman34243/drishti-flood-nowcast` with in-browser predict + JS A* routing → end-user planner `flood_planner.html` (2 baked storms × t0+9 leads int16-mm bins, 744 KB) with tap-depth/peak/onset/risk bands + normal vs flood-aware road routing → physics viewer `flood_viewer.html` (35 KB zero-dep canvas, 10 v0 + 2 v1 scenarios, Quiet Cartography restyle, CSV export, click inspector, surcharge alarms).
- **Honesty spine:** every drainage pipe is SYNTHETIC (`verified=false`); 30 m DSM resolves broad SW→NE fall (~16 m) but no roads/drains; all depths are MODEL OUTPUT, never observed flooding. This labelling is in README, knowledge.md, source.md, docs/assumptions.md, every viewer banner.

**Counts (excl `.git`, measured 2026-09-07):** 854 files, 825 MB total. 569 JSON (mostly `outputs/viz` frames), 62 py, 54 pyc, 46 md, 23 png, 20 bin (planner), 16 jpeg, 13 geojson, 8 html, 8 h5, 7 tif, 7 csv, 6 yaml, 2 zip, 2 pt. Top dirs: `outputs/` 709 MB, `kiet_terrain/` 40 MB, `terrain/` 23 MB, `kiet_campus_map/` 3.2 MB, `kiet_campuse_data/` 2.2 MB, `data/` 788 KB, `planner/` 744 KB. Git: 33 commits on `main` only, `5d9cd1b first commit` → `60a1028 Landing: drop duplicate demo card`.

## File map of this dump

| File | What |
|---|---|
| `00_INDEX.md` | this file |
| `01_project-overview-what-why.md` | WHAT + WHY, tracks, problem statement, current state |
| `02_architecture-how-things-connect.md` | end-to-end pipeline, data flow, mermaid diagrams |
| `03_module-deep-dives/` | per-folder deep dives (6 files + README) |
| `04_formulas-algorithms-parameters.md` | every equation/threshold/magic number with file:line |
| `05_experiments-ledger.md` | Exp-ID table from git + report.md + outputs |
| `06_data-datasets-sources.md` | all datasets, schemas, sizes, provenance, limitations |
| `07_research-papers-references.md` | every paper/doc/library cited or strongly implied |
| `08_decisions-tradeoffs-evolution.md` | design decisions, alternatives, git evolution, FACT vs INFERRED |
| `09_how-to-run-reproduce-demo.md` | setup, commands, demo flows, deploy |
| `10_gaps-todo-future-work.md` | what works / broken / incomplete / next |
| `11_for-paper-and-ppt/` | copy-paste bullets, figures list, tables |

## How to use

- **Paper/PPT/viva:** start here → `11_for-paper-and-ppt/README.md` → `01` → `02` → `04` → `05`.
- **Reproduce:** `09_how-to-run-reproduce-demo.md`.
- **Every claim:** carries `path:line` or commit hash. `[INFERRED]` = archivist inference, not repo text.
- **Stale-doc warning:** root `README.md` describes only v0 (10 scenarios); `knowledge.md` (2026-09-06) + `report.md` §§16–24 supersede it.
