# 10 — Gaps / TODO / Future Work

## 1. What works now (FACT)

Maps (2D+3D+landing, Vercel+Render 200s); simulator 8/8 + per-scenario gates; v1 dataset 360 rows + SHA + verify PASS + 8 QC PNGs; baseline subset30 + full100 (RMSE 0.048/0.049); Space + model repo live 200s; planner live zero-errors; viewer local-full + prod-demo; routing 10/10 + 1/1; headfull proof ALL PASSED.

## 2. Broken / incomplete (FACT)

- Full-227 training OOM (~6.8 GB bulk float32; `train_full.py:load_split` 100 scn 9 s OK, 227 timeouts) → needs streaming DataLoader (`knowledge.md:415-426` next-1).
- v1 viewer never built (only 2 v1 scenarios ported via v1demo); choices: build v1 viewer or retire (`knowledge next-3`).
- SCS-CN + `Infiltration` class dead; `kk=2.2` hardcode; `k_per_h`/weir/CFL/dep-drain unused (`knowledge next-2`).
- TPU v5e1 OK / v6e1 no quota; T4 no speedup (NumPy); GPU path open.
- Root README stale (v0-only, omits v1/model/planner/Space); `docs/` plans predate §§20–24.
- Legacy: `flood/` .pyc, `drainage/`/`synthetic/`/`terrain/{processed,products}` empties, `visualization/*/` stubs, `ood/` vs `v1/ood/` duplicate (89 MB same file? verify by hash before dedupe).

## 3. Missing / ambiguous (archivist audit)

- SIH problem statement text not in repo (inferred from SIH_DEMO + Space title 26085).
- Rainfall CSV provenance unknown (GPM/ERA5 per filenames NOT verified); no IMD IDF.
- No sensor/observed flood extents; no calibration; no drain survey (all synthetic conf 0.3–0.7).
- OSM geometry not field-checked; sanctioned affine 3–5 m UNVERIFIED; DSM building hits.
- Colab session logs + TPU quota messages not in repo (only outcomes in knowledge/report).
- `outputs/` 709 MB local-only: full regen needs Colab re-run (~4.28 CPU-h) or HF fetch (v0+v1 test only).
- Planner bins = model predictions (synthetic demo), not physics; viewer bundles = physics; Space windows = model — three truths, label carefully.

## 4. Future (knowledge.md:415-426 + [INFERRED])

1. Streaming DataLoader → full-227 → test 606 + OOD 1861 per-lead RMSE/CSI + no-flood calibration → ConvLSTM/graph hybrid.
2. Wire/remove SCS-CN + un-hardcode kk + calibrate infil/Manning/dep.
3. v1 viewer or retire; unify planner/viewer/Space data story.
4. Scale `--prod-n` 1000+, more variants, FABDEM-vs-DSM, calibrated soils.
5. Confront reality: survey inlets, observed extents, IMD design storms, backwater/outfall BCs.
6. [INFERRED] Dedupe ood duplicate; refresh root README; archive `flood/` .pyc; fill or remove empty namespaces; version planner bins; add CITATION + LICENSE.
