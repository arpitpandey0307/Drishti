# KIET Flood-ML Dataset v1.0 — Report (SYNTHETIC training data, NOT observations)

All drainage is SYNTHETIC / inferred / unverified (`verified=false`) — never real
KIET infrastructure. All flood depths are model output, never observed flooding.
Physics engine unchanged from the validated simulator (8/8 tests pass);
Phase 3 added only scenario sampling, recession tails, and per-scenario
uncertainty plumbing. See `source.md` §§9-10.

## 1. Totals

| item | value |
|---|---|
| manifest rows | 360 (358 valid, 2 quarantined, 0 failed) |
| prod pool (train/val/test) | 324 = 240 stratified + 36 dry top-up + 48 long-dry top-up |
| train / val / test | 227 / 49 / 48 scenarios (scenario-level split, no frame leaks) |
| OOD (`dataset/ood/` layout → `outputs/datasets/v1/ood/`) | 34 valid + 2 quarantined |
| storage (HDF5 gzip) | 515 MB total: train 296 / val 57 / test 67 / ood 89 / quarantine 7 MB |
| per-scenario | ~1.4 MB compressed |
| simulator compute | 4.28 CPU-hours total; mean 43 s / median 38 s per scenario |
| mass conservation | max err 1.6e-3, mean 2.8e-5 (quarantine threshold 0.35) |
| generation wall time | ~3.5 h across 4 Colab VMs (2 preempted; resumed via manifest both times) |
| seeds | master 26085 (prod), +9999 (ood), 99991 (dry top-up), 77791 (long-dry) |
| versions | dataset v1.0, simulator v1.0, recorded in every HDF5 attr + manifest |

Resume/reproduce: `python3 -m dataset.generator.run_v2 --prod-n 240 --ood-n 36
--workers N` (skips manifest-marked IDs); Colab pipeline: `docs/colab_generation.ipynb`.
Final assembly from partial VMs: `python3 -m dataset.merge_splits ...` (dedupe by ID).

## 2. Compute sizing (why 240+36, benchmark-first per spec)

- Local PC: 4 CPU / 7.6 GB, 1.3 s per 5-min output step (~60 s/scenario).
- Colab CPU VM: 2 vCPU / 13 GB / 94 GB free, 0.57 s/step (~30-40 s/scenario).
- Colab T4 VM: Tesla T4 present, but the simulator is pure NumPy/SciPy CPU code —
  benchmarked 0.58 s/step, identical speed, same 2 vCPUs. GPU gives NO speedup
  for this physics; T4 quota was later exhausted, so the bulk ran on CPU VMs.
- ~1.4 MB/scenario → 360 scenarios ≈ 515 MB. Colab-scale ceiling for a follow-up:
  ~3000 scenarios/session (~12 h limit, ~4 GB) — resume with larger `--prod-n`.

## 3. Rainfall diversity (stratified: class quotas + Latin-Hypercube over duration/σ/speed)

Classes (grounded in local CSV stats: daily max 114.59 mm, p99 ~37 mm):
trace 65 (18%: 17 + 24 dry + 24 longdry) / light 63 / moderate 73 / heavy 70 /
extreme 48 / OOD 34 (150-200 mm, 6-8 h, 10-15 m/s storms — all beyond train range).
Temporal: uniform 28.5%, peaked 25.4%, front_loaded 19%, back_loaded 13.7%,
multi_peak 13.4%. Spatial: uniform 24.3%, gaussian 24%, gradient 22.1%,
moving 16.8%, multi 12.8%. Durations 0.5-6 h (+ dry tails to 3 h); ~57% of main
pool carries a 0.5-2 h dry recession tail (drain-down dynamics).

## 4. Drainage / blockage / terrain uncertainty (all synthetic, labelled)

6 network variants × drain_eff 0.7-1.35 (0.5-0.65 OOD) pipe+inlet multiplier ×
inlet/manning/depression/impervious jitter × DEM N(0, 0.05 m) deltas stored
per-scenario (`dem_delta`; base verified terrain untouched).
Blockage: none 40.8% (all top-ups are free-drainage by design), 0.1: 11.7%,
0.25: 10.3%, 0.5: 9.8%, 0.6: 4.7% (OOD), 0.75: 7.8%, 0.85: 4.7% (OOD),
0.9: 10.1%; modes pipe_uniform 48% / inlet_subset 24% / outfall_restricted 28%.
Edge classes (36): free-drain extremes, blocked-moderate, low-point bullseye,
rapid surcharge — including moderate-rain-floods / heavy-rain-doesn't pairs.

## 5. Scenario classes & balance

Scenario-level severity (max depth): no-flood 9.5% (34), minor 11.2% (40),
moderate 15.4% (55), severe 64% (229). The campus ponds readily, so raw counts
skew deep — what matters for training is window balance:

Full-lead windows (30-min history → 5..180-min targets, hist=6, leads 1..36):
train 2692 (no-flood 12.4% / minor-moderate 35.0% / severe 52.6%),
val 542 (2.0 / 44.3 / 53.7), test 606 (18.2 / 28.5 / 53.3), OOD 1861.
154/324 prod scenarios are too short (T<42) for +180-min targets — they train
short leads only. Val no-flood windows are thin (11); test coverage is the
binding metric and is healthy. Slow-accumulation, rapid-onset, moving-storm,
multi-pocket, surcharge, and drain-down cases all present (see QC PNGs).

## 6. Splits & OOD

70/15/15 by complete scenarios, stratified by (rain class, blocked?) —
168/37/35 for the main pool, plus top-ups 59/12/13 → final 227/49/48.
Test holds unseen combos of rain × movement × profile × pattern × blockage ×
drainage. OOD: 34 scenarios, every one out-of-range on ≥2 factors.
Zero scenario overlap across files (verified). Normalization
(`normalization_train.json`) computed from TRAIN only (193→ final 227 scenarios).

## 7. Validation & quarantine

Auto-checks per scenario: NaN/Inf, negative depth, max depth ≤ 2 m, velocity ≤
3 m/s, mass err ≤ 0.35, graph validity. 2 OOD scenarios (181/183 mm rain →
2.0-2.5 m depths) quarantined to `kiet_flood_quarantine.h5`, never trained on.
0 failed. 3 Colab preemptions survived via CSV-manifest resume + local backups;
deterministic IDs/seeds made multi-VM merge exact (dedupe by ID, 0 missing).

## 8. ML API

`dataset/ml_dataset.py`: `FloodWindows` (static/dynamic separation, 9 static +
3 dynamic channels, graph pipe/node states, 9 leads 5-180 min, primary targets
depth+mask, secondary max/ever-flood/TTF/velocity/surcharge), numpy batches +
optional torch wrapper, `collate` handling ragged graphs. Sanity-checked on all
4 files. `dataset/compute_normalization.py` (train-only), `dataset/stats.py`
(balance + `outputs/figures/dataset_v1_distributions.png`),
`dataset/qc_plots.py` (8 representative PNGs in `outputs/figures/qc/`),
`dataset/verify_transfer.py` (checksums, readability, disjointness — PASS),
`dataset/merge_splits.py` (multi-VM assembly).

## 9. Files (local PC = final home)

`outputs/datasets/v1/`: `kiet_flood_{train,val,test}.h5`, `ood/kiet_flood_ood.h5`,
`kiet_flood_quarantine.h5`, `dataset_manifest.csv` (360 rows), `kiet_networks_v1.json`
(6 synthetic networks), `normalization_train.json`, `SHA256SUMS`.
Legacy v0 `outputs/datasets/kiet_flood_test.h5` (viewer) untouched.
Schema: `dataset/schemas/hdf5_schema.md`. Next: model training (not started).

## 10. Known limits

Severe-heavy by max-depth; campus ponds easily (single-pocket 40 cm = "severe").
Val no-flood windows thin (2%). OOD extremes can exceed solver plausibility
(2 quarantined at >2 m — validation working as designed). Peaked profiles
25% (edge-case oversampling). Drainage entirely synthetic. No IDF fitting, no
calibration to KIET soils, no river backwater, rooftops ignored.
