# 03.05 — data/ + terrain + campus + docs + random_info

## data/ (784 KB, 13 files — curated static GIS)

- `blocks_centroids.csv` 397 B — 8 rows A,B,C,D,E,F,G,L (A 28.75315,77.49713,G+2,2056.5); from `build_accurate_geojson.py:161-175`.
- `campus.geojson` 22 KB 50 feats — OSM buildings+pitches+boundary+label via `build_road_data.py:65-78`; validated `validate_geojson.py:2-8`.
- `campus_accurate.geojson` 16 KB 17 feats verified-only — affine ENU→WGS84 (`:51-54`, CONTROLS 7 `:8-16`, `solve_affine :17-49`, OSM_MATCH `:101`, split `:134-148`); props sanctioned_name/floors/footprint/confidence/osm_match/real_name; guarded `check_accurate.py`, `check_sums.py`.
- `campus_sanctioned_unverified.geojson` 30 KB 63 feats DO-NOT-RENDER — parking/solar/road + unmatched; parking 15000<ps<26000 (`check_sums.py:22-24`).
- `roads.geojson` 84 KB 199 LineStrings — Overpass way[highway] BBOX 28.7480/77.4920/28.7585/77.5050 (`build_road_data.py:2`); props name/highway/service/access/tunnel/ref/osm_id (`:13-31`).
- `terrain_grid.json` 21 KB — browser grid {source_res 30.92, rows[{lat,lon,elevation|null}]}.
- `terrain_3d.json` 299 KB — {bounds lon0 77.4956/lat0 28.7506/lon1 77.5012/lat1 28.7543, grid 160×104 elev 219.22…}; embedded by `build_standalone_3d.py:15-27`.
- `terrain_overlay_meta.json` 286 B — bounds + Copernicus GLO-30 + min 214.68 max 231.31.
- Contours smooth 107 KB 25 feats / pkg 13 KB 13 feats; low_points 2.1 KB 10 feats (threshold_p10 215.476, e.g. [77.49888,28.75388]:215.385); hillshade 154 KB + slope_class 11 KB (Leaflet imageOverlay).

## terrain/ (raw 23 MB, rest empty)

- `terrain/raw/N28E077_FABDEM_V1-2.tif` 23,812,146 B — FABDEM v1-2 tile N28E077 (Copernicus-derived bare-earth, 30 m), archival source covering 28.75/77.49. Current `twin.py:96` loads `data/terrain_grid.json` instead — tif is lineage, not runtime.
- `terrain/processed/`, `terrain/products/` — empty, awaiting DEM build outputs (twin does upsampling in-memory).

## kiet_terrain/ (40 MB real DEM package)

- `README.md:1-79` — boundary OSM way 835252667 lat 28.7509201–7542239 lon 77.4959414–5010837 centroid 28.75279,77.49883 (`:9-13`); source `Copernicus_DSM_COG_10_N28_00_E077_00_DEM.tif` AWS COG (`:21-22`), DSM≠DTM, 30 m EPSG:4326 <4 m LE90 <6 m CE90 (`:23`); clipped 214.6786–231.3076 mean 219.2223 (`:25`); Leaflet snippet (`:54-71`); DLR/Airbus + ODbL (`:77-79`).
- `build_log.txt` bbox + {raw 41680243, min 214.678 max 231.307 mean 219.222 slope_max 14.35}.
- `campus_osm.geojson` 3.0 KB 32-vertex; `osm_kiet_full.json` 6.4 KB (cgimap 2.1.0, node 7796503327 28.75309,77.50090…).
- `data/terrain/raw/...DEM.tif` 40 MB; `clipped/*.tif` 963 B stubs; `derived/` elevation/slope/aspect/relief stubs + contours 13 KB + low 2.1 KB + grid 21 KB + overlay 288 B + PNG stubs.

## kiet_campus_map/ (3.2 MB screenshot reconstruction)

`README.md:1-45` (1920×1080 Google screenshot `Untitleddesign(10).png`, pixel-exact latlon-approx `:20-22`, 88041 sqm A–H 100+ rooms 550 auditorium `:26`); `manifest.json:1-51` (anchor 28.75257,77.49851, 11 facility classes, 12 labels Jayant…Pharmacy); `boundary.geojson` 11 KB 1 poly; `visible_features.geojson` 5.6 KB 12 pts; `boundary_points.json` 22 KB / `.csv` 6.4 KB (x_px/y_px/norm/lon/lat e.g. 546,416,0.2845,0.3855,77.49461,28.75356); `red_pixels.json` 309 KB; `boundary_mask.png` 11 KB; `boundary_overlay.png` 2.8 MB cyan QA.

## kiet_campuse_data/ (2.2 MB sanctioned survey)

16 jpeg (no 0.jpeg; 5.jpeg 181 KB largest, 12.jpeg 112 KB smallest; hands/ruler occlusions) + 16 `*_info.md` + `info.md` 12 KB master (`:1-141`): 2-sheet compounding Rev6 16/10/2024 1:400 khasra 277M/278O/280A (`:12-17`); plot 68756.00 net 68331.72 coverage 35%→23916.10 FAR 2.0→136663.44 parking req 20190/prov 20232.12 (`:42-56`); demolition C-1 184.78 (`:58`); setback 760.73 (`:64`); parking A–R 20232.13 (`:68`); layout A G+2 45×45.70 E G+5 40.23 Z G+8 26.80 D star 9.55 solar ~500 KW RWH+50 KL (`:74-95`); dup groups T1:2,12 T2:3,4 S1:5,6,15 E:8,9,11 K:7,13,16 unique 1,10,14 (`:99-116`).

## docs/ (specs + reports)

- `assumptions.md:1-26` — verified (13×20 DEM, OSM, GDA numbers, rain max 114.59 p99 37 `:5-8`); inferred (4 m roads, inlets, flow dirs `:12-14`); synthetic (sub-30 m relief, pipes, Manning, walls, outfalls, depths `:18-23`); verified=false tagging (`:25-26`).
- `simulation.md:1-45`, `drainage.md:1-28`, `hydraulics.md:1-37`, `validation.md:1-36`, `viewer.md:1-69`, `dataset_report.md:1-117` (v1.0 canonical: 360 rows, 515 MB, 4.28 CPU-h, mass max 1.6e-3 mean 2.8e-5, classes, 6 nets, severity, windows, quarantine 2 OOD>2 m, limits).
- `colab_generation.ipynb` — `run_v2 --prod-n 240 --ood-n 36` pipeline.
- `superpowers/plans/` 5 files (road-map, accurate-map, baseline-nowcaster, sih-demo, sih-inference) + `specs/` 3 files — plan history.

## random_info/ (560 KB external rain + theory)

- `daily_rainfall_2016_2026.csv` 127,927 B 3653 rows (date,rainfall,24h,48h,72h,7d) — grounds quotas (max 114.59 p99 ~37).
- `Ghaziabad_Rainfall_2021_2025.csv` 134,312 B / `ERA5_Land_...` 155,735 B / `GPM_IMERG_...` 130,472 B — 1827 rows each (system:index,date,rainfall,.geo).
- `urban_drainage_network` 14,303 B 192 lines — SWMM Saint-Venant + Manning 0.011–0.015, SWMManywhere, Rational Q=CIA, SewerTris/aiswmm; justifies synthetic inversion.
