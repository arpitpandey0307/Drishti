# 08 — Decisions / Trade-offs / Evolution (FACT vs INFERENCE)

## 1. Git evolution (FACT: 33 commits main-only, 5d9cd1b → 60a1028)

1. `5d9cd1b first commit` → `7700a35/ e0a8b26/ c522720` static-host compat (index landing, render fix, vercelignore, deploy URLs).
2. `6bd5abb/973d03e/aec7223/d4bd278/6eee622/d805514/a29e276/1414aba/9d075f2` accurate map (design→affine A–Z→centroids→roads→3D→log→parking→ignore photos).
3. `1ff86e5/21f5a50/1052b30/36ee570/695c58a/f4b4a89/c615cf4/4c5ca6a/525a9b2` label/geometry fights (snap 0.0 m → verified-only → strip fills/loops/labels → restore OSM relabels → drop toggles; one revert).
4. `8422ab8 SIH working project` (squash: simulator+dataset+baseline+viewer+routing+HF) → `904c5e3` ONNX single-file fix → `8b05e53` lean push → `012d979/ed05a4c` planner → `77b5ef4` judge demo (autoplay+CSV+card) → `432d78b/16b2a5d` prod demo bank → `844b434` headfull proof → `fd7e99e/60a1028` viewer fallback + card trim.
- Working tree clean at dump (`git status` empty, `git diff --stat` empty).

## 2. Key decisions (FACT per knowledge.md:368-389 + report)

| # | Decision | Alternative discarded | Why | Evidence |
|---|---|---|---|---|
| D1 | Diffusive storage-cell, not full SWE | inertial/full dynamic | fast ~0.6 s/step, stable, bulk depths match | knowledge §9; docs/simulation.md |
| D2 | Buildings = walls | pond-then-delete | deletion leaked mass | report §13 traps |
| D3 | DAG drainage | cyclic graph | cycles trapped water | report §13 |
| D4 | No cell-net rescaling | wet-cell normalise variants | breaks mass | knowledge §9 |
| D5 | LHS + quotas (v1) | pure random | balance + coverage | suite_v2.py; dataset_report |
| D6 | Scenario-level splits + train-only norm | frame-level / global norm | leakage | ml_dataset.py; compute_normalization |
| D7 | Colab CPU, T4 rejected | GPU training/sim | benched identical 0.57 vs 0.58 s/step | knowledge §6; report §16 |
| D8 | Two top-ups (dry 36 + longdry 48) | duplicate sampling | 0.2% no-flood + T<42 untrainable at +180 | knowledge §9 |
| D9 | `outputs/datasets/v1/` version dir | overwrite v0 | viewer compat | knowledge §9 |
| D10 | In-browser ONNX, no Gradio | Docker/Gradio Space | PRO paywall; free static never sleeps | report §20 |
| D11 | Single-file ONNX | external-data sidecar | ORT-web `MountedFiles` failure | report §20; commit 904c5e3 |
| D12 | Demo bank committed | full outputs/ | prod 404 vs blob bloat | report §23; .gitignore !viz-demo |
| D13 | 3 apps (planner/viewer/Space) | one app | distinct users/data/hosts | §22–24 |

## 3. Dead ends / traps (FACT knowledge.md:391-412 + report §13)

Sign-flipped Qin; building deletion; trapped cycles; overflow leak → surface-return; ponded-unit bug — all fixed + regression-tested. `flood/` dead .pyc; `Infiltration` class + `k_per_h` + SCS-CN never called (live kk=2.2); `visualization/*/` stubs; `synthetic/`, `terrain/{processed,products}`, old splits abandoned. Colab lessons: snapshot every ~15 min (lost 136/276 once); >50 MB uploads need subdir+500 s + mkdir-first; 40 MB chunks+cat; `colab exec`+log+poll (nohup dies; timeout≠stop; always `colab stop`). Loader: per-call H5 OK smoke, too slow 2692; bulk fast 100 scn/9 s but ~2.9 GB/100 scn → full 227 ~6.8 GB OOM → streaming DataLoader next.

## 4. [INFERRED] (archivist, not repo text)

- Track A came first (maps/deploy commits predate SIH squash); flood work reused its GIS.
- Multiple HTML versions = audience split, not indecision (planner end-user vs viewer engineer vs Space ML-proof vs 3D showcase).
- `flood/` deletion = rename to `simulation/` for SIH modularity; `drainage/`/`terrain/` empties = planned namespaces never filled (real code under `simulation/`).
- Parking sums (20232.12) double as affine sanity, not engineering.
- 33-commit shallow history + `8422ab8` squash ⇒ real iteration happened off-branch/Colab, squashed on push (see knowledge §93-96 uncommitted warning — since resolved, tree now clean).
