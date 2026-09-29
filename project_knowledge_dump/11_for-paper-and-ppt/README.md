# 11 — For Paper & PPT (copy-paste ready)

## Bullets — problem & approach

- Campus-scale pluvial flood nowcasting (0–3 h, 5–180 min leads) for KIET Ghaziabad (28.7523N 77.4985E) with zero sensors/drains surveyed.
- Solution: plausible-but-synthetic digital twin (160×110 @5 m) → mass-conservative simulator (diffusive-wave storage-cell + Manning-pipe DAG + Horton) → stratified 360-scenario dataset (515 MB) → 476k U-Net nowcaster (36 ch → 9 leads) → browser ONNX demos + safe routing.
- Honesty: all drainage SYNTHETIC (`verified=false`); 30 m DSM ±4 m broad-relief-only; all depths MODEL OUTPUT.

## Bullets — methods (1 line each)

- Terrain: Copernicus GLO-30 DSM 13×20 (100 valid 214.68–231.31 m) → bilinear 160×110 @5 m + ±0.075 m micro-relief; D8 + p90 low-points.
- Surface: `q=h_flow^(5/3)/n·√S·dx`, S≤0.05, 1/8-volume limiter, dt=2 s ×150, walls=buildings, vel proxy clip [0,3].
- Drainage: terrain+road DAG ~50 inlets 2 outfalls; `Qcap=(1/n)A R^(2/3)√S`; inlet `min(cap·(1−0.8blk),ponded·dx²/dt)` ×0.3 surcharged; node 1 m²×1.5 m; blockage 0–90% ×3 modes.
- Rain: temporal×spatial 5-min, 10–150 mm/0.5–6 h (OOD 150–200/6–8 h), wet-mean normalised + recession tails.
- ML: HIST 6 → LEADS 9 (5..180 min); loss MSE+0.2·BCE(≥0.05 m); Adam 1e-3; train-only norm; scenario splits 227/49/48 +34 OOD.

## Bullets — results

- Mass ~1e-8 typical (v1 max 1.6e-3 mean 2.8e-5, quarantine 0.35); 8/8 physics tests; blockage 0→50% drain 12.2→8.2 mm pond 44.5→48.5 mm; low-points ~2×.
- Dataset: 358 valid +2 quarried; windows 2692/542/606 +1861 OOD; severity no-flood 9.5/minor 11.2/moderate 15.4/severe 64%.
- Model: 0.1374→0.1362 (100 scn 10 ep); val RMSE +30 min 0.048 m / +180 min 0.049 m; ONNX maxdiff 3e-07; live val00213 +30 max 0.101 m 175 m² route 745 m.
- Demos: Space live; planner selftest 64 cm/DANGER 5.30 km; viewer validator ALL PASSED; headfull play+inspector+CSVs PASSED.

## Figures list (path → caption suggestion)

1. `preview_terrain_map.png` 692 KB — 2D terrain+roads + low pockets.
2. `preview_3d_browser.png` 119 KB — 3D world screenshot (headless-Chrome proof).
3. `preview_campus_zoom.png` 748 KB — campus zoom.
4. `preview_flood_viewer_surcharge.png` 438 KB — viewer t+5:05, 21 surcharged (causal chain).
5. `outputs/figures/dataset_v1_distributions.png` 47 KB — 6-hist balance (rain/maxd/flood-frac/duration/blockage/sim-time).
6. `outputs/figures/scenario_0003.png` 162 KB / `scenario_0009.png` 178 KB — 6-panel scenario (DEM/landcover/network/rain/maxd/extent).
7. `outputs/figures/qc/*.png` ×8 — 3-panel QC (max-depth/DEM/hyetograph-vs-ponding).
8. `outputs/viz/test_scenario_0009` frames — animation source (depth 0–50+ cm).
9. `planner/storms/` heat overlay — NOW→+180 planner screenshot (retake live).
10. Space screenshot — predict+route (retake live).

## Tables (ready)

**T1 configs:** terrain 160×110@5 m EPSG:32643/4326 28.7523/77.4985; surface dt 2 s h_flood 0.05 vel 3.0; Horton road 5/1/open 35/8/dep 1.0/2.5 (live k 2.2); pipes D 0.3–1.2 n 0.013 S 0.002–0.05 inlets 60/15 m nodes 1 m²×1.5 m cap 0.05; rain 10–150 mm 1–6 h step 5; sim seed 26085 nets 6 quarantine 0.35.
**T2 dataset:** 360 rows = 240 +36 dry +48 longdry +36 OOD-plan → 227/49/48 +34 OOD +2 quar; 515 MB (296/57/67/89/7); windows 2692/542/606/1861; classes trace 65/light 63/moderate 73/heavy 70/extreme 48/OOD 34.
**T3 model:** BaselineUNet 36→9 base32 476,297; MSE+0.2BCE Adam 1e-3 b4/16 e5/10; subset30 353/103 win 8 ep 0.1373→0.1363; full100 1165/542 win 10 ep 0.1374→0.1362 RMSE 0.0482/0.0485.
**T4 thresholds:** flood 0.05; WATCH 0.15/WARNING 0.30/severe 0.40; planner avoid ≥0.30 penalty 10×; caps depth 2.0 vel 3.0 mass 0.35.

## Viva Q&A (5 likely)

1. Real drains? — None; synthetic DAG labelled verified=false; swap schema in docs/drainage.md:26-27.
2. 30 m DEM for 5 m sim? — Broad fall only; sub-30 m interpolated (assumption §10-1); LiDAR needed for engineering.
3. Mass vs calibration? — No observations; mass (~1e-8) + 8 tests + gates are trust anchor.
4. Why CPU not GPU? — NumPy sim benched identical (T4 0.58 vs CPU 0.57 s/step); model small (476k) trains CPU-viable.
5. OOM full-227? — Bulk 6.8 GB; streaming DataLoader planned; 100-scn scale-up already validates trend.
