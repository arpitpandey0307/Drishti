# 03.02 — dataset/ + models/ + space/ (ML side)

## dataset/ (API + v1 pipeline)

- `dataset/__init__.py:1` — empty marker.
- `dataset/ml_dataset.py:1-214` — Core ML API, scenario-level windows (no frame leakage). `STATIC_CHANNELS` 9 (`:25-26`: dem,slope,flow_accum_log,low_points,imperv,manning,is_road,is_building,in_domain); `DYNAMIC` (`:27`: rain,depth,velocity); `LEAD_STEPS_DEFAULT [1,2,4,6,8,12,18,24,36]×5min=5..180` (`:28`); `FLOOD_THRESHOLD 0.05` (`:29`). `FloodWindows.__init__` (`:44-64`, index (sid,t0,T)); `_static` (`:69-79`, log1p accum); `_graph` (`:81-88`); `get(idx,norm)` (`:90-139` → static (C,Y,X), dyn_hist (3,H,Y,X), future_rain (L,Y,X), node/pipe, blockage, target_depth (L,Y,X), mask, max_depth, ever_flood, ttf, vel, leads, spec); `g_target_ttf` (`:142-149`); `apply_norm` (`:152-168`); `numpy_batches` (`:171-178`); `collate` ragged (`:181-192`); `torch_dataset` nan→-1 (`:195-214`). Used `train_baseline.py:30`, `space/README.md:26`.
- `dataset/compute_normalization.py:1-84` — Train-only Welford (`:19-38`, stride>20000 `:28-29`); `compute(train,out)` (`:41-75`: dem/slope/imperv/manning/flow_log, rain/depth/vel, node/pipe); CLI (`:80-84`). Output `outputs/datasets/v1/normalization_train.json` (dem 219.76±3.36, rain 1.71±4.55).
- `dataset/merge_splits.py:1-94` — Multi-VM assembly. `main(manifests,h5s,out,ood)` (`:22-83`): dedupe (`:28-33`), groups `_v1_` (`:36-40`), copy STATIC_KEYS + gzip (`:59-64`), rewrite manifest (`:68-77`), verify (`:79-82`).
- `dataset/stats.py:1-92` — Balance. `severity` (`:19-26`: <0.05 no-flood/<0.15 minor/<0.40 moderate/else severe); `analyze` (`:29-83` + `dataset_v1_distributions.png` `:76`).
- `dataset/qc_plots.py:1-91` — `qc_scenario` 3-panel (`:13-50`); `auto_pick` per-class 2 (`:53-77`) → `outputs/figures/qc/*.png` 8 files.
- `dataset/verify_transfer.py:1-112` — Gate. `FILES` (`:17-18`); `sha256` (`:21-26`); `main` (`:29-104`): checksums, dedupe, readability (v1.0, dem/slope/accum/low, per-group rain/depth/vel/flooded/node/pipe/dem_delta/maxd/ttf), disjoint splits, quarantine, dataloader (`target_depth.shape[0]==9`).
- `dataset/generator/run.py:1-104` — Legacy v0. `run(split,n,seed,out)` (`:21-97`): load 5 YAML (`:22-26`), Twin (`:32`), nets (`:33`), suite (`:37`), simulate (`:54`) + checks (`:55-57`), gzip writes (`:61-69`) + attrs (`:71-74`), statics (`:82-85`); `_coerce` int64 fix (`:89-95`, see `outputs/gen_test.log`).
- `dataset/generator/run_v2.py:1-349` — Current v1.0 parallel. `MANIFEST_COLUMNS` 26 (`:23-27`); `_init` (`:32-43`); `_build_overrides` dem_delta N(0,0.05) (`:46-52`); `_lowpoint_center` (`:55-59`); `_run_one` (`:62-121`: bullseye `:71-72`, drain_eff `:76-78`, blockage `:82-93`, simulate `:96-98`, checks `:103-106`, quarantine merr>0.35, flood_frac `:107-109`); `_load/append_manifest` (`:125-141`); `_write_static` slope/accum/low + attrs v1.0 (`:148-164`); `_write_scenario` dem_delta/flooded (`:167-192`); `run(prod,ood,seed,out,workers,only)` (`:195-331`: suites `:206-208`, ProcessPool `:259`, quarantine `:285-290`, networks `:321-329`); CLI (`:336-349`).
- `dataset/schemas/hdf5_schema.md:1-84` — v0 spec (`:3-29`) + v1 deltas (`:32-57`: split files, dem_delta, recession_h, drain_eff/manning/dep/imperv/terrain_seed/ml_split).

## models/ + outputs/models/

- `models/__init__.py:1` — empty.
- `models/baseline_unet.py:1-40` — `BaselineUNet(in_ch=36,n_leads=9,base=32)` (`:12-13`); `_blk` Conv-ReLU×2 (`:6-8`); e1/e2/e3 (`:14-16`); pool (`:17`); up/d (`:18-22`); `forward` + F.pad align (`:24-37`); `count_params` (`:39-40`, ~476k). Input (B,30→36,110,160): 9 static+18 hist+9 future rain.
- `models/train_baseline.py:1-82` — `build_sample` concat (`:9-15`); `main` (`:18-78`): FloodWindows (`:31`), smoke 8 windows npz (`:33-44`), full N=min(len,2692) (`:52`), DataLoader (`:55-59`), Adam 1e-3 (`:62`), MSE+0.2·BCE (`:70`), save (`:77`). Defaults `--train/--val/--epochs 5/--batch 4/--out baseline.pt` (`:20-26`).
- `models/train_full.py:1-144` — Bulk. HIST=6, LEADS 9 (`:9-10`); STATIC_KEYS (`:11-12`); `load_split` (`:15-82`: norm `:28-35`, sid filter `:36`, window loop `:46`, h_flat `:56-61`, norm dyn `:65-77`, max_windows `:80-81`); `main` (`:85-140`: norm fallback `:93-95`, timing `:100-106`, val_rmse30/180 `:135-137`).
- Artifacts: `outputs/models/baseline_subset30.pt` 1.9 MB (Sep06 22:36), `baseline_full100.pt` 1.9 MB (Sep06 23:17).

## space/ (HF static demo source)

- `space/README.md:1-28` — Tracked index.html + windows/meta.json; gitignored onnx(.data) + w*.bin. Fetch via `api.route_nowcast._get` (`:11-17`); rebuild from `baseline_unet.py` + `Aman34243/drishti-flood-nowcaster` single-file ONNX (`:23-25`); windows from `ml_dataset:FloodWindows` + `build_sample` → float32 LE w*.bin 36×110×160 (`:26-27`).
- `space/index.html` (~6 KB) — ort.min.js@1.22.0, canvas viewer, SYNTHETIC banner, title `Drishti Flood Nowcast — SIH 26085`.
- `space/windows/meta.json:1` — leads [5..180]×9, 110×160×36, windows s0–s5 across val_v1_00213/00208.
- Live: `https://aman34243-drishti-flood-nowcast.static.hf.space/` + model repo `Aman34243/drishti-flood-nowcaster`. Verified 200s (`report.md:291-305`).
