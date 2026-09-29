# knowledge.md — Drishti: single source of truth (read this first)

> Handover document for a new teammate. Covers what we're building, what's done,
> how everything works, why decisions were made, and what remains.
> Every technical claim verified against the repo on 2026-09-06.
> **Implemented vs planned** and **real vs inferred vs synthetic** are marked
> explicitly throughout. Formula sources live in `source.md`.

Standing repo rule (`AGENT.md`): log what you do and how you solved problems in
`report.md` as you work.

---

## 1. What this project is

**Drishti** started as interactive KIET-campus maps and grew into an **urban-flood
digital twin for SIH 26085**. Two tracks share one repo:

| Track | Status | Entry point |
|---|---|---|
| A. Campus maps (2D roads/terrain, 3D terrain world) | ✅ Done, deployed | `index.html` → `kiet_road_map.html`, `kiet_terrain_map.html`, `kiet_3d_standalone.html` |
| B. Physics flood simulator + synthetic ML dataset | ✅ Simulator + viewer + dataset v1.0 done | `simulation/`, `dataset/`, `flood_viewer.html`, `outputs/datasets/v1/` |
| C. Flood-nowcasting ML model | 🔶 **Baseline trained** (30-scn smoke + 100-scn scale-up on T4; full 227 open) | `models/`, `outputs/models/`, `docs/superpowers/plans/2026-09-06-baseline-nowcaster.md` |

Live deployments (Track A): `https://drishti-sand.vercel.app` (Vercel) and
`https://drishti-cl8r.onrender.com` (Render) — static hosting (`vercel.json`,
`render.yaml`, `index.html` landing). The flood viewer is **not** linked from the
landing page and needs a local HTTP server (it uses `fetch()`).

The end goal of Track B/C: predict street-level flooding **0–3 hours ahead** from
forecast rainfall + terrain + surface + drainage state. No sensors, no calibrated
model, and unmapped underground drainage exist — so we generate **mass-conservative
synthetic training data** from a plausible (not calibrated) physics twin, and will
train the nowcaster on it later.

---

## 2. Repo map (what lives where)

```
simulation/            THE physics engine (Track B core)
  terrain/twin.py        5 m grid, DEM upsample, masks, D8 flow/accumulation/low-points
  surface/runoff.py      diffusive-wave storage-cell solver (per-2 s-substep)
  surface/infiltration.py  Horton + SCS-CN class — NOTE: never instantiated (dead path, §4)
  hydraulics/simulate.py   coupling loop: rain→infil→surface⇄drainage, recession, overrides
  hydraulics/pipes.py      DrainageState: inlet capture, routing, surcharge, blockage
  drainage/network.py      synthetic network synthesis (DAG to outfalls)
  rainfall/generator.py    temporal×spatial storm fields
  scenarios/spec.py        v0 random sampler (legacy) · suite_v2.py  v1 stratified sampler
  validation/checks.py     per-scenario quality gates
dataset/               dataset tooling (Phase 3)
  generator/run.py       v0 generator (JSON manifest, 3 network variants)
  generator/run_v2.py    v1 generator (CSV manifest, parallel, quarantine, splits, OOD)
  ml_dataset.py          FloodWindows dataloader (numpy-first, torch-optional)
  compute_normalization.py  train-only normalisation stats
  stats.py / qc_plots.py / verify_transfer.py / merge_splits.py
  schemas/hdf5_schema.md   v0 + v1 HDF5 layout
models/                Track C baseline (2026-09-06, see §6.1)
  baseline_unet.py       U-Net base=32, 476k params, in 36ch → 9 leads, 110x160
  train_baseline.py      MSE+BCE trainer + numpy smoke mode
  train_full.py          fast bulk preload + per-lead RMSE eval
tests/test_baseline_unet.py  forward-shape test (needs torch; skipped locally)
api/                   SIH demo routing (2026-09-06, see report §19)
  route.py               A* safe_route(depth, valid, start, end) on 5 m grid
  route_nowcast.py       HF-Space fetch → onnxruntime predict → safe_route → JSON (report §20)
tests/test_route.py      avoids-flood + sealed-blocked cases (2/2)
tests/test_route_nowcast.py  Space-layout fixture, no network (1/1)
config/                terrain.yaml, hydraulics.yaml, drainage.yaml, rainfall.yaml,
                       simulation.yaml (versions, counts, tolerances)
tests/test_simulator.py  8 physics/graph tests (older split files deleted; .pyc ghosts remain)
data/                  vendored GeoJSON + terrain_grid.json + 3D payload (tracked)
kiet_terrain/          Copernicus package + OSM boundary (raw 40 MB tif lives here;
                       the two *.zip files at root are gitignored redundancies)
kiet_campuse_data/     16 site photos + *_info.md transcription (gitignored; derived
                       GeoJSON in data/ IS tracked) — sanctioned GDA plan Rev 6
random_info/           rainfall CSVs + urban_drainage_network (SWMM research note, no ext.)
visualization/data_adapter/  export_viz.py + validate_viz.py (H5→browser bundles)
                       (controls/layers/viewer/animation/ are EMPTY stubs — ignore)
tools/viz.py           matplotlib scenario PNGs (DEM/landcover/network/rain/depth/extent)
scripts/               map builders + check_* validators (Track A; flood code doesn't use them)
flood_viewer.html      zero-dependency canvas viewer for v0 test split (Track B UX)
docs/                  simulation/drainage/hydraulics/assumptions/validation/viewer.md,
                       dataset_report.md (v1.0 numbers), colab_generation.ipynb,
                       superpowers/{plans,specs}/ (Track A design docs)
outputs/               GITIGNORED, local-only: datasets/{v1,…}, viz/, figures/,
                       geojson/ (synthetic_drainage_v0.geojson export), gen_test.log
flood/                 DEAD — only stale .pyc, sources deleted. Do not use.
terrain/{processed,products}/, drainage/, synthetic/{seed11,quarantine}/
                       legacy/experiment leftovers, not wired into anything.
report.md / source.md / environment.md / knowledge.md (this file)
```

**Git state warning (2026-09-06):** Phase 2/3 work (`config/`, `dataset/`,
`flood_viewer.html`, all `docs/*.md`, `environment.md`, this file) is
**uncommitted** (`??` in `git status`); `report.md`, `README.md`, `.gitignore`
have uncommitted edits. Commit before restructuring.

**Environment:** Python 3.12, `pip install h5py pyyaml matplotlib scipy`
(numpy stock). No torch (dataloader is numpy-first by design). Runtimes used:
local PC (4 CPU/7.6 GB) + Google Colab CPU VMs via `colab` CLI
(see `environment.md`, `docs/colab_generation.ipynb`).

---

## 3. Getting started (commands a teammate actually needs)

```bash
pip install h5py pyyaml matplotlib scipy          # one-time
python3 -m pytest tests/test_simulator.py -q      # 8 physics tests (~2 min)
python3 -m dataset.generator.run_v2 --smoke --workers 2   # 4 scenarios, outputs/datasets/smoke/
python3 -m http.server 8123                       # then open /flood_viewer.html (needs v0 viz bundles)
python3 -m visualization.data_adapter.export_viz --split test
python3 -m visualization.data_adapter.validate_viz   # must print ALL CHECKS PASSED
python3 -m dataset.stats --manifest outputs/datasets/v1/dataset_manifest.csv
python3 -m dataset.verify_transfer --dir outputs/datasets/v1
```

Resume a killed generation (never regenerates done IDs):
`python3 -m dataset.generator.run_v2 --prod-n 240 --ood-n 36 --workers N`
Scale up: raise `--prod-n` (Colab ceiling ≈ 3000/session). Merge multi-VM partials:
`python3 -m dataset.merge_splits --manifest-in … --h5-in … --ood-in … --out-dir …`.

---

## 4. The physics engine (exactly as coded)

### 4.1 Terrain twin (`simulation/terrain/twin.py`)

Real backbone: `data/terrain_grid.json` — Copernicus GLO-30 DSM, 13×20 @ ~30 m,
100 valid cells 214.68–231.31 m, ±4 m accuracy, DSM≠bare earth (independently
re-verified from the raw GeoTIFF, `report.md` Exp1). Processing: NaN→nearest fill,
bilinear upsample to **160×110 @ 5 m**, + seeded micro-relief `U(−0.075,+0.075)` m
→ `dem_source="synthetic-upsampled"`. Masks: `in_domain` (OSM way 835252667,
~83k m²), `is_building` (sanctioned footprints), `is_road` (≤4 m of OSM
centerlines), `is_open`. Roads n=0.015/imperv 1.0, open n=0.045/imperv 0.35
(Chow-typical, uncalibrated). D8 flow directions, high→low accumulation,
`low_points` = top-decile accumulation (tests prove ~2× ponding). Local
equirectangular metres about (28.7523, 77.4985), labelled EPSG:32643; grid
`row0 = north`; `X, Y` in metres.
*Sources: Copernicus DEM handbook via Copernicus Data Space (DLR/Airbus,
TanDEM-X/GLO-30, ±4 m LE90, DSM≠DTM); OSM roads/buildings/boundary;
GDA sanctioned Rev-6 plan for the 17-block list. D8/accumulation is standard
raster-hydrology method, implementation-local (no external citation claimed).*

### 4.2 Surface flow (`simulation/surface/runoff.py`) — diffusive wave, Bates & De Roo 2000

Full shallow-water equations track inertia (local + convective acceleration),
which matters for dam breaks and steep flash floods but costs small timesteps
and solves shock fronts our 5 m synthetic-terrain campus never credibly resolves.
For slowly-varying pluvial ponding, gravity ≈ friction at every instant, so the
momentum equation collapses to a diagnostic velocity (no time derivative) —
the **diffusive wave**. That's the whole bet: trade inertial shocks (which
Dottori & Todini 2012 show a diffusive model misses, while bulk depths/extents
still match) for speed (~0.6 s/step) and stability on coarse grids:
`V = −R^(2/3)/(n·|∇zs|^½)·∇zs`, `∂h/∂t = ∇·(β∇zs) + q`.
Coded per 2 s substep: `h_flow = max(ws₁,ws₂)−max(z₁,z₂)`; slope capped
**S ≤ 0.05** (DSM-noise guard); `q = h_flow^(5/3)/n·√S·dx` along `sign(Δws)`;
**no face moves > 1/8 upwind-cell volume** (`runoff.py:39-46`); update
`h += dt·(R−I)/3.6e6 − dt·(sink−return) + dt·Qnet/dx²`, floored at 0.
The `h^(5/3)` comes from Manning's `V=(1/n)R^(2/3)√S` with wide-channel `R≈h_flow`
(FHWA HDS-3). Buildings/outside-domain are **no-flow walls**; velocity is an
ML-feature proxy (`|Qnet|/max(max(h₂,h)·dx,ε)`, clipped [0,3] m/s — not a
momentum solve; line 60 holds a dead `if False` branch, harmless quirk).
*Sources: Bates & De Roo 2000, J. Hydrology 236 (LISFLOOD-FP storage-cell +
flow-limiter concept); HEC-RAS 1D/2D diffusive-wave reference (canonical V form);
IWA 2017 urban-pluvial paper (diffusive+Manning justification, `Sf=n²V²/R^(4/3)`);
Dottori & Todini 2012, Hydrol. Processes (bulk-depth validity + building proxy);
Manning n table Chow 1959 via TxDOT; HDS-3 for the SI Manning form — all §2/§4
of source.md.* The 0.05/1/8/dt=2 s numbers themselves are engineering guards in
our code, not literature values.

### 4.3 Infiltration — READ THIS (two paths, one live)

Physically, Horton says: dry soil drinks fast (`f0`), decays exponentially as
pores fill, and asymptotes to the saturated rate (`fc`) — `cap = fc +
(f0−fc)·e^(−k·t)`, actual `f = min(cap, rain)`. So roads (5→1 mm/h) shed almost
everything while open ground (35→8 mm/h) absorbs early storm volume and then
gives up — that saturation collapse is what creates late-event ponding even at
constant rain. Our classes are literature-typical, NOT KIET soil measurements
(SWMM guidance: Horton's output is most sensitive to `fc`, so the saturated rate
is the one worth field-measuring if we ever calibrate).
The **live path is inline Horton in `simulate.py:63,83`** with a **hardcoded
`kk = 2.2`** for all classes. Consequence: the config `k_per_h`
values (2.0/2.5/1.0) are **silently unused**, and `surface/infiltration.py`
(`Infiltration` class incl. incremental SCS-CN `Q=P²/(P+S)`, `Smax=25400/CN−254`
mm — the metric form of SWMM's `1000/CN−10` inches — plus Akan & Houghtalen
per-step form) is **never instantiated — dead code**. SCS-CN is
implemented-but-unwired, not "an option". Depression storage (road 1.0 /
open 2.5 mm — SWMM separates it from infiltration, grass ≈2.5 mm) fills before
ponding and never drains (mass sink). Effective rain = `max(rain−infil,0) −
to_depression`.
*Sources: EPA SWMM Ref Vol I – Hydrology, Rossman & Huber 2016 (Horton,
Green-Ampt, SCS-CN, depression storage); IWA infiltration-methods comparison
(Horton-default choice + fc-sensitivity guidance); swmm5.org InfoSWMM notes
(SCS-CN incremental steps); HEC-RAS infiltration reference (parameter context);
Manning-table values §4 of source.md.* Green-Ampt/Holtan were researched and
deliberately not implemented (Holtan needs soil-moisture + ET accounting).

### 4.4 Drainage — synthetic network + 1D hydraulics (all `verified=false`)

Network (`drainage/network.py`, SWMM node-link concept): score = accumulation +
low-point bonus + road proximity → greedy 15 m-exclusion picking (~50 inlets) →
2 lowest-ground outfalls → **downstream DAG** (each node → strictly
outfall-closer node; trunk fallback D=1.0 m) — no trapped cycles. Diameters
0.25–1.2 m, concrete n=0.013 (Chow 1959), slopes ∈ [0.002, 0.05]. **6 variants**
in v1.0. Replacement path: drop same-schema real JSON, set `verified=true`.
Hydraulics (`hydraulics/pipes.py`, SWMM Vol II): `Qcap=(1/n)·A·R^(2/3)·√S`
(HDS-3); inlet `min(cap·(1−0.8·blk), ponded·dx²/dt)` (surcharged ×0.3); routing
capped by `Qcap·(1−blk)`; node storage 1 m²×1.5 m; free outfalls; **surcharge
overflow returns to the surface same step** (mass-exact). Blockage 0–90% ×
`pipe_uniform` / `inlet_subset` / `outfall_restricted`.
Honesty note: real SWMM routes conduits with the full 1D Saint-Venant dynamic
wave; we use Manning capacity caps + single-pass downhill routing instead — a
deliberate simplification for event-scale pluvial flow in a small synthetic
network (fast, stable, and mass-closed by construction). Pressurised/backwater
transients inside pipes are therefore NOT modelled; what the ML model sees is
capacity-limited conveyance + node ponding + surface return, which is the
behaviourally relevant part for street flooding.
*Sources: EPA SWMM 5.1 manual (node-link architecture, surcharge/blockage
concepts — no code copied); SWMM Ref Vol II – Hydraulics, Rossman 2017
(Manning conduit friction, node continuity + storage, surcharge above rim);
FHWA HDS-3 (SI Manning + circular-pipe `A=πD²/4, R=D/4` capacity); Chow 1959
n=0.013 concrete; `random_info/urban_drainage_network` background note on
Saint-Venant vs SWMM practice.*

### 4.5 Rainfall (`rainfall/generator.py`)

Temporal {uniform, peaked, front/back-loaded, multi-peak} × spatial {uniform,
gaussian, moving (`pos=c+v·(t−T/2)`, 2–10 m/s train / 10–15 OOD), gradient,
multi-cell}, 5-min steps; totals 1–150 mm / 0.5–6 h train, 150–200 mm / 6–8 h
OOD (local CSV stats: daily max 114.59 mm, p99 ~37). Normalised so **spec total
= wet-cell mean** (rooftops excluded). v1 honours spec σ/speed/dir/bullseye.
Why these shapes: uniform = stratiform all-day rain; peaked = SCS-like triangular
burst; front/back-loaded = exponential arrival/departure of the monsoon core;
multi-peak = successive cells; gaussian = isolated thunderstorm; moving =
squall line crossing the campus (the transit is centred mid-event by
construction); gradient = orographic/directional bias; multi-cell = scattered
convection. No IDF curve was fitted — ranges only, never design storms.
*Sources: in-repo CSVs (`random_info/`, provenance unknown — ranges only, §6 of
source.md). Realism anchor: spec totals spot-checked against p99/max.*

### 4.6 Coupling + mass (`hydraulics/simulate.py`)

Per 5-min step → 150×2 s substeps: Horton → depression → effective rain →
`DrainageState.step` → `step_surface` → assert finite/non-negative. Dry
**recession tails** appended post-normalisation (totals exact). Per-scenario
overrides (drain_eff, DEM delta, manning/depression scales) change no physics;
all recorded in spec JSON. **Identity:**
`rain = infiltration + depression + ponding + discharge + node_storage`
(~1e-8 typical; v1.0 max 1.6e-3, mean 2.8e-5; quarantine at 0.35).
Why mass is the trust anchor: with no observations to calibrate against, closure
is the only proof the coupling has no leaks or creations — every bug in §10's
trail was caught or confirmed by this identity first.
*Sources: SWMM 5.1 event-simulation framing (subcatchment→inlet→conduit→outfall
accounting); SWMM Vol II node continuity. The 5 cm flooded threshold, 3 m/s
velocity cap, and 0.35 quarantine tolerance are project conventions, not
literature values.*

---

## 5. Real vs inferred vs synthetic (ledger)

**Real:** 13×20 DEM values · OSM geometry (not field-checked) · sanctioned
plot/coverage/FAR numbers · rainfall CSV *ranges* (provenance unknown) · FABDEM
tile in `terrain/raw/` (reference only — twin uses the DSM package, not FABDEM).
**Inferred (0.4–0.7):** landcover rasterization · inlet positions · D8 directions.
**Synthetic (never cite as measurement):** sub-30 m relief · entire pipe network ·
infiltration/Manning/depression params · blockage · all storms · all flood depths ·
recession tails · OOD extremes. Labelling enforced in code/configs/GeoJSON/HDF5/
figures (`verified=false, source=synthetic/inferred`).

---

## 6. Dataset v1.0 (`outputs/datasets/v1/`, 515 MB — the deliverable)

**How built:** stratified sampler (`suite_v2.py`: class quotas + LHS over
duration/σ/speed — LHS puts exactly one sample per univariate stratum, so rare
corners (extremes, bullseyes) are covered with far fewer runs than Monte Carlo;
*source: `scipy.stats.qmc.LatinHypercube` docs, method of McKay et al. 1979 via
those docs' references*) → `run_v2.py` (CSV-manifest
resume, parallel workers, quarantine file, versioned attrs) → Colab CPU VMs
(T4 benchmarked identical 0.58 s/step — NumPy can't use GPUs) → 3 preemptions
survived via resume + snapshot backups + deterministic-ID merge → 2
analysis-driven top-ups (dry 36, long-dry 48) → train-only normalisation.
Full numbers: `docs/dataset_report.md`.

**Contents:** 360 rows: 358 valid + 2 quarantined (OOD >2 m) + 0 failed.
Prod 324 → train/val/test **227/49/48 scenarios** (whole scenarios, stratified,
zero cross-file overlap — verified). OOD 34. Windows (6-step history → 9 leads
5–180 min): 2692/542/606 train/val/test, 1861 OOD; no-flood-target share
12/2/18% (val thin — test is the binding metric). Per scenario: rain, depth,
velocity, flooded (≥5 cm), node_depth, pipe_flow/capacity, surcharge, overflow,
blockage, dem_delta (exact jittered terrain = dem+dem_delta), max_depth,
time_to_flood, spec/mass attrs. Static root grids incl. slope/flow_accum/
low_points. Manifest columns: id, seed, split, status, all parameters,
sim_time_s, validation, mass_err, max_depth, flood_frac, file_path, errors.

**ID schemes (do not confuse):** v0 `scenario_NNNN` (legacy viewer file
`outputs/datasets/kiet_flood_test.h5`, 10 scenarios — viewer reads ONLY this);
v1 `<split>_v1_NNNNN` (main pool idx <240; dry top-up 10000+; long-dry 20000+).

**ML API:** `FloodWindows` — 9 static + 3 dynamic channels, pipe/node graph state,
primary (depth, mask) + secondary (max/ever-flood/TTF/velocity/surcharge) targets,
numpy batches + optional torch wrapper, ragged-graph collate. Normalisation
**must** come from `normalization_train.json` (train-only).

### 6.1 Track C baseline training log (2026-09-06 — all runs)

- **Model:** `BaselineUNet(in_ch=36, n_leads=9, base=32)`, 476,297 params.
  In = 9 static + 18 dyn-hist (3ch × 6 steps) + 9 future-rain; out = 9 depth maps
  (leads 5..180 min). Loss = MSE depth + 0.2·BCE mask (≥5 cm), Adam 1e-3.
  (Early plan said in_ch=30 — wrong; smoke proved 9+18+9=36, fixed.)
- **Run 0 smoke (local, no torch):** `python3 -m models.train_baseline --smoke`
  → windows train=2692 val=542, batch (8,36,110,160)→(8,9,110,160), smoke OK.
- **Run 1 subset30 (Colab T4, torch 2.11+cu128):** 30 train / 10 val scenarios
  (43+12 MB uploads), 353/103 windows. 2 epochs 62 s: 0.1379→0.1367.
  8 epochs 73 s: 0.1373→0.1363 plateau. Artefact
  `outputs/models/baseline_subset30.pt` (1.9 MB).
- **Run 2 full100 (Colab T4):** 100 train / 49 val scenarios (full val file),
  1165/542 windows, batch 16, 10 epochs ~13 s/epoch. Loss 0.1374→0.1362.
  Val RMSE +30 min **0.048 m** / +180 min **0.049 m** (best; mid-run 0.049–0.054).
  Artefact `outputs/models/baseline_full100.pt` (1.9 MB). Log `/tmp/full100.log`.
- **Full-227 attempt:** 296 MB train.h5 chunk-uploaded (8×40 MB) + `cat`
  reassembled OK on VM, but bulk preload (~6.8 GB float32) exceeds single-exec
  comfort → timed out twice. Needs streaming H5 DataLoader (not built yet).
- **Colab GPU/TPU probe (2026-09-06):** T4 ✅ (`cuda True Tesla T4`),
  TPU v5e1 ✅, TPU v6e1 ❌ (no quota). All probe VMs stopped; `No active sessions`.
- **Plan:** `docs/superpowers/plans/2026-09-06-baseline-nowcaster.md`.
  Detail: `report.md` §§17–18.

Teammate gotchas: T varies per scenario (6–96 steps; rain and depth share T,
recession tail included as rain zeros); `flooded` = depth ≥ 0.05 m;
`flood_frac` = flooded cell-*time* share over wet cells; N=50/E=48 in all v1
variants today but the code only promises "≈50, spacing-limited" — always read
graph dims from the file; `kiet_networks_v1.json` holds **base** capacities while
per-scenario `pipe_capacity` is already drain_eff-scaled — build ML graph
features from the per-scenario arrays + spec, not the JSON; determinism
(same-seed → identical arrays) holds only for unchanged code; new scenario
classes go in `suite_v2.py` (`make_*_suite` + wire into `run_v2.py --only`).

---

## 7. Viewer + viz pipeline (Track B UX)

`flood_viewer.html` (35 KB single file, zero JS deps, canvas 2D): scenario select,
play/scrub/speed, 6 layer toggles, cell/node/pipe inspector, live metrics,
surcharge alarms, 0–50+ cm legend; styled by `Quiet Cartography Overlay Design
System.md` (glass panels, Manrope/Playfair/DM Mono). Pipeline:
v0 H5 → `export_viz.py` (int16/base64 frames, 1 mm display resolution) →
`validate_viz.py` (**ALL CHECKS PASSED**; see `docs/viewer.md` for the exact
validation table incl. node #9/pipe #39 spot checks) → `outputs/viz/`
(gitignored, regenerate with 2 commands; needs `http.server`, not `file://`).
Scope: 2D only, v0 test split only — v1 viewing never built.

---

## 8. Validation & gates

8/8 `tests/test_simulator.py`: Manning formula · twin loads · graph validity ·
rain normalisation · **mass closure** · blockage 0→50% (drainage 12.2→8.2 mm,
ponding 44.5→48.5 mm) · low-points ~2× · rain→runoff monotonic. Per-scenario:
NaN/Inf, negative depth, depth ≤2 m, velocity ≤3 m/s, mass ≤0.35, graph checks.
`verify_transfer.py` (checksums/readability/disjointness/dataloader) → PASS;
`SHA256SUMS` in v1/; 8 QC PNGs in `outputs/figures/qc/`.

---

## 9. Decisions (why, with the rejected alternative)

- **Diffusive wave, not full SWE/inertial:** justified for slowly-varying pluvial
  floods (Bates & De Roo; Dottori & Todini show bulk depths match); explicit,
  fast (~0.6 s/step), stable on coarse grids. Full SWE would need smaller dt and
  buy little at 5 m on synthetic terrain.
- **Buildings as walls:** an early version ponded-then-deleted rooftop water
  (mass leak); walls + `h[blocked]=0` fixed it. Rooftop storage ignored (documented).
- **DAG drainage:** cyclic graphs trapped water; strictly-outfall-closer linking
  guarantees outflow paths (proven by mass closure + graph checks).
- **No cell-net rescaling:** scaling outflows without matching inflows created
  mass; per-face 1/8 caps alone guarantee stability.
- **LHS + quotas over pure random:** coverage guarantees for rare corners
  (extremes, bullseyes) with fewer scenarios.
- **Scenario-level splits + train-only norm:** frame-level splits would leak
  storms across train/test; including val/test in norm leaks the eval distribution.
- **T4 rejected:** benchmarked, not assumed — identical speed for NumPy code.
- **Two top-ups, not endless duplication:** window-level analysis showed 0.2%
  no-flood targets and T<42 scenarios untrainable at +180 min; long-dry
  scenarios (3.5–6 h drizzle) fixed it to 12% — new scenarios, not copies.
- **`outputs/datasets/v1/` version dir:** never overwrite the v0 viewer file or
  prior releases; legacy `kiet_flood_test.h5` untouched.

## 10. Dead ends & traps (don't repeat these)

- Sign-flipped Qin (anti-diffusion) · building water deletion · trapped cycles ·
  overflow leak · ponded-unit bug — all fixed, all regression-tested (§4).
- `flood/` package: dead prototype (only `.pyc` left). `Infiltration` class +
  config `k_per_h` + SCS-CN wiring: implemented but **never called** — the live
  Horton uses hardcoded k=2.2 (§4.3). `visualization/*/` except `data_adapter/`:
  empty stubs. `synthetic/`, `terrain/{processed,products}/`, old split test
  files: abandoned. Free-Colab VMs die without warning: keep
  manifest+snapshot backups every ~15 min (lesson learned at 136/276 lost once).
- Colab file transfer (corrected 2026-09-06): single `colab upload` >~50 MB to a
  **new subdir** 500s — `mkdir` it first via exec, or upload flat to `/content/`.
  40 MB chunks + `cat` reassembly verified for 296 MB train.h5 (8 parts) + 57 MB
  val.h5 (2 parts). Downloads have no such cap.
- Colab long-job pattern (2026-09-06): run training via **`colab exec` (kernel) +
  log-file + `colab console` poll**. Client exec timeout ≠ server stop (job keeps
  running; check `colab status` BUSY/IDLE). Console-background `nohup &` dies on
  disconnect — do not use. Always `colab stop` when done.
- Baseline loader gotcha: `FloodWindows.get()` opens the H5 per call — fine for
  smoke, too slow for 2692 windows. `models/train_full.py:load_split` bulk-loads
  with one open handle (fast: 100 scn in 9 s) but preloads ~2.9 GB/100 scn —
  full 227 (~6.8 GB) OOMs/times out. Next: streaming DataLoader.

## 11. What's next (planned, NOT implemented)

1. **Nowcaster follow-up (baseline done, §6.1):** streaming H5 DataLoader for full
   227-scn train → test (606 windows) + OOD (1861) eval with per-lead RMSE/CSI +
   no-flood calibration (val no-flood windows thin at 2%) → ConvLSTM/graph hybrid.
2. Wire or remove SCS-CN (decide: delete dead class or thread `method` through
   `simulate()`; either way un-hardcode `kk`).
3. v1 viewer support (export_viz currently v0-only) or retire viewer.
4. Scale-up (`--prod-n` 1000+, more network variants, FABDEM-vs-DSM terrain
   sensitivity, calibrated infiltration if soil data appears).
5. Confront with reality: inlet survey, observed flood extents, IMD design storms.
6. Commit the uncommitted Phase 2/3 tree; dedupe `outputs/datasets/ood/` vs
   `v1/ood/` (same 34 scenarios, two copies).

## 12. Sources

All external sources in `source.md` (no invented citations): EPA SWMM 5.1 + Ref
Vol I/II · Bates & De Roo 2000 · LISFLOOD-FP manual · HEC-RAS DWE · IWA 2017
urban-pluvial · Dottori & Todini 2012 · Horton/Green-Ampt/SCS-CN via SWMM docs +
swmm5.org · Chow 1959 / USGS WSP 2339 / FHWA HDS-3 · Copernicus DEM handbook ·
OSM · GDA sanctioned plan · in-repo rainfall CSVs · `scipy.stats.qmc` docs
(McKay 1979 via refs) · Colab CLI README. Assumptions ledger: §5 + `source.md`
§§8/10 + `docs/assumptions.md`.
