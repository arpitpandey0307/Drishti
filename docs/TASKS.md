# Drishti — SRS Build Plan (5 Tasks)

This plan splits [`SRS.md`](SRS.md) into five sequential tasks. Each task ends with a
working, demo-able system, and each task builds on the one before it. Scope follows
**SRS §11 Level 1 (Demonstration)**: public rainfall, public DEM, synthetic drainage and
simulated sensors. Every output must be labelled *observed / derived / modelled / synthetic*
(SRS §10).

| # | Task | SRS modules | Acceptance criteria | Effort |
|---|---|---|---|---|
| 1 | Physics core: coupled 1D/2D twin — **DONE** ([details](simulation.md)) | D, E, F, G, H, I | AC-02 … AC-06 | 5–6 person-weeks (pw) |
| 2 | Rainfall nowcast + probabilistic flood forecast — **DONE** ([details](forecast.md)) | A, B, C, M, N | AC-01, AC-07, AC-08, AC-12, AC-19 | 5–6 pw |
| 3 | Closed loop: data assimilation + drainage health | J, K, L, U, V | AC-09, AC-10, AC-11 | 5–6 pw |
| 4 | Decisions: impact, routing, what-if, actions, sensors | O, P, Q, R, S, T, X | AC-13, AC-14, AC-15, AC-20 | 5–6 pw |
| 5 | Platform: API, dashboard, validation, security | W, Y, Z, §12–§24 | AC-16, AC-17, AC-18 | 6–7 pw |

Total: about 27–32 person-weeks, which is roughly 6 weeks full-time for a 5–6 person team.

---

## Task 1 — Physics Core: Coupled 1D/2D Digital Twin ✅ DONE

> Implemented as an in-house NumPy local-inertial 1D engine instead of PySWMM (no SWMM
> binaries for Python 3.14); networks export to SWMM `.inp` for cross-checking.
> See [`simulation.md`](simulation.md).

**Goal:** a correct, mass-conserving model in which rainfall becomes runoff, flows over the
DEM, enters a real hydraulic drainage network, surcharges and flows back onto the street.

### 1.1 Restore missing modules
- Rebuild `simulation/terrain/twin.py` (`Twin`: DEM, X/Y grids, `dx`, masks `in_domain`,
  `is_building`, `is_road`, `is_open`, Manning grid) from `data/terrain_grid.json` and
  `kiet_terrain/campus_osm.geojson`.
- Rebuild `simulation/drainage/network.py` (`generate()`, `pipe_capacity()`): synthetic
  manholes/inlets placed along roads and low points, pipes directed downhill, outfalls at
  the domain edge. Every asset is tagged `verified=false`.
- Get `tests/test_simulator.py` passing again.

### 1.2 Terrain intelligence (Module D)
- A terrain metadata record with CRS, vertical datum, resolution and **data tier** (Tier 1:
  public 30 m DSM). The tier is shown in the UI (SRS §D).
- Derive flow direction, flow accumulation, depressions and road elevation profiles.

### 1.3 Hydrologic runoff (Module E)
- Pipeline: interception → infiltration → depression storage → effective rainfall.
- Wire the dead SCS-CN code into `simulation/surface/infiltration.py` next to Horton, with the
  method chosen in `config/hydraulics.yaml`. Remove the hard-coded `kk = 2.2`.
- Subcatchment delineation: each inlet gets a contributing area.

### 1.4 1D drainage hydraulics (Module G), replacing `pipes.py`
- Use **PySWMM / SWMM5** as the 1D engine: dynamic-wave routing, backwater, reverse flow,
  surcharge. Node types: inlet, manhole, junction, storage, pump, outfall. Link types:
  pipe, culvert, channel.
- Export the synthetic network to a SWMM `.inp` file.
- This fixes the current bugs: node storage never draining, 1 m² node area, and the
  non-topological single-pass routing.

### 1.5 Surface–drainage exchange (Module H)
- At each inlet, exchange flow is set by the surface head vs sewer head: weir equation
  (shallow surface) or orifice equation (submerged), capped by inlet capacity.
- Supports capture, surcharge, reverse flow and inlet overflow.
- 2D step ↔ SWMM step coupling with a shared exchange time step.

### 1.6 Boundary conditions (Module I)
- Time-varying outfall stage: free outfall, fixed stage and time series (a river/nala level
  stand-in). A pump discharge boundary.

### 1.7 2D surface (Module F)
- Keep the existing diffusive-wave solver. Add velocity and flow-direction outputs,
  and a mass-balance report per run (target error < 1e-6).

**Deliverables:** `simulation/` rebuilt; `python -m simulation.run --scenario X` produces a
depth/velocity/node-state time series; mass-balance test; baseline experiments B1–B5
(SRS §7) runnable by switching components on/off.

---

## Task 2 — Rainfall Nowcast + Probabilistic Flood Forecast ✅ DONE

> Implemented in `forecast/`. pysteps has no Python 3.14 wheel, so STEPS (optical flow, AR(2)
> cascade, stochastic noise, blending) is re-implemented in NumPy. The surrogate was retrained on
> 290 fresh Task-1 physics runs and exported to ONNX (1 MB, shipped in `forecast/models/`).
> See [`forecast.md`](forecast.md) for results and limitations.

**Goal:** from rainfall observations to a 0–180 min forecast with P10/P50/P90 depth and
exceedance probabilities, fast enough to refresh every 5 minutes.

### 2.1 Observation adapters (Module A)
- A provider-agnostic adapter interface: `RainfallSource.fetch(t) -> grid + metadata`.
- Adapters: (a) archived radar / GPM IMERG replay, (b) rain-gauge CSVs from
  `data/raw/rainfall/`, (c) a synthetic storm generator (existing). MOSDAC DWR adapter stub.

### 2.2 Observation quality engine (Module B)
- Status per observation: VALID / SUSPECT / STALE / MISSING / FAULT.
- Checks: physical range, spikes, frozen values, gaps, clock drift, gauge-vs-radar
  contradiction.

### 2.3 Rainfall nowcast engine (Module C)
- **pysteps**: optical-flow extrapolation for 0–60 min; STEPS ensemble (≥ 20 members).
- 60–180 min: blend with NWP or climatology, with widening uncertainty.
- Gauge bias correction of the radar field.
- Output: ensemble plus P10/P50/P90 rainfall fields.

### 2.4 Surrogate model (Module M, global level)
- Regenerate the training dataset with the Task-1 physics; retrain the U-Net with a
  streaming DataLoader (fixes the out-of-memory problem in `models/train_full.py`).
- Export to ONNX. Report per-lead-time RMSE and CSI on held-out and out-of-distribution sets.

### 2.5 Probabilistic flood forecast (Module N)
- Push every rainfall ensemble member through the surrogate → depth ensemble.
- Per cell and per road segment: expected depth, P10/P90, peak depth, peak time,
  time-to-threshold, flood duration, P(depth > 10/20/30 cm).

### 2.6 Adaptive fidelity (Module M, local level)
- Hotspot detection: high risk, high uncertainty or next to critical infrastructure.
- Rerun the full physics model only on hotspot tiles, then merge the refined result.

### 2.7 Degradation modes (SRS §16)
- Radar missing → fall back to gauges and widen uncertainty; the forecast is flagged as degraded.

**Deliverables:** `forecast/` package; `run_forecast(t0)` returns a probabilistic forecast
object in < 60 s; exceedance maps for +15/+30/+60/+120/+180 min.

---

## Task 3 — Closed Loop: Data Assimilation + Drainage Health

**Goal:** the twin corrects itself from observations and infers hidden infrastructure
problems. This is the project's main differentiator.

### 3.1 Digital twin state (Module J)
- A state store: surface state, sewer state, storage, pump state, boundary state, rainfall
  state and infrastructure condition. Each value carries its estimate, observation,
  uncertainty, timestamp and source.

### 3.2 Virtual sensor network (twin experiment / OSSE)
- A "truth" run with hidden parameters (e.g. a blockage at one node, a different roughness).
- Virtual water-level sensors at 5–10 manholes and 2–3 street points, with noise, dropouts
  and injected faults. Clearly labelled **synthetic**.

### 3.3 TwinSync data assimilation (Module K)
- **Ensemble Kalman Filter** over state (node depths, surface depth near sensors) and
  parameters (inlet efficiency, blockage factor, roughness, infiltration).
- Compare open-loop vs assimilated error → evidence for hypothesis H2.
- Particle filter as an optional alternative.

### 3.4 Drainage health intelligence (Module L)
- Residual analysis: expected vs observed node level, conditioned on rainfall and boundary.
- Output per suspected asset: cause (inlet blockage, pipe obstruction, pump failure,
  sensor anomaly, parameter error, external inflow), likelihood, evidence and recommended
  inspection. Never a definitive failure claim.
- Demo: recover the hidden blockage from task 3.2.

### 3.5 Evidence fusion + sensor fault isolation (Module U, AC-10)
- A trust score per source; faulty sensors are rejected and the twin carries on with the rest.
  Conflicting observations are flagged, not averaged.

### 3.6 Forecast health card (Module V)
- Rainfall freshness, radar coverage, drainage coverage, sensor health, time since last
  assimilation, uncertainty level and overall status (OPERATIONAL / DEGRADED).

**Deliverables:** `twin/` package; an assimilation experiment notebook with plots; an anomaly
list API; health card JSON.

---

## Task 4 — Decisions: Impact, Routing, What-If and Actions

**Goal:** turn forecasts into operational decisions for roads, facilities and interventions.

### 4.1 Hazard / exposure / vulnerability / risk (Module O)
- Hazard = depth and velocity (depth × velocity product); exposure = roads and facilities
  in the hazard; vulnerability per asset class; risk = expected consequence under the ensemble.

### 4.2 Dynamic road impact (Module P)
- For every OSM road segment: depth(t), velocity(t), duration, status (Passable / Degraded /
  High Risk / Impassable), travel-time factor.
- Configurable thresholds by vehicle class (car, bus, ambulance, fire truck, two-wheeler)
  and by emergency policy.

### 4.3 Time-dependent probabilistic routing (Module Q)
- A server-side road graph (from `data/roads.geojson`). Each edge's cost is evaluated at the
  **predicted arrival time** on that edge.
- Objective = travel time + flood exposure + failure probability (weights set by vehicle).
- Return 3 alternative routes, each with ETA and P(depth > threshold). Never label a route as
  absolutely "safe" (AC-20).
- Fixes the current A* bugs (no re-relaxation, inadmissible heuristic).

### 4.4 Critical infrastructure impact graph (Module R)
- Hospitals, fire stations, shelters, substations (OSM). For each one: time until its access
  route is at risk, and how long an alternative stays available.

### 4.5 Counterfactual simulation (Module X)
- What-if: rain +20%, node N loses 50% capacity, pump P fails, downstream level +0.5 m,
  road closed. Rerun the physics (or surrogate) and compare against baseline.

### 4.6 Action impact optimizer (Module S)
- Candidate actions: pump activation, drain clearance, road closure, diversion.
- Evaluate single actions and pairs; report peak-depth change, flooded-area change,
  accessibility change and cost. Rule-based / greedy ranking for the MVP. Recommendation
  only, never automatic control.

### 4.7 Sensor placement advisor (Module T)
- Greedy selection of the candidate node with the largest reduction in ensemble variance
  (using Task-3 machinery); output the recommended location plus the expected uncertainty
  reduction.

**Deliverables:** `decision/` package (impact, routing, scenarios, actions, sensors), all
callable from Python and exposed through the Task-5 API.

---

## Task 5 — Platform: API, GIS Dashboard, Validation and Security

**Goal:** a running service and an operator dashboard that answers *what, where, when, why,
what next, what to do and how certain* (SRS §19), plus honest validation.

### 5.1 Backend service (SRS §13)
- FastAPI app with the `/api/v1/*` endpoints: observations, rainfall current/forecast,
  twin state/health, flood forecast/probability/hotspots, drainage state/anomalies,
  `POST routing/time-dependent`, `POST scenarios/simulate`, `POST actions/evaluate`,
  sensor recommendations, validation events/metrics.
- A scheduler that runs the loop every 5 min: ingest → QC → assimilate → forecast → impact.
- PostGIS (or SQLite + SpatiaLite for the demo) for the core entities (SRS §14).
- GeoJSON outputs so navigation apps can consume routes and closures.

### 5.2 Provenance (SRS §10, AC-18)
- Every forecast run stores input data versions, model version, parameter set, config hash
  and code commit. Any run can be replayed exactly.

### 5.3 Operator dashboard (SRS §19–§24)
- Views: A Live situation, B Forecast (+15 … +180 min slider), C Probability maps,
  D Drainage health, E Impact, F Action lab.
- Hotspot explanation panel "WHY?" (Module W): rainfall, runoff, terrain, drain state,
  anomaly and boundary contributions.
- Intervention impact panel, sensor recommendation panel, route planner (origin,
  destination, vehicle, departure time, risk tolerance → 3 routes with trade-offs shown).
- Forecast health card always visible; degraded-mode banner.

### 5.4 Historical replay + validation (Modules Y, Z; SRS §7, §30)
- Replay mode: an archived rainfall event → forecast vs "observed" (synthetic truth, plus
  news-reported waterlogging points where available).
- Metrics: MAE/RMSE (rain), water-level and peak-timing error (hydraulics), IoU/CSI/precision/
  recall/false alarm rate (maps), Brier score/reliability/interval coverage (probabilities),
  lead time and hotspot hit rate (operations).
- Baselines B1–B7 benchmark table. No numbers without held-out validation.

### 5.5 Interoperability + security (SRS §12, §17, §18)
- CAP XML alert export; OGC API Features for roads and drainage (pygeoapi); SensorThings-style
  observation schema.
- JWT authentication, role-based access (Admin, Operator, Dispatcher, Model Engineer,
  Infrastructure Engineer, Public), audit log, rate limiting, secrets through environment variables.

### 5.6 Deployment
- Docker Compose (api + worker + db + web). The static demo stays on Vercel/Render.

**Deliverables:** a running platform, the dashboard, the benchmark table, and a demo script
for the SIH presentation.

---

## Out of scope (SRS Phase 2–3, pitch as roadmap)

Live municipal integration, real pump telemetry, tide/coastal boundaries, traffic prediction,
satellite observations, GNN hydraulic surrogate, NSGA-II/MILP optimization, multi-city.
