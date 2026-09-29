# 01 — Project Overview: WHAT was built and WHY

## 1. Problem statement (SIH 26085) [INFERRED from SIH_DEMO.md + knowledge.md + Space title]

Predict street-level flooding 0–3 h ahead from forecast rain + terrain + surface + drainage, with safe-route output. Concrete demo checklist (`SIH_DEMO.md:55-61`): 0–3 h nowcast → Space (5–180 min) + `models/`; rain+DEM+drain coupling → `simulation/`+`dataset/`+viewer; capacity/blockage/backflow → pipes + surcharge inspector; Web-GIS cm depths → `flood_viewer.html` + Space heatmap; safe routing API → Space overlay + `api/route_nowcast.py`.

No sensors, no calibration data, no mapped drains exist for KIET — so the team generated mass-conservative synthetic training data from a plausible (not calibrated) twin (`knowledge.md:30-34`). All drainage is SYNTHETIC (`README.md:35-36`, `SIH_DEMO.md:3`, every viewer banner).

## 2. WHAT — complete inventory by track

### Track A — Campus maps (done, deployed)

| Artifact | File | Purpose | Evidence |
|---|---|---|---|
| 2D road map | `kiet_road_map.html` (4.9 KB, Leaflet 1.9.4) | OSM highways + sanctioned blocks + satellite | Root-file dump §12; `scripts/build_road_data.py:1-81` |
| 2D terrain+road | `kiet_terrain_map.html` (7.1 KB) | + hillshade/slope/contours/low pockets + click-elevation | `report.md:77-93` §4; `data/terrain_*.png/.geojson` |
| 3D terrain world | `kiet_3d_standalone.html` (279 KB) | Three.js, self-contained, click query, exaggeration 1–6× | `report.md:107-137` §§7–8; `scripts/build_standalone_3d.py:1-30` |
| 3D server version | `kiet_3d_terrain.html` (12.6 KB) | same, fetches `data/terrain_3d.json` | Root dump §12 |
| Landing | `index.html` (2.4 KB) | 6 cards, cures static-host 404 | `report.md:158-169` §11; `index.html:18-26` |
| Data | `data/roads.geojson` 199 feats; `data/campus_accurate.geojson` 17 feats; `data/campus.geojson` 50 feats; `data/terrain_3d.json` 299 KB | vendored layers | data-inventory §1 |
| Deploys | Vercel `https://drishti-sand.vercel.app`, Render `https://drishti-cl8r.onrender.com` | static hosting | `knowledge.md:25-28`, `vercel.json`, `render.yaml` |

Centre `[28.75257, 77.49851]` zoom 16; bounds `[[28.75069444,77.49569444],[28.75430555,77.50125]]`; OSM + Esri World Imagery + Copernicus attribution.

### Track B — Flood twin → dataset → model → demos (done through hosted demo)

| Stage | Artifact | Size/state | Evidence |
|---|---|---|---|
| Simulator | `simulation/` 10 logic modules, 8/8 physics tests | passing | `tests/test_simulator.py:1-83`; module dump §4 |
| Dataset v1.0 | `outputs/datasets/v1/` 515 MB, 360 rows (358 valid + 2 quarantined) | local-only (gitignored), SHA256SUMS | `docs/dataset_report.md:1-117` |
| Legacy v0 | `outputs/datasets/kiet_flood_test.h5` 17 MB, 10 scenarios | viewer-only | `outputs/gen_test.log` |
| Model | `outputs/models/baseline_subset30.pt` + `baseline_full100.pt`, 1.9 MB each | gitignored, weights on HF | `models/train_baseline.py`, `train_full.py` |
| Live inference | HF static Space `Aman34243/drishti-flood-nowcast` + model repo `Aman34243/drishti-flood-nowcaster` | live 200s | `report.md:291-305` §20; `space/README.md` |
| Planner (end-user) | `flood_planner.html` (16.5 KB) + `planner/storms/` 2×10 bins 744 KB | committed, live on Vercel | `report.md:323-334` §22 |
| Viewer (physics) | `flood_viewer.html` (38 KB) + `outputs/viz/` (local) + `outputs/viz-demo/` (5.3 MB committed) | `?bank=demo` prod fix | `report.md:336-351` §§23–24 |
| Routing API | `api/route.py` A* + `api/route_nowcast.py` HF→ONNX→route | 2/2 + 1/1 tests | `api/route.py:1-31`, `tests/test_route*.py` |

Grid: 160×110 @5 m (~800×550 m), centre 28.7523/77.4985, EPSG:32643 calc / EPSG:4326 store (`config/terrain.yaml:2-9`). Storms: 10–150 mm / 0.5–6 h train, 150–200 mm / 6–8 h OOD. Leads 5–180 min (9). Flood threshold 0.05 m everywhere.

## 3. WHY this shape — goals and constraints

1. **No ground truth** → synthetic twin is the only trainable source; mass conservation (~1e-8 typical, quarantine 0.35) is the trust anchor (`knowledge.md:242-257`).
2. **Free-tier hosting** → Gradio/Docker Spaces need PRO, so model went in-browser: single-file ONNX + static Space that never sleeps (`report.md:291-305`).
3. **Static deploys** → `index.html` landing + `vercel.json` + `render.yaml` + `.vercelignore`; 40 MB raw DEM kept out (`report.md:158-169`).
4. **Prod 404** → `outputs/` gitignored emptied the viewer; fix shipped 2 smallest bundles (T=15 + T=20, 5.3 MB) as `outputs/viz-demo/` with `?bank=demo` switch (`report.md:336-343`).
5. **Two audiences** → planner (end-user, tap + routes) vs viewer (judge/engineer, full physics + inspector) vs Space (live ML). Kept as three separate HTML apps, not one.

## 4. Current state (FACT)

- Works: all maps; simulator 8/8; v1 dataset 360 rows; baseline trained (subset30 + full100); Space live; planner live; viewer local-full + prod-demo; routing CLI; 10/10 route+physics + 1/1 nowcast tests.
- Broken/incomplete: full-227 training OOM (~6.8 GB bulk); v1 viewer never built (only 2 v1 scenarios ported); SCS-CN dead; `kk=2.2` hardcode; TPU v6e1 no quota; `flood/` + `drainage/` + `terrain/{processed,products}` + `synthetic/` are empty/legacy; root README stale (v0-only).
- Demo path: `SIH_DEMO.md:1-61` (Space → planner → viewer → CLI → retrain).
