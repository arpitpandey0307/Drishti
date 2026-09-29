# Forecast — rainfall nowcast + probabilistic flood forecast (Task 2, SRS Modules A, B, C, M, N)

From rainfall observations to a 0–180 min flood forecast with P10/P50/P90 depth and
exceedance probabilities, in well under a minute per cycle. Level-1 scope (SRS §11): the
radar, gauges and NWP are **synthetic** (a hidden storm "truth"), the drainage network is
synthetic, and every output is labelled observed / derived / modelled / synthetic.

```
python -m forecast.run --event squall --seed 3 --t0 90                        # one forecast cycle
python -m forecast.run --event squall --seed 3 --t0 90 --radar-outage 60:400  # radar failure -> DEGRADED
python -m forecast.run --event squall --t0 90 --gauge-fault G3:frozen:40      # faulty gauge rejected
python -m forecast.verify --event squall --seed 3 --t0 90 --compare-refine    # score vs synthetic truth
python -m forecast.surrogate.dataset --n 260 --ood 30 --workers 6             # regenerate training data
python -m forecast.surrogate.train --epochs 12                                # retrain + export ONNX
python -m pytest -q tests/test_forecast.py
```

In Python: `run_forecast(t0, sources)` returns the forecast JSON, maps, and the rain and depth
ensembles. Outputs go to `outputs/forecasts/<id>/`: `forecast.json`, `maps.npz` and
`exceedance_{10,20,30}cm.png` (+15 / +30 / +60 / +120 / +180 min).

## Pipeline

| Step | SRS | File |
|---|---|---|
| Observation adapters | A | `forecast/obs.py` |
| Quality engine | B | `forecast/quality.py` |
| Gauge bias correction, STEPS ensemble, NWP/climatology blending | C | `forecast/steps.py`, `forecast/motion.py` |
| Twin state at t0 (physics on observed rain, open loop) | F–I | `simulation/hydraulics/simulate.py` (`rain=`) |
| Surrogate depth ensemble (global level) | M | `forecast/surrogate/` |
| Probabilistic flood forecast, per cell and per road | N | `forecast/probabilistic.py` |
| Hotspots + local physics refinement | M | `forecast/adaptive.py` |
| Orchestration, health, provenance, degradation | §10, §16 | `forecast/run.py` |
| Synthetic truth events | §11 | `forecast/storms.py` |
| Verification against the truth | Z (preview) | `forecast/verify.py` |

### A — Observation adapters
`RainfallSource.fetch(t) -> Observation` (grid or gauge points, plus provenance and status).
An adapter never raises for a missing product: it returns `MISSING`, and the platform degrades.

- `SyntheticRadar`: truth × Z-R bias (0.75) × correlated log-normal noise. Supports outages and frame faults.
- `SyntheticGauges`: 5-min tipping-bucket accumulations at 8 stations. Faults can be injected: offline, frozen, spike, negative, clock drift, stuck at zero.
- `RadarArchiveReplay`: replays archived radar or GPM-IMERG frame stacks at any cadence. `.save()` archives any source.
- `GaugeCSVSource`: gauge CSVs with `time_min` or ISO `time`, `station_id`, `x_km,y_km` or `lat,lon`, and `rain_mm`.
- `MosdacDWRSource`: stub for the MOSDAC DWR pathway. Without credentials it always reports `MISSING`.
- `SyntheticNWP`: the truth smoothed to 8 km, shifted 20 min and scaled ×1.2 (a stand-in for NWP guidance).

The daily CSVs in `data/raw/rainfall/` feed the climatology fallback. They cannot drive a
5-min nowcast.

### B — Quality engine
Statuses are VALID / SUSPECT / STALE / MISSING / FAULT, each with reasons. The checks cover:
- impossible values
- spikes, unless corroborated by the previous report or by radar
- frozen sensors (6 identical non-zero reports) and frozen radar frames
- clock drift (> 60 s)
- stale data and missing intervals
- low radar coverage and domain-mean jumps
- gauge-vs-radar contradictions (0 reported while radar shows > 5 mm/h for 3 steps, and the reverse)

Only VALID gauges enter the bias correction. Radar frames that are FAULT, STALE or MISSING are
not used.

### C — Nowcast
The engine is an in-house STEPS: pysteps has no Python 3.14 wheel, so it follows pysteps'
algorithms.
1. Mean-field gauge bias correction over 60 min, clipped to [0.33, 3].
2. Motion from pyramidal Lucas-Kanade optical flow on dBR.
3. Lagrangian alignment of the last 3 frames.
4. A 6-level FFT cascade with an AR(2) model per level.
5. Per-member non-parametric spectral noise and per-member motion perturbation.
6. Probability matching, then semi-Lagrangian extrapolation.

Member 0 is the unperturbed control. Blending weights follow FR-C03: nowcast weight 1.0 up to
30 min, 0.85 at 60 min, 0.45 at 120 min and 0.2 at 180 min. The rest of the weight goes to NWP
(perturbed per member), or to monsoon climatology when there is no NWP. The regional grid is
192 × 192 km at 1 km. At that scale, campus rainfall is smooth, and the provenance says so.

### M — Surrogate (global level)
A residual U-Net (`depth(t0+lead) = relu(depth(t0) + Δ)`) on the 76 × 104 domain crop. It has
36 input channels: 9 static, 6 steps of rain and depth history, cumulative future rain for each
of 14 leads, and a blockage plane. It outputs depth at 5, 10, 15, 20, 30, 40, 50, 60, 75, 90,
105, 120, 150 and 180 min.

- **Data:** 260 in-distribution runs plus 30 out-of-distribution runs of the Task-1 physics (6 h each). The rain families are regional storms, spec patterns and random pulses. Blockage is 0–0.5; the OOD set uses 1.8–2.5× storm intensity and blockage 0.75.
- **Splits:** by scenario, never by window.
- **Training:** streams windows on the fly, fixing the old out-of-memory problem.
- **Artefacts:** `forecast/models/surrogate_v2.onnx` with metrics in `surrogate_v2.json`.

Velocity is not an input or output, because the Task-1 velocity is a crude proxy.

### N — Probabilistic flood forecast
For every cell:
- expected depth and P10 / P50 / P90 at every lead
- peak depth (mean, P10, P50, P90) and peak time
- time to 10 cm, and the probability of reaching it
- expected flood duration
- P(depth > 10 / 20 / 30 cm) per lead and over the whole horizon

For every OSM road segment, the same statistics come from the worst cell on the segment in each
member. The domain summary gives flooded area P10/P50/P90 per lead and the exceedance area.
Probabilities are ensemble frequencies and are not calibrated; the JSON states this.

### M — Adaptive fidelity (local level)
1. Divide the domain into 16 × 16-cell tiles (80 m).
2. Mark a tile as a hotspot if any of these holds:
   - P(depth > 20 cm) ≥ 0.3
   - P90 − P10 peak depth ≥ 10 cm
   - P(depth > 10 cm) ≥ 0.1 within 25 m of a campus building
3. Take the representative members at the P50 and P90 rain ranks, and run the full coupled physics for them (2 parallel processes).
4. Inside hotspot tiles, replace those members with the physics result. Every other member gets the physics-minus-surrogate correction of its nearest representative.

A hotspot that is still below 10 cm at t0 but has P ≥ 0.5 of reaching it is marked
`early_warning` (AC-12).

### Degradation (SRS §16, AC-19)
| Condition | Rain source | Forecast |
|---|---|---|
| Last 3 radar frames usable | radar + gauge bias correction | OPERATIONAL (if gauges are mostly valid) |
| Radar missing, stale or faulty; ≥ 3 valid gauges | gauge IDW, last radar motion if ≤ 30 min old, else no advection | **DEGRADED**: noise × 1.5, nowcast weight × 0.6 |
| No usable radar and < 3 gauges | NWP / climatology only | **DEGRADED** |

`health.reasons` lists every cause, including rejected gauges and radar QC flags.

## Results

All numbers below are for the synthetic twin experiment: squall seed 3, 20 members, 1 km
radar with 0.75 bias. They score the system against its own synthetic truth, not against
observations.

**Cycle time:** 18–20 s on a laptop CPU, against a < 60 s target.

| Stage | Time |
|---|---|
| Ingest + QC | 0.6 s |
| Nowcast (20 members × 36 steps) | ≈ 8.5 s |
| Twin state (physics) | ≈ 2 s |
| Surrogate | 0.2 s |
| Hotspot physics refinement | ≈ 7.5 s |

**Surrogate on held-out physics scenarios** (from `forecast/models/surrogate_v2.json`):

| Lead (min) | 5 | 30 | 60 | 120 | 180 |
|---|---|---|---|---|---|
| RMSE test (cm) | 0.66 | 1.43 | 1.96 | 2.54 | 2.38 |
| RMSE persistence (cm) | 0.74 | 2.57 | 4.01 | 5.36 | 5.12 |
| CSI 10 cm, test | 0.93 | 0.82 | 0.80 | 0.79 | 0.79 |
| CSI 10 cm, persistence | 0.89 | 0.58 | 0.39 | 0.26 | 0.24 |
| CSI 10 cm, OOD (1.8–2.5× rain, blockage 0.75) | 0.92 | 0.81 | 0.80 | 0.77 | 0.78 |

**End to end** (`python -m forecast.verify`):

| t0 / sources | Rain CSI 1 mm/h at +60 / +180 (persistence) | Flood CSI 10 cm at +60 / +180 | Early warning (AC-12) |
|---|---|---|---|
| t0 = 90 min, before the squall arrives, radar OK | 0.75 / 0.73 (0.47 / 0.03) | 0.22 / 0.50 | 36% of later-flooded cells flagged, 0% false alarms, 50 min ahead |
| t0 = 115 min, storm established, radar OK | 0.71 / 0.72 (0.48 / 0.02) | 0.77 / 0.83 | 67% flagged, 2% false alarms, 20 min ahead |
| t0 = 115 min, radar outage + frozen gauge G3 | 0.57 / 0.66 | 0.20 / 0.40 | 26% flagged, 0% false alarms; **DEGRADED**, G3 = FAULT |

**What the numbers show:**
- The rainfall nowcast beats persistence from +60 min onwards.
- The flood forecast is good once the storm is observed.
- The ensemble is **under-dispersive**. P10–P90 covers the truth in only 5–50% of active cells. Early in an intensifying storm the forecast is biased low, because STEPS extrapolates the current intensity distribution and cannot predict convective growth.
- Losing the radar costs real skill, and the platform reports the degradation instead of hiding it.

**Next steps:** calibrate the spread with Task 3 assimilation (the twin state is currently open
loop), then check reliability over many events.

## Known limitations
- All observations are synthetic. Real skill needs archived DWR or IMERG plus gauge data (Task 5 replay and validation).
- Probabilities are not calibrated. Reliability can only be checked over many cases.
- The surrogate emulates network variant 0 with nominal pumps and outfalls. Other drainage states come in only through the blockage plane and the physics refinement. Task 3 assimilation will correct the open-loop twin state.
- There is no velocity forecast.
