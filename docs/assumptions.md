# Assumptions — synthetic vs verified

## VERIFIED (real data)

- 13×20 source DEM values (report.md Exp1 независим verification).
- OSM roads/buildings/boundary geometry as vendored (not field-checked).
- Sanctioned plot/coverage/FAR numbers (transcribed from GDA drawings).
- Rainfall CSV daily stats (max 114.59 mm, p99 ≈ 37 mm) — provenance unknown, ranges only.

## INFERRED (heuristic, confidence 0.4–0.7)

- Fine-grid landcover rasterization (4 m road width, affine sanctioned georef ±3–5 m).
- Inlet positions (road + low-point + accumulation heuristics).
- Flow directions from 30 m DSM.

## SYNTHETIC / ASSUMED (never cite as measurement)

1. All sub-30 m relief (upsampling + 0.15 m noise).
2. Entire pipe network (diameters, slopes, inverts, capacities).
3. Infiltration/Manning/depression parameters (uncalibrated).
4. Blocked-building walls; rooftops ignored; closed domain boundary.
5. Free outfalls (no river backwater); rainfall scenarios (not IMD design storms).
6. All flood depths = model output, not observations.

Every synthetic feature carries `verified=false, source=synthetic/inferred`
in code, configs, GeoJSON, HDF5 attrs, and figures.
