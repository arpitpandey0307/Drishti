# 03.03 — outputs/ + visualization/ + tools/ + scripts/ + tests/

## outputs/ (580 files, 709 MB — generated, gitignored except viz-demo)

- `outputs/gen_test.log` — v0 10 lines: `scenario_0000 rain=62 blk=0 maxd=0.503` … `0009 rain=104 blk=0.5 maxd=1.202`, mass_err 0.000.
- `outputs/datasets/kiet_flood_test.h5` 17 MB + `kiet_networks_test.json` 77 KB + manifest 180 B (v0); `ood/kiet_flood_ood.h5` 89 MB.
- `outputs/datasets/v1/` 515 MB: train 296 MB / val 57 / test 67 / ood 89 / quarantine 7.0 + networks 153 KB + norm 976 B + manifest 76 KB (360 rows) + SHA256SUMS 860 B.
- `outputs/figures/`: `dataset_v1_distributions.png` 47 KB (`stats.py:61-77`), `scenario_0003.png` 162 KB / `0009.png` 178 KB (`tools/viz.py:12-34`), `qc/*.png` ×8 65–81 KB.
- `outputs/geojson/synthetic_drainage_v0.geojson` 29 KB (`tools/viz.py:36-47`, `note:SYNTHETIC`).
- `outputs/viz/` + `viz-demo/`: ~580 `frame_*.json` 139 KB + `meta.json` 220–222 KB; `viz/index.json` 2.7 KB (12 entries), `viz-demo/index.json` 446 B (2). Dirs `test_scenario_0000..0009`, `v1demo_test_v1_00224/00226`. Sample meta (`test_scenario_0000`): spec{id 0, seed 35159, front_loaded, multi_cell, 4.77 h, 61.79 mm}, T 57, mass{rain 61.79, infil 39.35, drain 6.96, ponded 13.24, maxd 503.46}, mass_err 5.6e-10, dem_cm/landcover/low/maxd/ttf b64i16, nodes/edges, quant{rain dmm, depth mm}, frames[{t_min,rain mean/max,flood_cells,flood_m2,maxd}].
- `outputs/viz-demo/` 5.3 MB committed (test_scenario_0001 T=15 + v1demo_test_v1_00226 T=20) — prod fix (`report.md:336-343`).

## visualization/ (H5→web; only data_adapter live)

- Stubs (0-byte, future): `visualization/__init__.py`, `viewer/__init__.py`, `layers/__init__.py`, `animation/__init__.py`, `controls/__init__.py` — ignore; logic in `flood_viewer.html` + data_adapter.
- `visualization/data_adapter/export_viz.py:1-167` — `export_split(split,h5,net,out,max)` (`:34-158`); landcover encode 0/1/2/3 (`:49-52`); low proxy lowest-10% DEM (`:55-58`); v1demo pick heaviest+blocked (`:60-69`); adjacency (`:87-91`); metrics (`:94-106`: depth_q, flood_cells ≥50, flood_m2×25); meta (`:107-136`, network_note SYNTHETIC `:119`); b64 frames (`:141-150`: rain×10 i16, depth×1000 i16, vel clip[0,3]×100 i16, node×1000 i16, pipe×1e5 i32); CLI (`:161-167`).
- `visualization/data_adapter/validate_viz.py:1-92` — Exactness on test_scenario_0009: index 10, DEM <0.006, maxd <0.0006, TTF exact, frames rain <0.06/depth/node <0.0006/pipe <6e-6, counts+dirs, surcharge set, flooded counts.

## tools/

- `tools/__init__.py` empty. `tools/viz.py:1-47` — `_im` (`:7-10`); `plot_scenario_grids` 6 panels (`:12-34`); `export_network_geojson` (`:36-47`).
- `tools/fetch_demo_data.py:1-35` — HF `Aman34243/drishti-demo-data`: REPO (`:10`), FILES 5 mappings (`:12-18`), `main` hf_hub_download+copy skip-if-exists (`:21-31`).

## scripts/ (map builders + HTML guards)

- `scripts/build_accurate_geojson.py:1-178` — affine (`solve_affine :17`, `ENU_to_WGS84 :51`, `rect :55`, `build_accurate :58`, `write_centroids :161`; CONTROLS 7 `:8-16`, OSM_MATCH `:101`, split `:134-148`).
- `scripts/build_road_data.py:1-81` — Overpass BBOX 28.7480/77.4920/28.7585/77.5050 (`:2`); `fetch :7-11`, `to_line :13-31`, `to_poly :33-55`, `build :57-78`.
- `scripts/build_standalone_3d.py:1-30` — embeds `data/terrain_3d.json` (FETCH_LINE `:13`, `main :15-27`).
- Guards: `validate_geojson.py` (FC, >5 feats, service+footway); `check_sums.py` (kinds, ring closure, lon 77.49–51/lat 28.74–76, parking 15000–26000); `check_accurate.py` (kinds required, bans parking/solar/road); `check_allmaps.py` (campus_accurate in 3D pages); `check_context.py` (renderCampus/kind/tooltip); `check_roadmap.py` (Esri, Accurate labels, no Sanctioned blocks); `check_roads_style.py` (styleRoad/NH-34/dash/legend); `check_shell.py` (leaflet 1.9.4, L.map, roads.geojson, OSM attr).

## tests/

- `tests/test_simulator.py:1-83` — 8 tests: `_cfgs :10-14`, `_spec :16-20`; manning Q(0.6,0.005,0.013)∈0.2–1.0 (`:22`); twin loads (`:26`: domain>1000, road>10, accum≥1); graph 3 variants verified==False (`:34`); rain 36 steps 3h/5min (`:43`); mass (`:51`); blockage drain↓ (`:60`); lowpoints ~2× (`:69`); monotonic (`:77`).
- `tests/test_baseline_unet.py:1-11` — (2,36,110,160)→(2,9,110,160), params>100k.
- `tests/test_route.py:1-18` — wall-with-gap vs sealed.
- `tests/test_route_nowcast.py:1-34` — mocked urlopen (`:26`), scenario val_v1_00213 lead 30 maxd>0. Needs /tmp/space onnx+windows.
