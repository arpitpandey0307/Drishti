# 06 — Data / Datasets / Sources

## 1. Static GIS (data/, 784 KB)

See `03_module-deep-dives/05_data-terrain-campus.md`. Runtime readers: `twin.py:125-132` (buildings/boundary/roads), `twin.py:96` (terrain_grid), HTML `fetch()` (all geojson/png). Rebuilders: `scripts/build_road_data.py` (Overpass), `scripts/build_accurate_geojson.py` (affine). Schema notes: roads LineString {name,highway,service,access,tunnel,ref,osm_id}; accurate {kind sanctioned_building/label_accurate/boundary_khasra, sanctioned_name,floors,footprint_sqm,confidence,osm_match,real_name}; centroids {name,lat,lon,floors,area,source}.

## 2. Terrain lineage (FACT)

`terrain/raw/N28E077_FABDEM_V1-2.tif` 23 MB (archival FABDEM) + `kiet_terrain/data/terrain/raw/Copernicus_DSM_COG_10_N28_00_E077_00_DEM.tif` 40 MB (GLO-30 DSM 3600² float32 1″, tiepoint 77E/29N) → clipped 13×20 float32 nodata −9999 100 valid 214.6786–231.3076 mean 219.2223 → `data/terrain_grid.json` 21 KB (browser) → `twin.py` 110×160 @5 m + micro-relief. OSM boundary way 835252667 ~83 k m². Limits: 30 m DSM ±4 m, DSM≠earth, max 231.3 likely building hit, slope_deg null in grid JSON (only in tif), smoothing display-only (`report.md:29-36`, `docs/assumptions.md`).

## 3. Sanctioned campus (kiet_campuse_data/, 2.2 MB, gitignored raw)

Rev6 16/10/2024 1:400 khasra 277M/278O/280A; plot 68756.00 net 68331.72 coverage 35%→23916.10 FAR 2.0→136663.44 parking 20190/20232.12; A G+2 45×45.70 … Z G+8 26.80; affine 3–5 m UNVERIFIED (`kiet_campuse_data/info.md:1-141`).

## 4. External rainfall (random_info/, 560 KB)

`daily_rainfall_2016_2026.csv` 3653 rows (provenance unknown; max 114.59 p99 ~37, 24 d >50 mm) + 3× Ghaziabad 2021–2025 1827 rows (GPM=NASA, ERA5=ECMWF per filenames NOT verified). Used for ranges only, never calibrated (`source.md:111-116`). Plus `urban_drainage_network` theory memo (SWMM/Manning/Rational).

## 5. HDF5 datasets (outputs/, gitignored local-only)

### v0 (viewer-only)
`kiet_flood_test.h5` 17 MB 10 scn (`scenario_NNNN`) + networks 77 KB + manifest; `ood/kiet_flood_ood.h5` 89 MB. Per-scenario: rain/depth/velocity/flooded/node_depth/pipe_flow/capacity/surcharge/overflow/blockage/ttf/maxd + spec/mass attrs; statics dem/manning/imperv/domain/road/bld/X/Y. Schema `dataset/schemas/hdf5_schema.md:3-29`.

### v1.0 (canonical, 515 MB, `docs/dataset_report.md`)
360 rows (`dataset_manifest.csv` 76 KB, 26 cols): 324 prod (240 main + 36 dry ids10000+ + 48 longdry ids20000+) → train/val/test 227/49/48 + 34 OOD + 2 quarantined (OOD >2 m) + 0 failed. Files train 296/val 57/test 67/ood 89/quarantine 7.0 + networks 153 KB + norm 976 B + SHA256SUMS. Per-scenario adds dem_delta, slope/flow_accum/low_points statics, recession_h/drain_eff/manning_scale/dep_scale/imperv_open/terrain_seed/ml_split attrs. Windows (HIST 6 → LEADS 9): train 2692/val 542/test 606/OOD 1861; no-flood-target 12/2/18%. Mass max 1.6e-3 mean 2.8e-5; 4.28 CPU-h mean 43 s. ID `<split>_v1_NNNNN`. Norm TRAIN-only. Fetch: `tools/fetch_demo_data.py` ← `Aman34243/drishti-demo-data`.

## 6. Planner + viewer + Space binaries

- `planner/storms/` 744 KB committed: 2 storms × (meta.json + 10 depth_*.bin int16 mm 110×160). storm-a val00213 (t0 5, 97.4 mm/4.86 h, blk 0.5); storm-b test00224 (t0 10, 92.5 mm/2.77 h, blk 0.75). Model `Aman34243/drishti-flood-nowcaster` (meta `model`, `kind:model-prediction (synthetic demo)`).
- `outputs/viz/` local (10 v0 + 2 v1demo, ~6 MB/scn int16+b64) + `outputs/viz-demo/` 5.3 MB committed (T=15+20). Regenerate: `export_viz --split test` / `--split v1demo --max 2`; verify `validate_viz` ALL PASSED.
- `space/windows/` gitignored w*.bin (float32 LE 36×110×160) + meta.json tracked; `drishti.onnx(.data)` gitignored, on HF model repo. `outputs/models/*.pt` 1.9 MB gitignored.
- `outputs/figures/` 2 scenario PNGs + distributions + 8 QC PNGs; `outputs/geojson/synthetic_drainage_v0.geojson` 29 KB.

## 7. Limitations (for paper §Method)

No sensors/calibration/mapped drains; DEM 30 m DSM ±4 m; sub-30 m relief interpolated; entire network synthetic (conf 0.3–0.7); Horton/Manning/depression literature-typical uncalibrated; buildings=walls rooftops ignored; outfalls free no backwater; storms plausible-synthetic not IMD (no IDF); blockage scenario knobs; equirect sub-m error; all depths MODEL OUTPUT (`source.md:148-163` Synthetic Assumptions ×11).
