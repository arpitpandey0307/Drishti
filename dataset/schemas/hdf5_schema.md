# HDF5 schema

## v0 (legacy): `outputs/datasets/kiet_flood_{test,val,prod}.h5`

Global attrs: `synthetic=True`, `crs_calc=EPSG:32643`,
note "SYNTHETIC physics-based training data — NOT observations".

Static datasets (root): `dem, manning, imperv (110×160 f8)`,
`in_domain, is_road, is_building (u1)`, `X, Y (m, f8)`.

Per `/scenario_NNNN` (attrs: `spec` JSON, `mass` JSON, `mass_err`,
`network_variant`, `flood_threshold_m=0.05`):

| name | shape | dtype | meaning |
|---|---|---|---|
| rain | (T,110,160) | f4 | mm per 5-min step |
| depth | (T,110,160) | f4 | water_depth (m) |
| velocity | (T,110,160) | f4 | speed proxy (m/s, cap 3) |
| flooded | (T,110,160) | u1 | depth ≥ 0.05 |
| node_depth | (T,N) | f4 | m above invert |
| pipe_flow | (T,E) | f4 | m³/s |
| pipe_capacity | (E,) | f4 | m³/s full-flow |
| surcharge | (N,) | bool | head > rim at end |
| overflow | (N,) | f4 | m excess head |
| blockage | (E,) | f4 | 0–0.9 applied |
| time_to_flood_min | (110,160) | f4 | NaN if never ≥5 cm |
| max_depth | (110,160) | f4 | m |

Resume: `{split}_manifest.json` lists done scenarios; re-running skips them.
Reproduce: seed in `config/simulation.yaml` (26085) + spec JSON per group.

## v1.0 (current): `outputs/datasets/v1/kiet_flood_{train,val,test}.h5` + `v1/ood/kiet_flood_ood.h5`

Scenario-level 70/15/15 split files (frames never leak across splits) plus a
separate OOD file with deliberately out-of-range combos. Rejected scenarios go
to `kiet_flood_quarantine.h5` (never trained on).

Global attrs add: `dataset_version=1.0`, `simulator_version=1.0`,
`generated_utc`.

Static datasets (root) add: `slope (f8)`, `flow_accum (f4)`, `low_points (u1)`.
These + dem/manning/imperv/masks/X/Y are the STATIC ML inputs; per-scenario
`dem_delta (110×160 f4)` reconstructs the exact jittered terrain used
(`dem_used = dem + dem_delta`; base verified terrain never modified).

Per `/<split>_v1_NNNNN` (attrs add `dataset_version`): same datasets as v0
plus `dem_delta`; `rain`/`depth`/`velocity` length T covers rain steps PLUS
any dry recession tail (`recession_h` in spec, zeros in rain). `spec` JSON
additionally records: `rain_class`, `edge_case`, `storm_sigma_m`,
`storm_speed_mps`, `storm_dir_deg`, `storm_center_xy` (bullseye cases),
`drain_eff`, `manning_scale`, `dep_scale`, `imperv_open`, `terrain_seed`,
`recession_h`, `ml_split`, `dataset_version`, `mass_err`.

Resume: `dataset_manifest.csv` (`scenario_id, seed, split, status, parameters…,
sim_time_s, validation_status, mass_err, file_path, errors`); re-running the
same `run_v2` command continues after the last completed scenario.
Reproduce: master seed 26085 + `simulation/scenarios/suite_v2.py` quotas/LHS.

Global attrs: `synthetic=True`, `crs_calc=EPSG:32643`,
note "SYNTHETIC physics-based training data — NOT observations".

Static datasets (root): `dem, manning, imperv (110×160 f8)`,
`in_domain, is_road, is_building (u1)`, `X, Y (m, f8)`.

Per `/scenario_NNNN` (attrs: `spec` JSON, `mass` JSON, `mass_err`,
`network_variant`, `flood_threshold_m=0.05`):

| name | shape | dtype | meaning |
|---|---|---|---|
| rain | (T,110,160) | f4 | mm per 5-min step |
| depth | (T,110,160) | f4 | water_depth (m) |
| velocity | (T,110,160) | f4 | speed proxy (m/s, cap 3) |
| flooded | (T,110,160) | u1 | depth ≥ 0.05 |
| node_depth | (T,N) | f4 | m above invert |
| pipe_flow | (T,E) | f4 | m³/s |
| pipe_capacity | (E,) | f4 | m³/s full-flow |
| surcharge | (N,) | bool | head > rim at end |
| overflow | (N,) | f4 | m excess head |
| blockage | (E,) | f4 | 0–0.9 applied |
| time_to_flood_min | (110,160) | f4 | NaN if never ≥5 cm |
| max_depth | (110,160) | f4 | m |

Resume: `{split}_manifest.json` lists done scenarios; re-running skips them.
Reproduce: seed in `config/simulation.yaml` (26085) + spec JSON per group.
