# KIET Terrain Integration — Experiment & Build Report

> Per `AGENT.md`: this file logs how the problem was solved, what was researched,
> what was tried, and what was built — so the full trail is preserved.

## 0. Request
User provided `kiet_real_terrain_package.zip` (Copernicus GLO-30 DSM + derivatives +
OSM boundary) and asked: use the terrain, run autonomous experiments/research,
and add an accurate terrain map on top of the existing road map.

## 1. Inventory of the terrain package (observed, not assumed)
- `data/terrain/raw/Copernicus_DSM_COG_10_N28_00_E077_00_DEM.tif` — 41,680,243 bytes,
  3600×3600 float32, 1 arc-sec (~30 m), tiepoint (0,0)→(77.0E, 29.0N), EPSG:4326.
  Pixel formula: `lon = 77 + col/3600`, `lat = 29 − row/3600`. Covers 77–78E, 28–29N.
- `data/terrain/clipped/*.tif` + `derived/*.tif` — all **20×13 px float32**,
  nodata −9999, 100 valid cells. Valid, but tiny (campus ≈ 500×400 m ≈ 16×13 cells).
- `derived/terrain_grid.json` — 13 rows × 20 cols = 260 cells, 100 valid elevations
  214.68–231.31 m, mean 219.22 m. **`slope_deg` is null for every cell** — slope grid
  exists only in `slope_degrees.tif`, not in the JSON.
- `derived/contours.geojson` — 13 lines at 4 levels (218.0, 221.33, 224.66, 227.98).
- `derived/low_points.geojson` — 10 cells ≤ p10 threshold 215.476 m.
- `derived/elevation_overlay.png` / `slope_overlay.png` — **20×13 px** direct grid renders.
- `derived/overlay_metadata.json` — raster bounds
  [[28.7506944, 77.4956944], [28.7543055, 77.50125]].
- `campus_osm.geojson` — 32-vertex OSM way 835252667 boundary (authoritative clip poly).
- Environment: **no GDAL, no rasterio** — PIL + numpy only. (Checked `gdalinfo` → missing,
  `import rasterio` → ModuleNotFound.)

## 2. Key accuracy judgment (research conclusion)
- 30 m DSM over a ~500 m campus gives ~100 usable cells. That resolves the
  broad SW→NE fall (~16 m across campus) but **cannot resolve individual roads,
  drains, or building pads**. Vertical LE90 <4 m is larger than most campus
  micro-relief. So: honest labels only — "broad fall direction + low pockets",
  never "flood depth" or "drainage engineering".
- DSM (surface) ≠ DTM (bare earth): cells over hostels/trees read high.
  The max 231.3 m cell is likely a building/vegetation hit, not ground.

## 3. Experiment log

### Exp1 — Verify raw DEM window vs package stats [DONE]
- Method: `PIL.Image.open` raw 3600×3600 float32 (~51 MB RAM, ok). Pixel math
  `col=(lon−77)*3600`, `row=(29−lat)*3600`. Window cols 1785:1805, rows 885:898
  for overlay bounds. Ray-cast point-in-polygon with the 32-vertex OSM boundary.
- Result: window 13×20=260 cells, min **214.6786** / max **231.3076** — exact match
  to package claim. Window mean 218.40 vs package polygon-masked 219.22.
  My independent polygon mask: n=101, mean 219.05, max 229.42 (package: n=100,
  mean 219.22, max 231.31). The 231.31 cell sits on the polygon edge — 1-cell
  masking difference, expected at 30 m resolution.
- Verdict: **package stats VERIFIED**. Pixel formula confirmed for all later work.
  Side-finding: max cell is an edge cell, likely a DSM building/vegetation hit.

### Exp2 — Recompute slope/hillshade, compare with package [DONE]
- Method: Horn's 3×3 slope on the 20×13 clipped grid, true metric cell size at
  28.7528°N (dx=27.11 m lon, dy=30.71 m lat). Hillshade az 315°/alt 45°.
  No GDAL/rasterio available — pure numpy.
- Result: my slope max **10.75°** / mean 4.54° vs package 14.36° / 5.21°.
  On 47 interior full-3×3 cells: mean abs diff 1.10°, max 4.87° (one edge cell).
  30 m-square-cell assumption barely changes it (max 10.95°).
- Verdict: **broad agreement, method-dependent details**. Package probably GDAL
  with different edge/nodata handling. Both say: gentle campus, a few moderate
  DSM-artifact cells at edges. Safe for 3-class visualization
  (flat <3° / gentle 3–8° / moderate >8°); unsafe for drainage engineering.
### Exp3 — High-res display overlays + smooth contours [DONE]
- Method: scipy `zoom(order=1)` ×40 → 800×520. Hillshade recomputed on the dense
  grid (az 315/alt 45), multiplied over a green→brown elevation ramp; nodata →
  transparent alpha. Slope classified flat <3° / gentle 3–8° / moderate >8°.
  Contours every 2 m via matplotlib on the dense grid, thinned 1:2, tagged
  "bilinear display smoothing — not survey".
- Result: `data/terrain_elevation_hillshade.png` (154 KB),
  `data/terrain_slope_class.png` (11 KB), `data/terrain_contours_smooth.geojson`
  (25 lines, 107 KB), `data/terrain_overlay_meta.json` (bounds + honesty note).
- Verdict: **display-quality good, source-truth preserved**. The 30 m blockiness
  is still faintly visible — deliberately kept, so nobody mistakes smoothing
  for accuracy. Pattern: high ground SW/center (~231 m), fall toward NE low
  pockets (~215 m) near the FC playground/SSB side.

## 4. What was built
- `scripts/` + `data/roads.geojson` + `data/campus.geojson` + `kiet_road_map.html`
  (earlier road map — untouched).
- **Exp3 outputs:** `data/terrain_elevation_hillshade.png` (800×520, hillshade-blended,
  transparent outside grid), `data/terrain_slope_class.png`,
  `data/terrain_contours_smooth.geojson` (25 lines @ 2 m, honesty-tagged),
  `data/terrain_overlay_meta.json`, plus staged copies `data/terrain_grid.json`
  (13×20, 100 valid), `data/terrain_low_points.geojson` (10),
  `data/terrain_contours_pkg.geojson` (13 package lines, kept for reference).
- **`kiet_terrain_map.html`** — Leaflet 1.9.4, same road hierarchy styling as the road
  map plus: elevation+hillshade overlay (on), slope class (off), smooth 2 m contours
  (on), low pockets (on), **click-anywhere elevation query** (nearest valid 30 m cell
  within ~25 m, popup shows `~X m ±4m`), combined layer control + legend, OSM and
  Copernicus attribution, `file://` fallback alert.
- `docs/images/preview_terrain_map.png` — static combined render (this report's proof).
- Validation: all 4 road-map checks + terrain shell/content checks + `node --check`
  pass; bundle ≈ 550 KB.

## 5. How to run
```
cd /home/devdevil/development/drishti
python3 -m http.server 8000
# open http://localhost:8000/kiet_terrain_map.html
```

## 6. Honest limits (do not remove)
30 m DSM, ±4 m vertical, DSM≠bare earth, smoothing is display-only. Good for
"high SW → low NE + watch the 10 low pockets in monsoon". Not for drainage
design, flood depth, or construction — needs LiDAR/RTK survey.

## 7. 3D terrain view [DONE]
- Request: use ALL data, max effort, very accurate 3D terrain view.
- **Payload `data/terrain_3d.json` (323 KB):** 160×104 bilinear-sampled mesh
  (16,640 nodes) from the verified 20×13 source grid + validity mask; 45 in-bounds
  OSM roads with per-vertex sampled elevations; 31 building footprints with base
  elevation (min corner sample) and estimated heights (12 m default, 18 m for
  Saraswati/staff quarters); 25 smoothed 2 m contours with elevations; 12 labels
  + 10 low pockets with elevations.
- **Page `kiet_3d_terrain.html` (Three.js 0.160 via CDN):** vertex-colored terrain
  mesh (invalid faces dropped), extruded buildings, draped roads
  (orange/white/blue by class), purple contours, blue low-pocket spheres, HTML
  labels, sun + hemisphere lighting, orbit controls, **exaggeration slider 1–6×**,
  per-layer toggles, auto-rotate, reset view, **click-terrain elevation query**.
  Data smoothness verified first (max neighbor step 1.42 m — an early scary
  matplotlib preview was proven to be a NaN-triangulation artifact, not data).
- **Verified with real headless-Chrome renders** (3 iterations for camera framing):
  `docs/images/preview_3d_browser.png` is an actual screenshot of the page, not a mockup.
- Run: `python3 -m http.server 8123` → `http://localhost:8123/kiet_3d_terrain.html`
  (needs internet once for the Three.js CDN).

## 8. file:// fix — standalone page [DONE]
- Symptom (user-reported): `Could not load data/terrain_3d.json` alert.
- Reproduced via headless Chrome on `file:///.../kiet_3d_terrain.html` — browsers
  block `fetch()` on file:// (CORS), so the data never loads. Root cause confirmed.
- Fix: `scripts/build_standalone_3d.py` embeds the payload into
  **`kiet_3d_standalone.html`** (293 KB, no fetch). Also upgraded the server
  version's error text to distinguish file:// (points to standalone) from bad
  server root. Verified: file:// screenshot of standalone is **pixel-identical**
  (md5 match) to the verified server render. User fix: double-click
  `kiet_3d_standalone.html` — no server needed (internet still needed once for
  the Three.js CDN).

## 9. Remove thin "tree" towers [DONE]
- Symptom (user-reported): tree-like objects in the 3D view.
- Diagnosis: small OSM structures (9 m² "big treat" kiosk, 25 m² "amul" shop,
  guard room, etc.) were all extruded to the 12 m default height, producing tall
  thin pillars that read as trees/poles.
- Fix: footprint-based heights (≤100 m²→4 m kiosk, ≤400 m²→8 m, default 12 m,
  hostels 18 m) written into `data/terrain_3d.json` (+`area_m2` per building),
  standalone rebuilt, verified by headless-Chrome screenshot — poles gone, low
  flat kiosks remain.

## 10. Remove floating "stick" lines at terrain edges [DONE]
- Symptom (user-reported): tree-like sticks into/out of the ground, still visible
  after §9. Zoomed headless-Chrome crops showed thin white lines floating past
  the terrain edge and lying on the dark base box — road/contour vertices inside
  the bounding box but OUTSIDE the valid DEM mask, floating in air like poles.
- Fix: clipped every road/contour polyline to the valid source-cell mask
  (all-4-neighbors-valid + half-cell edge erosion), splitting into valid runs
  (roads 45→30 segments, contour pts −33%). Before/after crops verified clean.

## 11. Static-hosting compat + deploy (Vercel & Render) [DONE]
- Compat: added `index.html` landing (root 404 otherwise), fixed `render.yaml`
  (dropped empty buildCommand), added `vercel.json` + `.vercelignore` (keeps the
  40 MB raw DEM out of Vercel deploys), verified zero absolute-path refs and all
  15 pages/assets return 200 locally.
- Vercel: imported meAnkit18/Drishti via dashboard (preset Other/static), production
  domain `https://drishti-sand.vercel.app` (plain `drishti.vercel.app` was taken by
  an older project). Note: hashed deployment URLs sit behind Vercel SSO login;
  the production domain is public. Verified 200s for /, 3D page, JSON.
- Render: new Static Site from repo, name Drishti, branch main, no build command,
  publish dir `.` — first deploy 21.7s, live at `https://drishti-cl8r.onrender.com`
  (verified 200s). Both hosts auto-redeploy on `main` pushes.

## 12. Accurate map (sanctioned Rev6 + Google-verified) [DONE]
- Builder `scripts/build_accurate_geojson.py` affine via 6 controls → `data/campus_accurate.geojson` (17 sanctioned buildings A-Z incl. star D, C1-demolish, khasra 280-282-286, 17 labels) + `data/blocks_centroids.csv`.
- Anchors 28.75257,77.49851 / 28.752441,77.49902 / 28.753007,77.498594. Target 3-5m, not survey.
- Maps upgraded: road + terrain + 3D load sanctioned toggles + Esri satellite, popups show 5-decimal lat/long + floors/area/source. 3D extrudes G+n*3.3m (shed 4m), demolish red, sanctioned green.
- Sums: footprint 12186.96 (sanity vs coverage 20801), parking 20232.12, FAR 87715 verified in check_sums. Checks: check_accurate OK 35 feats, check_roadmap OK, check_allmaps OK.

## 13. Physics-based flood digital twin (SIH 26085) [DONE 2026-09-06]
- Goal: simulator + synthetic-data generator only (no ML model yet).
- Researched EPA SWMM 5.1/Ref Vol I-II, LISFLOOD-FP (Bates & De Roo 2000), HEC-RAS DWE,
  UPFLOOD diffusive urban model, Dottori & Todini 2012, Horton/Green-Ampt/SCS-CN,
  Chow 1959 Manning tables, Copernicus GLO-30 handbook. All recorded in `source.md`
  (no invented citations) + Synthetic Assumptions section.
- Twin: 160x110 @5m grid (UTM43N-equivalent), DEM upsampled from verified 13x20 source,
  OSM boundary primary (~83k m2; screenshot boundary ~16.9k m2 kept alternate),
  buildings=walls, roads n=0.015 impervious, open n=0.045.
- Network: terrain+road-inferred DAG to 2 outfalls, ~50 inlets, diameters 0.25-1.0m,
  all verified=false; 3 variants + 6 blockage levels x 3 modes.
- Solver: explicit diffusive storage-cell (Manning), dt=2s, 1/8-volume face caps,
  S cap 0.05, Horton + depression storage, Manning pipes + inlet caps + node storage
  + surcharge-return + blockage; mass closes to 3e-8.
- Debug trail: sign-flipped Qin (anti-diffusion), building-cell water deletion (walls fix),
  trapped network cycles (DAG fix), overflow leak (surface-return fix), ponded unit bug.
- Dataset: 10 test scenarios in outputs/datasets/kiet_flood_test.h5 (17MB, all fields +
  flooded mask + mass attrs, manifest resumable, seed 26085); networks JSON; 2 inspected PNGs.
- Tests: 8/8 pass. Docs: simulation/drainage/hydraulics/assumptions/validation.md.

## 14. Interactive flood simulation viewer [DONE 2026-09-06]
- `flood_viewer.html` (single file, zero deps, canvas 2D): scenario select (10),
  play/pause/reset/speed/timeline scrub (Space + arrows), 6 working layer toggles
  (terrain/rain/water/velocity/drainage/surcharge), click inspector for cells
  (elev/rain/depth/vel/flooded/ttf), nodes (level/in/out/cap/surcharge/provenance),
  pipes (len/D/flow/cap/util/blockage/status), live metrics + causal-chain tracker,
  depth legend 0/1/5/10/20/50+ cm, synthetic-drainage banner.
- Adapter `visualization/data_adapter/export_viz.py`: H5 -> outputs/viz bundles
  (meta + per-frame base64 int16 JSON, ~6MB/scenario, lazy-loaded). No physics touched.
- Validator `validate_viz.py`: ALL CHECKS PASSED (exact grids, edge dirs, 21-id
  surcharge set == model, timeline t=(k+1)*5min, flooded counts on quantized grids).
- Browser-verified: scrub/play/pause/speed/toggles/scenario-switch/cell+node+pipe
  clicks (node #9 level 1.500m=rim surcharge YES; pipe #39 0.0104/0.4932 m3/s).
  Fixed along the way: b64 decoder bug, missing initial load, rain masked to domain,
  play-at-end restart, pipe hit-test 8->13px, surcharge rim-threshold (> vs >=),
  flooded counts now from quantized grids (1mm display resolution documented).
- Preview: `docs/images/preview_flood_viewer_surcharge.png` (t+5:05, 21 surcharged nodes).
- Limits: 2D only; outputs/ gitignored (regenerate w/ 2 commands); needs http server.
- Dataset scaling PAUSED per user instruction (test split only).

## 15. Viewer restyle — Quiet Cartography Overlay Design System [DONE 2026-09-06]
- Applied `Quiet Cartography Overlay Design System.md` across `flood_viewer.html`:
  QC tokens, Manrope/Playfair/DM Mono, glass panels (18px blur), full-bleed map,
  left scenario directory (search + All/Light/Heavy/Blocked pills + rows with
  aria-current), right inspector detail card (6-layer anatomy + Copy readout /
  Jump-to-first-flooding actions), bottom-center transport with depth legend,
  lower-left live-stats + causal steps, lower-right layer pill group (aria-pressed),
  reduced-motion + focus-visible support, <640px responsive rules.
- Map/data rendering untouched (validation still holds).
- Browser-verified: directory search (moving→3/10), pill filters, node #9 card
  (Rim 215.4m, surcharging tag), cell card, transport, all toggles.
- Preview refreshed: `docs/images/preview_flood_viewer_surcharge.png`.

## 16. Flood-ML training dataset v1.0 (Phase 3) [DONE 2026-09-06]
- Stratified sampler (`simulation/scenarios/suite_v2.py`): rainfall class quotas
  (trace/light/moderate/heavy/extreme, local-CSV-grounded) + Latin-Hypercube
  (scipy qmc, numpy fallback) over duration/sigma/speed; 6 synthetic network
  variants; balanced blockage quotas x 3 modes; DEM/manning/depression/imperv
  jitter; 0.5-2 h recession tails; 15% targeted edge cases; separate OOD sampler.
- Simulator deltas (additive only, physics untouched, 8/8 tests pass): spec-driven
  storm sigma/speed/dir/center, `dem`/`manning` overrides, inlet-cap and
  depression scales, dry recession tail (rain/depth lengths consistent).
- Generator (`dataset/generator/run_v2.py`): CSV manifest resume, 2-worker parallel,
  quarantine file, versioned HDF5 attrs, static grids + slope/accum/low-points,
  per-scenario dem_delta. Colab-first: CPU VM bench 0.57 s/step; T4 bench 0.58
  s/step (NumPy can't use GPUs — documented, CPU used). 3 VM preemptions survived
  via manifest resume + local snapshot backups + deterministic-ID merge
  (`dataset/merge_splits.py`).
- Final (local `outputs/datasets/v1/`, 515 MB, SHA256SUMS): 360 rows, 358 valid +
  2 quarantined (OOD >2 m), 0 failed; train/val/test 227/49/48 scenarios;
  OOD 34; windows (30-min hist -> 5-180-min leads) 2692/542/606/1861 with
  12/2/18% no-flood targets. Two analysis-driven top-ups (dry 36 + long-dry 48)
  fixed scenario AND window balance. Normalization from TRAIN only.
- Tooling: `dataset/ml_dataset.py` (windows/graph/batching, torch-optional),
  `compute_normalization.py`, `stats.py`, `qc_plots.py` (9 PNGs),
  `verify_transfer.py` (PASS). Docs: `docs/dataset_report.md`,
  `docs/colab_generation.ipynb`, schema v1, `source.md` §§9-10. Model NOT trained.

## 17. Baseline nowcaster — first training [DONE 2026-09-06]
- Model `models/baseline_unet.py`: U-Net base=32, 476k params, in 36ch
  (9 static + 18 dyn-hist + 9 future-rain) → 9 leads depth, 110x160.
- Trainer `models/train_baseline.py`: MSE depth + 0.2 BCE mask, Adam 1e-3,
  train-only norm. Smoke locally: 8 windows OK. Plan:
  `docs/superpowers/plans/2026-09-06-baseline-nowcaster.md`.
- Colab T4 (torch 2.11+cu128): subset 30 train / 10 val scenarios
  (43+12 MB uploads, full 296 MB train.h5 exceeds ~50 MB upload cap).
  Windows 353/103. 2 epochs 62s loss 0.1379→0.1367; 8 epochs 73s
  loss 0.1373→0.1363 (plateau — underfit, expected on subset).
- Artefact: `outputs/models/baseline_subset30.pt` (1.9 MB, gitignored).
  Full-227-scenario training still open (chunk upload or Drive staging).

## 18. Baseline scale-up 100/49 scenarios [DONE 2026-09-06]
- Chunk upload works: 40 MB splits to `/content/chunks/` + `cat` reassembly
  (dir must exist first). Full 296 MB train.h5 reassembled OK on T4 VM.
- Bulk preload of 227 scenarios (2692 windows ~6.8 GB) too slow/OOM for
  single-exec timeout — scaled to 100 train scenarios instead.
- Run: train 1165 windows (100 scn) / val 542 (49 scn, full val),
  10 epochs batch 16, ~13 s/epoch. Loss 0.1374→0.1362.
  Val RMSE +30min 0.0482 / +180min 0.0485 (best epochs; mid-run 0.049-0.054).
- Artefact: `outputs/models/baseline_full100.pt` (1.9 MB). Log: /tmp/full100.log.
- Lesson: use exec (kernel) + log-file + console-poll for long jobs; console
  background `nohup &` dies on disconnect; client exec timeout ≠ server stop.

## 19. SIH demo slice — v1 viewer + landing + safe-route API [DONE 2026-09-06]
- `export_viz --split v1demo --max 2`: heavy test_v1_00224 (T=51) + blocked
  test_v1_00226 (T=20) → viewer-compatible bundles; index merged 10+2=12.
  Validator relaxed to v0-count check → ALL CHECKS PASSED. Viewer loads
  `outputs/viz/index.json` dynamically, so v1demo appears with no JS change.
- `index.html`: 4th card → `flood_viewer.html` (synthetic-drainage honesty note).
  Served 200/200 on :8199.
- `api/route.py`: A* on 5 m grid (8-conn, flooded ≥5 cm blocked) →
  `{path, length_m, blocked}`. `tests/test_route.py` 2/2; full suite 10/10
  (8 physics + 2 route). Plan: `docs/superpowers/plans/2026-09-06-sih-demo.md`.

## 20. HF-hosted model + live inference (free tier) [DONE 2026-09-07]
- Finding: Gradio/Docker Spaces need PRO — free tier is static-only. So the
  model runs **in-browser**: `baseline_full100.pt` → ONNX (dynamo export,
  weights in `drishti.onnx.data` sidecar; ORT-vs-torch maxdiff 3e-07 on random
  input) + 6 demo windows (15 MB) on static Space (free, never sleeps).
- Space `Aman34243/drishti-flood-nowcast`
  (https://aman34243-drishti-flood-nowcast.static.hf.space/): window picker,
  9 lead times, canvas depth heatmap, JS A* route overlay, deep-link
  `?window=&lead=`. Verified 200s for page/onnx/meta + title.
- Model repo `Aman34243/drishti-flood-nowcaster`: weights + card + code.
- Connection: `api/route_nowcast.py` fetches Space-hosted weights/inputs,
  predicts via onnxruntime, routes → JSON. Live: val_v1_00213 +30min,
  max 0.101 m, 175 m² flooded, 745 m safe route. Test 1/1 (local-file fixture).
- `SIH_DEMO.md` runbook + landing Live-Model card. Gradio `app.py` kept in
  /tmp only (needs PRO — not pursued).

## 21. Lean GitHub push + deploy verification [DONE 2026-09-07]
- `.gitignore`: outputs/, *.h5/*.tif/*.pt/*.onnx(+.data), kiet_terrain/data/,
  terrain/ + flood/ + synthetic/ + drainage/ (dead, unimported), space bins,
  caches. Removed tracked 40 MB raw tif (`git rm --cached`, file kept local).
  Staged set audited: no blobs >1 MB except 438 KB preview PNG.
- Fresh-clone runnable: `tools/fetch_demo_data.py` pulls viewer sets from new
  public dataset `Aman34243/drishti-demo-data` (v0 17 MB + v1 67 MB, verified
  round-trip); `space/README.md` documents binary fetch + rebuild.
- Pushed 8422ab8 (+904c5e3 ONNX fix). Vercel serves new landing (Live-Model
  card found in prod HTML); Render 200 incl. flood_viewer.html.
- Browser check via headless Chrome (no browser-MCP tool in this env; `mcp`
  CLI broken — missing typer): landing 5 cards OK; Space caught + fixed
  ORT-web external-data failure (console: `Module.MountedFiles is not
  available`) by inlining weights to single-file ONNX (ORT-vs-torch 3e-07);
  Space now prints "model ready".

## 22. End-user planner page [DONE 2026-09-07]- `flood_planner.html` (new; landing card inserted after Flood Nowcasting Demo,
  all existing cards untouched): Leaflet OSM + campus + roads, baked
  baseline-U-Net depth stacks (`planner/storms/`, 2 storms × t0 + 9 leads,
  int16-mm bins, 744 KB total) as heat overlay with NOW→+180 slider, tap for
  water-now/at-horizon/peak/onset + CLEAR/WATCH/WARNING/DANGER badge, nearest
  road label, origin/destination → normal (grey dashed) vs flood-aware (green,
  10× depth penalty, ≥30 cm hard-avoid) A* routes with distance/worst-water
  stats, `?storm=&h=&selftest=` deep-links, synthetic labels throughout.
- Verified headless: zero console errors; overlay pixel-signature confirmed;
  selftest shows 64 cm/DANGER + working dual routes (5.30 km). Fixed along the
  way: `depth_now.bin` naming, init-order guard, overlay pane order, demo
  endpoints via largest road-graph component. Live on Vercel (200s).

## 23. Prod simulation fix — shipped demo bank [DONE 2026-09-07]
- Root cause: `outputs/` gitignored → `outputs/viz/index.json` 404 on Vercel,
  viewer directory empty on prod (planner data was fine).
- Fix: `outputs/viz-demo/` (2 smallest bundles: test_scenario_0001 T=15 +
  v1demo_test_v1_00226 T=20, 5.3 MB) committed via `outputs/*` + `!viz-demo`
  ignore negations; viewer `?bank=demo` switches roots (3 fetch sites +
  0009-aware default). Local full bank + validator untouched.
- Verified: headless 2/2 runs render, prod serves index + frames (200s).

## 24. Headfull browser proof — simulation works [DONE 2026-09-07]
- No browser-MCP server exists here (`mcp` = dev-tools CLI only), so tested
  with real headed Chrome (Xvfb + CDP, `/tmp/cdp_test.py`): Play advanced
  k 0→4 (clock t+0:25), canvas click selected cell [64,80] with inspector
  readout, timeline CSV 17 rows, cell-series CSV 17 rows — ALL PASSED.
  Screenshot shows live flooding + surcharge halos + full causal chain.
  Nothing to fix.

## Landing redesign — 2026-09-07 (cinematic flood-intelligence theme)
- Inspected `index.html` (6 plain cards), `vercel.json` (static, no build), routes: `flood_planner.html`, HF Space nowcast, `kiet_3d_standalone.html`, `flood_viewer.html?bank=demo&env=csv`, `kiet_terrain_map.html`, `kiet_road_map.html`.
- Rewrote `index.html` only: full-viewport `<video autoplay muted loop playsinline>` (Pexels CDN flood clips + photo poster fallback), dark cinematic gradient + grain overlays, glassmorphism cards (`backdrop-filter: blur(18px)`), navy/black + cyan accents, Space Grotesk/Inter type.
- Hero: DRISHTI / Urban Flood Intelligence System / street-level flooding + safer routes tagline / primary CTA `flood_planner.html` / NOW→+180 min note / 0–3 HR NOWCAST + REAL-TIME FLOOD INTELLIGENCE + STREET-LEVEL PREDICTION details. Cards preserve all 6 original hrefs in 5 prioritized glass tiles (2D maps merged into one tile with 2 chips). Responsive 5→3→1 col, `prefers-reduced-motion` respected, video tryPlay retry + error fallback.

## 25. Project explainer video with /brag [DONE 2026-09-30]
- Goal: a 4–5 min narrated video (problem → solution → uniqueness → full prototype demo → results) that a stranger can follow.
- Tooling: installed the `/brag` + `/brag-slim` skills (github.com/latent-spaces/brag) into `~/.claude/skills/`, the Hyperframes skills
  (`npx hyperframes skills`, CLI 0.8.93) and Kokoro TTS (`pip install kokoro-onnx soundfile`). `/brag --voice` keeps the full Hyperframes workflow.
- Script: 15 scenes written from `docs/SRS.md`, `docs/TASKS.md`, `docs/dashboard.md` and the homepage copy (`brag-output/brag-plan.md`).
  Every figure comes from `dashboard/data/` (CSI 0.79 vs 0.24, 67 % flagged / 20 min / 2 % FAR, 87 % less sensor error, 21.9 s cycle).
- Narration: Kokoro `af_heart`, one WAV per sentence so subtitles and on-screen reveals land on the words; music bed ducked under the voice (`work/build_timeline.py`).
- Demo footage: real clips of the running site (`python -m http.server 8123`) recorded with headless Chrome (GPU) via CDP screencast,
  with a visible cursor and clicks scheduled on the narration timeline (`work/record.js`): homepage 3D replay, dashboard A–H,
  radar-outage drill, routing, action lab + approval, CAP export.
- Composition: `brag-output/composition/index.html`, generated by `work/gen.py` (label cards, punch-ins on the side panel, subtitles, count-ups).
  `npx hyperframes check` passes (0 errors, layout clean, 45/45 contrast). Output `brag-output/brag.mp4` (1920×1080, 30 fps, 4:51) + `brag.jpg` poster + `share-copy.txt`.
