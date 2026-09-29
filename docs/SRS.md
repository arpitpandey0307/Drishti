# SOFTWARE REQUIREMENTS SPECIFICATION

# Adaptive Closed-Loop Urban Flood Intelligence Platform

## Physics-Informed Digital Twin, Probabilistic Nowcasting and Decision Optimization

**Problem Statement:** SIH26085
**Organization:** Ministry of Earth Sciences
**Department:** National Centre for Medium Range Weather Forecasting
**Theme:** Disaster Management
**Category:** Software

---

# 1. Executive Summary

The system shall be an **adaptive, closed-loop urban flood intelligence platform** that continuously observes an urban drainage system, estimates its current hydraulic state, forecasts future inundation, diagnoses potential infrastructure degradation, quantifies uncertainty, and converts predictions into operational decisions.

Unlike a conventional flood-warning dashboard, the system shall maintain a continuously updated **digital representation of the urban hydrological-hydraulic system**.

The operational loop shall be:

```text
OBSERVE
   ↓
INGEST + QUALITY CONTROL
   ↓
ESTIMATE CURRENT STATE
   ↓
FORECAST
   ↓
QUANTIFY UNCERTAINTY
   ↓
IDENTIFY IMPACT
   ↓
DIAGNOSE INFRASTRUCTURE
   ↓
SIMULATE INTERVENTIONS
   ↓
OPTIMIZE RESPONSE
   ↓
OBSERVE AGAIN
   ↓
UPDATE DIGITAL TWIN
```

The platform shall provide forecasts over a **0–3 hour horizon**, while explicitly representing the degradation of forecast certainty with increasing lead time.

The core technical system shall couple:

* rainfall nowcasting,
* hydrologic runoff modelling,
* 2D urban surface hydraulics,
* 1D drainage hydraulics,
* surface/drainage exchange,
* downstream boundary conditions,
* real-time state observations,
* probabilistic uncertainty,
* road and infrastructure impact,
* time-dependent routing.

---

# 2. Problem Statement Interpretation

The platform addresses five operational questions:

### Q1 — WHERE?

Which streets, intersections and facilities are likely to experience flooding?

### Q2 — WHEN?

When will the flood threshold be crossed?

### Q3 — HOW SEVERE?

How deep, how fast and for how long?

### Q4 — WHY?

Is flooding being driven by:

* rainfall intensity,
* topography,
* drainage surcharge,
* blockage,
* pump failure,
* tidal backwater,
* river level,
* surface bottleneck?

### Q5 — WHAT SHOULD BE DONE?

Which intervention or route change reduces expected impact most effectively?

---

# 3. Product Vision

The system shall transform:

> **Rainfall information**

into:

> **an operational forecast of physical hazard, infrastructure state, uncertainty and recommended response.**

Example:

```text
ROAD R-184

Expected rainfall:
82 mm/hr

Predicted peak depth:
22 cm

Probability depth >15 cm:
84%

Time to threshold:
31 min

Primary driver:
Drainage surcharge

Suspected hydraulic degradation:
N-218 inlet, 42% ± 12%

Emergency route impact:
High

Recommended action:
Clear N-218 / divert emergency traffic
```

---

# 4. Design Principles

The platform shall follow eight principles.

## P1 — Physics First

Conservation laws and hydraulic constraints remain the primary mechanism.

## P2 — Data Corrects Physics

Sensor and observational data continuously update imperfect model states.

## P3 — Uncertainty Is a First-Class Output

The system shall never imply false precision.

## P4 — Compute Where It Matters

High-fidelity computation shall be concentrated around important/high-uncertainty regions.

## P5 — Explain Every Critical Prediction

Operators shall be able to understand the dominant drivers.

## P6 — Prediction Must Lead to Action

Outputs shall be connected to route and intervention decisions.

## P7 — Human Approval

The system is decision support and shall not automatically execute physical interventions.

## P8 — Provenance by Default

Every forecast shall be reproducible.

---

# 5. System Architecture

```text
                     ┌───────────────────────┐
                     │   OBSERVATION LAYER   │
                     │                       │
                     │ DWR / Rain Gauges     │
                     │ Water Levels          │
                     │ Pump Status           │
                     │ Tide / River          │
                     │ Citizen Observations  │
                     │ Traffic / Road State  │
                     └───────────┬───────────┘
                                 │
                                 ▼
                  ┌───────────────────────────┐
                  │ DATA QUALITY + FUSION     │
                  │                           │
                  │ QC / Bias / Staleness     │
                  │ Sensor Fault Detection    │
                  │ Spatial/Temporal Fusion   │
                  └─────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │ HYDROMETEOROLOGICAL        │
                 │ NOWCAST ENGINE              │
                 │                            │
                 │ Radar extrapolation        │
                 │ NWP blend                  │
                 │ Ensemble rainfall          │
                 └─────────────┬──────────────┘
                               │
                               ▼
             ┌────────────────────────────────────┐
             │      HYDROLOGIC TRANSFORMATION     │
             │                                    │
             │ Rainfall → Effective Rainfall      │
             │ → Runoff → Catchments              │
             └────────────────┬───────────────────┘
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
        ┌──────────────────┐   ┌─────────────────────┐
        │ 2D SURFACE       │◄─►│ 1D DRAINAGE        │
        │ HYDRODYNAMICS    │   │ HYDRAULICS          │
        │                  │   │                     │
        │ Depth            │   │ Pipes               │
        │ Velocity         │   │ Manholes            │
        │ Flow             │   │ Pumps               │
        │ Storage          │   │ Gates               │
        └────────┬─────────┘   └──────────┬──────────┘
                 │                        │
                 └───────────┬────────────┘
                             ▼
                 ┌─────────────────────────┐
                 │ DIGITAL TWIN STATE      │
                 │                         │
                 │ Surface state           │
                 │ Sewer state             │
                 │ Boundary state          │
                 │ Infrastructure state   │
                 └────────────┬────────────┘
                              │
                              ▼
                ┌─────────────────────────┐
                │ DATA ASSIMILATION       │
                │                         │
                │ EnKF / Particle Filter │
                │ State correction        │
                │ Parameter update        │
                └────────────┬────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ ADAPTIVE FORECAST ENGINE      │
              │                              │
              │ Coarse/global forecast       │
              │ Hotspot refinement           │
              │ Surrogate acceleration       │
              │ High-fidelity local solve    │
              └──────────────┬───────────────┘
                             │
                             ▼
             ┌─────────────────────────────────┐
             │ PROBABILISTIC FLOOD FORECAST    │
             │                                 │
             │ Depth / Extent / Velocity       │
             │ P10 / P50 / P90                 │
             │ Threshold probabilities         │
             │ Time-to-impact                  │
             └───────────────┬─────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   INFRASTRUCTURE       ROAD IMPACT        DIAGNOSTICS
   EXPOSURE             & ROUTING           & HEALTH
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                    ┌────────────────────┐
                    │ ACTION OPTIMIZER   │
                    │                    │
                    │ Pumps              │
                    │ Drain clearance    │
                    │ Road closure       │
                    │ Response routing   │
                    │ Resource staging   │
                    └─────────┬──────────┘
                              │
                              ▼
                       GIS / API / ALERTS
```

---

# 6. Functional Modules

# MODULE A — Multi-Source Observation Layer

## FR-A01 — Radar Data

The system shall support:

* Doppler radar rainfall,
* radar-derived precipitation products,
* radar mosaics where available.

The architecture shall use an adapter layer rather than hard-coding one provider.

Indian meteorological and satellite infrastructure exposes near-real-time weather and DWR products through MOSDAC services, providing a realistic pathway for an Indian deployment.

## FR-A02 — Rain Gauges

The system shall ingest:

* automatic rain gauges,
* cumulative rainfall,
* rainfall intensity,
* station health.

## FR-A03 — Water-Level Sensors

Inputs may include:

* drains,
* manholes,
* nalas,
* sump wells,
* rivers,
* reservoirs.

## FR-A04 — Pump and Gate State

The system shall ingest:

* pump ON/OFF,
* pump capacity,
* gate state,
* pump alarms,
* operational availability.

## FR-A05 — Citizen Observations

The system may ingest:

* observed flood depth,
* photograph,
* timestamp,
* location.

These observations shall be quality scored.

---

# MODULE B — Observation Quality Engine

Every observation shall receive a quality status:

```text
VALID
SUSPECT
STALE
MISSING
FAULT
```

The engine shall detect:

* impossible values,
* spikes,
* frozen sensors,
* clock drift,
* missing intervals,
* contradictory observations.

Sensor quality matters because poor observations can corrupt a digital twin. Real-time drainage research specifically addresses sensor fault detection and data reliability.

---

# MODULE C — Rainfall Nowcast Engine

## FR-C01

The system shall support:

```text
Radar observation
Radar extrapolation
Rain-gauge correction
NWP guidance
```

## FR-C02

The system shall generate rainfall scenarios:

```text
P10
P50
P90
```

or an equivalent ensemble representation.

## FR-C03

Forecast lead time shall be segmented:

```text
0–60 min
→ radar-dominant

60–180 min
→ blended radar + NWP
```

The architecture shall expose rainfall uncertainty to the downstream hydraulic model.

---

# MODULE D — Terrain Intelligence Engine

The system shall maintain:

* DEM/DTM,
* vertical datum,
* CRS,
* land-cover classes,
* imperviousness,
* road elevation,
* building footprints where available,
* drainage depressions,
* flow paths.

## Terrain Data Tiers

```text
Tier 1:
Public/coarse data

Tier 2:
Derived enhanced surface

Tier 3:
Partner / municipal high-resolution data
```

The system shall display which tier is being used.

This prevents false claims of metre-scale accuracy when the available terrain is materially coarser.

---

# MODULE E — Hydrologic Runoff Engine

For each catchment:

```text
Rainfall
↓
Interception
↓
Infiltration
↓
Depression Storage
↓
Effective Rainfall
↓
Runoff
```

Supported methods may include:

* Rational Method,
* Green-Ampt,
* Horton,
* SCS-CN,
* calibrated subcatchment models.

The method shall be selected based on available input data.

---

# MODULE F — 2D Surface Hydraulic Engine

The 2D engine shall compute:

* water depth,
* surface velocity,
* flow direction,
* surface storage,
* inundation extent.

The system shall enforce mass conservation.

For advanced implementation, shallow-water or local-inertial formulations may be used.

---

# MODULE G — 1D Drainage Hydraulic Engine

The drainage system shall contain:

### Nodes

* inlet,
* manhole,
* junction,
* storage,
* pump,
* outfall.

### Links

* pipe,
* culvert,
* channel,
* conduit.

The hydraulic state shall include:

```text
Discharge
Depth
Hydraulic head
Storage
Flow direction
Surcharge
```

Established tools such as SWMM already provide dynamic-wave routing, pumps, weirs, orifices, backwater, surcharge, reverse flow and surface ponding.

---

# MODULE H — Surface–Drainage Exchange Engine

This shall be a physically defined exchange model rather than a simple overflow condition.

For each inlet/exchange location:

```text
surface head
       ↕
 inlet capacity
       ↕
 sewer head
```

Exchange shall support:

* capture,
* surcharge,
* reverse flow,
* inlet overflow.

The 1D–2D architecture is technically established; commercial tools already dynamically link underground pipe networks and surface domains.

Therefore, the system shall treat **the coupling itself as a foundation, not as the sole innovation.**

---

# MODULE I — Boundary Condition Engine

Supported boundaries:

* free outfall,
* river stage,
* tidal stage,
* coastal surge,
* downstream lake level,
* controlled outlet,
* pump discharge.

The engine shall permit time-varying boundary conditions.

---

# MODULE J — Digital Twin State Engine

The twin shall maintain a current estimate of:

```text
Surface water state
Sewer state
Drainage storage
Pump state
Boundary state
Rainfall state
Infrastructure condition
```

Each state shall have:

```text
estimated value
observation
uncertainty
timestamp
source
```

---

# MODULE K — TwinSync Data Assimilation

This is a core differentiator.

## FR-K01

The platform shall compare:

```text
Model prediction
      vs
Observed reality
```

## FR-K02

The system shall update state using:

* Ensemble Kalman Filter,
* Particle Filter,
* or another validated sequential data-assimilation method.

Recent research has demonstrated 1D–2D urban flood prediction with particle-filter assimilation of both sewer and surface observations, improving spatial skill over an open-loop model.

## FR-K03

The system may update uncertain parameters such as:

* inlet efficiency,
* roughness,
* infiltration,
* depression storage,
* effective pipe capacity,
* blockage factor.

---

# MODULE L — Drainage Health Intelligence

This module shall detect deviations between expected and observed hydraulic behavior.

Example:

```text
Expected Node Level:
0.65 m

Observed:
1.08 m

Rainfall:
within expected range

Downstream stage:
normal

Inference:
Local hydraulic degradation suspected
```

Potential causes:

```text
Inlet blockage
Pipe obstruction
Pump failure
Sensor anomaly
Incorrect model parameter
Unexpected external inflow
```

The system shall produce:

```text
suspected cause
likelihood
affected asset
evidence
recommended inspection
```

It shall not make a definitive physical-failure claim without sufficient evidence.

---

# MODULE M — Adaptive Fidelity Engine

This is another major differentiator.

## Global Level

Use:

* coarse numerical model,
* fast surrogate,
* lower-resolution surface representation.

## Local Level

When a region becomes:

```text
high risk
OR
high uncertainty
OR
critical infrastructure adjacent
```

the engine automatically performs a higher-fidelity calculation.

```text
CITY
 ↓
FAST GLOBAL SCREEN
 ↓
HOTSPOT DETECTION
 ↓
LOCAL HIGH-FIDELITY MODEL
 ↓
REFINED FORECAST
```

The computational architecture is motivated by current research showing that physics-based urban flood simulations can be too expensive for direct real-time use and that learned surrogate models can greatly accelerate prediction.

---

# MODULE N — Probabilistic Flood Forecast

Each location shall provide:

```text
Expected depth
Lower bound
Upper bound
Peak depth
Time to threshold
Probability of threshold exceedance
Flood duration
Velocity where available
```

Example:

```text
R-184

P(depth > 10 cm) = 92%
P(depth > 20 cm) = 64%
P(depth > 30 cm) = 18%

Peak depth:
21 cm

Peak time:
+56 min
```

---

# MODULE O — Flood Hazard Model

The system shall distinguish:

### Hazard

Physical flood intensity.

### Exposure

Assets/roads/persons within the hazard.

### Vulnerability

Sensitivity to that hazard.

### Risk

Combined expected consequence under uncertainty.

---

# MODULE P — Dynamic Road Impact Model

For every road:

```text
depth(t)
velocity(t)
duration(t)
closure status(t)
travel time(t)
```

The system shall derive:

```text
Passable
Degraded
High Risk
Impassable
```

Thresholds shall be configurable by:

* vehicle class,
* road type,
* emergency policy.

---

# MODULE Q — Flood-Aware Time-Dependent Routing

The route engine shall evaluate the predicted state **when the vehicle reaches each road segment**, rather than using a single static flood state.

A route shall minimize an objective such as:

```text
Expected travel time
+
flood exposure
+
failure probability
+
traffic delay
```

For emergency vehicles, the system shall support different objective weights.

---

# MODULE R — Critical Infrastructure Impact Graph

The system shall connect:

```text
Flood Zone
   ↓
Road
   ↓
Hospital
   ↓
Emergency Route
   ↓
Response Capability
```

Example:

```text
Hospital H-12

Access Route:
At risk in 26 min

Alternative:
Available for next 74 min

Emergency exposure:
HIGH
```

---

# MODULE S — Action Impact Optimizer

The system shall evaluate proposed interventions.

Examples:

```text
Pump activation
Drain clearance
Temporary road closure
Diversion
Resource relocation
Pump prioritization
```

Each scenario shall produce:

```text
Peak depth change
Flooded-area change
Lead-time change
Road accessibility change
Critical-infrastructure impact
Operational cost
```

The optimizer may use:

* constrained optimization,
* MILP,
* Bayesian optimization,
* NSGA-II/NSGA-III,
* rule-based optimization for MVP.

Digital-twin-based flood intervention and pump optimization are already active research areas, so the differentiating element shall be their integration with the closed-loop nowcasting and uncertainty system.

---

# MODULE T — Sensor Placement Advisor

The system shall identify where additional sensing would provide the greatest value.

Example:

```text
Candidate Sensor
      ↓
Forecast uncertainty reduction
      ↓
Network observability gain
      ↓
Recommended location
```

Output:

```text
Recommended new sensor:
N-331

Expected uncertainty reduction:
28%

Primary benefit:
Downstream drainage state estimation
```

Sensor-placement optimization is an established technical problem in drainage modelling, giving this module a solid scientific basis.

---

# MODULE U — Evidence Fusion

Evidence sources shall include:

```text
Physics model
Radar
Rain gauge
AWLR
Pump telemetry
Citizen observation
Traffic information
Historical event data
Satellite observation
```

The system shall assign each evidence source:

```text
trust score
timestamp
spatial coverage
quality
```

Conflicting observations shall not be silently merged.

---

# MODULE V — Forecast Health Card

Every forecast shall contain an operational health summary.

Example:

```text
FORECAST HEALTH

Rainfall freshness:       34 sec
Radar coverage:           96%
Drainage coverage:         81%
Sensor health:             92%
Assimilation age:          2 min

Forecast uncertainty:     MODERATE
Boundary certainty:       HIGH

Overall model status:
OPERATIONAL
```

This is significantly more useful than a single generic confidence score.

---

# MODULE W — Explainable Flood Diagnosis

Every hotspot shall have:

```text
WHY?
```

Example:

```text
HOTSPOT R-184

Rainfall:
82 mm/hr

Surface runoff:
HIGH

Terrain:
LOW ELEVATION

Inlet N-218:
CAPTURE CAPACITY REDUCED

Drain:
SURCHARGED

Boundary:
ELEVATED

Result:
SURFACE WATER ACCUMULATION

Expected peak:
22 cm
```

---

# MODULE X — Counterfactual Simulation

Operators shall be able to ask:

### What if rainfall increases 20%?

### What if N-218 loses 50% capacity?

### What if pump P-17 fails?

### What if the downstream water level rises 0.5 m?

### What if a road is closed now?

The system shall recalculate:

* flood depth,
* flood duration,
* affected infrastructure,
* routes,
* intervention benefit.

---

# MODULE Y — Historical Event Replay

The system shall provide a replay mode.

```text
Historical Event
      ↓
Original rainfall
      ↓
Original observations
      ↓
Model replay
      ↓
Prediction
      ↓
Observed reality
      ↓
Error analysis
```

---

# MODULE Z — Model Validation

Validation shall cover four layers.

## Z1 Meteorological

* MAE
* RMSE
* bias
* spatial correlation

## Z2 Hydraulic

* water-level error
* flow error
* peak timing error

## Z3 Flood Map

* IoU
* CSI
* precision
* recall
* false alarm rate
* miss rate

## Z4 Probabilistic Forecast

* Brier score
* calibration curve
* reliability
* interval coverage

## Z5 Operational

* lead time,
* correct hotspot detection,
* route availability prediction,
* intervention benefit estimation.

No performance number shall be published without held-out validation.

---

# 7. Baseline Experiments

The platform shall support:

```text
B1:
Rainfall threshold

B2:
Rainfall + DEM

B3:
Rainfall + DEM + runoff

B4:
Rainfall + runoff + 1D drainage

B5:
Full coupled 1D/2D model

B6:
Full model + data assimilation

B7:
Full model + adaptive forecasting
```

This allows the team to demonstrate not just that the system works, but **which components materially improve the prediction.**

---

# 8. Unique Technical Contributions

The project shall emphasize these as its primary differentiators:

## Innovation 1 — Closed-Loop Flood Twin

Not:

```text
Model → Dashboard
```

but:

```text
Reality → Twin → Forecast → Reality → Twin
```

## Innovation 2 — Drainage Health Inference

Forecast disagreement becomes evidence for:

* blockage,
* pump degradation,
* inlet failure,
* incorrect parameters.

## Innovation 3 — Uncertainty-Driven Computation

More computational resources are allocated where:

* uncertainty is high,
* consequences are high,
* decisions are time-critical.

## Innovation 4 — Probabilistic Action Routing

Routing is based on predicted flood distributions rather than a binary flood map.

## Innovation 5 — Intervention Impact Engine

The system estimates:

> **“What action changes the flood outcome the most, and how much?”**

## Innovation 6 — Sensor Placement Advisor

The system recommends where sensing infrastructure should be added.

## Innovation 7 — Evidence-Aware Forecast

The system explicitly tracks what information supports each prediction.

---

# 9. Data Architecture

## Required data

### Meteorology

* DWR/radar precipitation
* gauge observations
* NWP guidance

### Terrain

* DEM/DTM
* roads
* imperviousness
* land cover

### Drainage

* pipes
* manholes
* inlets
* pumps
* outfalls

### Boundary

* river stage
* tide
* downstream level

### Observations

* water level
* pump status
* validated reports

MOSDAC already provides a pathway for meteorological, radar, ground-observation and forecast/nowcast datasets.

---

# 10. Data Provenance

Every dataset shall store:

```text
source
timestamp
version
resolution
CRS
vertical datum
quality
license
coverage
```

The system shall distinguish:

```text
Observed
Derived
Modelled
Synthetic
```

---

# 11. Indian Data Reality Mode

The platform shall support three deployment levels.

## Level 1 — Demonstration

Uses:

* public rainfall,
* public DEM,
* synthetic drainage,
* replayed flood event.

## Level 2 — Pilot Municipality

Adds:

* municipal drainage network,
* local rain gauges,
* water-level sensors,
* pump telemetry.

## Level 3 — Operational City

Adds:

* live radar,
* high-resolution terrain,
* full drainage inventory,
* boundary conditions,
* sensor assimilation,
* operational routing.

This makes the architecture realistic even when complete city infrastructure data are unavailable.

---

# 12. Interoperability

The platform shall expose standard geospatial and sensor interfaces where feasible.

## OGC API Features

Used for:

* roads,
* drainage features,
* administrative boundaries,
* infrastructure.

OGC API Features provides standardized Web API building blocks for geospatial feature access.

## OGC SensorThings

Used for:

* rainfall sensors,
* water levels,
* pump telemetry,
* IoT observations.

SensorThings is specifically designed to standardize geospatial IoT observation access.

## CAP

Alerts should support the Common Alerting Protocol where operational integration is required. CAP is an established standard for exchanging multi-hazard emergency alerts across networks.

---

# 13. API Architecture

```http
GET /api/v1/observations
GET /api/v1/rainfall/current
GET /api/v1/rainfall/forecast

GET /api/v1/twin/state
GET /api/v1/twin/health

GET /api/v1/flood/forecast
GET /api/v1/flood/probability
GET /api/v1/flood/hotspots

GET /api/v1/drainage/state
GET /api/v1/drainage/anomalies

POST /api/v1/routing/time-dependent

POST /api/v1/scenarios/simulate

POST /api/v1/actions/evaluate

GET /api/v1/sensors/recommendations

GET /api/v1/validation/events
GET /api/v1/validation/metrics
```

---

# 14. Core Data Entities

```text
City
Zone
Catchment

RainfallObservation
RainfallForecast
RainfallEnsemble

DEMTile
LandCover

DrainNode
DrainLink
Inlet
Pump
Gate
Outfall

SurfaceState
DrainageState
BoundaryState

FloodForecast
FloodProbability
Hotspot

Infrastructure
RoadSegment
Route

Sensor
SensorObservation
SensorHealth

HydraulicAnomaly
SuspectedFailure

Intervention
Scenario
ActionEvaluation

ForecastRun
ModelVersion
ParameterSet

ValidationEvent
ValidationMetric
```

---

# 15. Performance Architecture

A single uniform simulation resolution shall not be required for the entire metropolitan region.

The platform shall support:

```text
Global coarse model
        ↓
Risk screening
        ↓
Hotspot extraction
        ↓
Local fine model
        ↓
Optional surrogate acceleration
```

This allows the system to pursue real-time operation without pretending that a massive high-resolution hydraulic simulation is computationally free.

GPU acceleration and surrogate modelling are valid optimization paths; current commercial and research systems demonstrate both directions.

---

# 16. Failure and Degradation Modes

The platform shall never produce a normal-looking forecast from broken inputs.

Examples:

```text
RADAR FAILURE
↓
Rainfall source degraded
↓
Uncertainty increases
```

```text
DRAINAGE DATA PARTIAL
↓
Local forecast coverage reduced
↓
Confidence/uncertainty shown
```

```text
SENSOR FAULT
↓
Observation rejected
↓
Twin continues with remaining observations
```

```text
HIGH UNCERTAINTY
↓
Adaptive engine increases local model fidelity
```

---

# 17. Security

The system shall support:

* RBAC,
* authentication,
* encrypted communication,
* audit logging,
* API authorization,
* rate limiting,
* secure secrets,
* data provenance.

For government deployment, the architecture should support **on-premise/private-cloud operation** where required.

---

# 18. Operational Roles

### System Administrator

* users,
* access,
* configuration.

### Flood Control Operator

* monitoring,
* alerts,
* hotspots,
* incidents.

### Emergency Dispatcher

* route planning,
* facility access.

### Hydraulic/Model Engineer

* calibration,
* parameters,
* forecast runs,
* validation.

### Infrastructure Engineer

* drainage health,
* blockage diagnosis,
* sensor deployment.

### Public Viewer

* published flood information,
* route risk.

---

# 19. Operator Dashboard

The main dashboard shall answer:

```text
WHAT IS HAPPENING?
WHERE?
WHEN?
WHY?
WHAT WILL HAPPEN NEXT?
WHAT SHOULD WE DO?
HOW CERTAIN ARE WE?
```

---

# 20. Main GIS Views

## View A — Live Situation

* rainfall,
* current flood,
* sensors,
* drainage state.

## View B — Forecast

* +15,
* +30,
* +60,
* +120,
* +180 minutes.

## View C — Probability

```text
P(depth > 10 cm)
P(depth > 20 cm)
P(depth > 30 cm)
```

## View D — Drainage Health

```text
Normal
Suspected degraded
Surcharging
Blocked suspected
Pump fault suspected
```

## View E — Impact

* roads,
* hospitals,
* stations,
* shelters,
* critical assets.

## View F — Action Lab

```text
What if pump P-17 starts?

What if N-218 is cleared?

What if R-184 is closed?

What if rainfall increases by 20%?
```

---

# 21. Forecast Explanation Panel

For each hotspot:

```text
LOCATION
R-184

FORECAST
Peak depth: 22 cm

PROBABILITY
P(>15 cm): 84%

LEAD TIME
31 minutes

WHY?

Rainfall:
82 mm/hr

Runoff:
HIGH

Terrain:
DEPRESSED

Drain:
SURCHARGED

Hydraulic anomaly:
N-218

Boundary:
ELEVATED
```

---

# 22. Intervention Impact Panel

```text
BASELINE
Peak depth: 22 cm

ACTION A
Activate Pump P17
→ 14 cm

ACTION B
Clear N218
→ 16 cm

ACTION C
Pump + Clear N218
→ 9 cm

BEST PROJECTED COMBINATION:
A + B

Expected reduction:
13 cm
```

This shall remain a recommendation, not an autonomous control action.

---

# 23. Sensor Recommendation Panel

```text
NETWORK OBSERVABILITY

Highest uncertainty zone:
Zone 4

Best sensor candidate:
N-331

Expected uncertainty reduction:
28%

Affected hotspot forecasts:
11

Recommendation:
Deploy AWLR sensor
```

---

# 24. Route Planner

Users provide:

```text
Origin
Destination
Vehicle
Departure time
Risk tolerance
```

The engine returns:

```text
Route A
ETA: 19 min
P(depth > threshold): 12%

Route B
ETA: 16 min
P(depth > threshold): 57%

Route C
ETA: 23 min
P(depth > threshold): 4%
```

For emergency operations, the interface shall expose the trade-off explicitly instead of silently selecting a route.

---

# 25. What Makes This Different From Existing Solutions?

The system shall explicitly position itself as:

### Existing systems commonly provide

```text
Observe
→ Forecast
→ Map
→ Alert
```

### This system adds

```text
Observe
→ Assimilate
→ Forecast
→ Quantify uncertainty
→ Diagnose hidden infrastructure state
→ Adapt computational fidelity
→ Evaluate interventions
→ Optimize routes/actions
→ Learn from observations
```

That is the central product thesis.

---

# 26. MVP

The MVP should **not attempt all research components simultaneously**.

The highest-value implementation is:

### Core

```text
Radar/rainfall
+
DEM
+
Drainage network
+
1D/2D simulation
```

### Differentiator 1

```text
Sparse water-level assimilation
```

### Differentiator 2

```text
Probabilistic threshold exceedance
```

### Differentiator 3

```text
Adaptive hotspot refinement
```

### Differentiator 4

```text
Drainage anomaly detection
```

### Product

```text
GIS
+
Explanation
+
Flood-aware routing
```

---

# 27. Phase 2

Add:

* particle-filter/EnKF assimilation,
* GNN hydraulic surrogate,
* blockage inference,
* action optimization,
* sensor placement recommendation.

---

# 28. Phase 3

Add:

* multi-city architecture,
* live municipal integration,
* advanced pump control optimization,
* satellite observations,
* AI rainfall nowcasting,
* traffic prediction,
* fully probabilistic ensemble forecasting.

---

# 29. Acceptance Criteria

The system shall pass the following tests.

### AC-01

Rainfall data are ingested and quality checked.

### AC-02

Rainfall is transformed into catchment runoff.

### AC-03

Surface flow produces spatially varying inundation.

### AC-04

Drainage hydraulics calculate network state.

### AC-05

Surface and drainage domains exchange water dynamically.

### AC-06

Downstream boundary conditions affect predictions.

### AC-07

The system generates a 0–180 minute forecast.

### AC-08

Forecast uncertainty is propagated to flood outputs.

### AC-09

Observed water-level data can update the model state.

### AC-10

Sensor anomalies are detected and isolated.

### AC-11

Hydraulic anomalies can be flagged as suspected infrastructure degradation.

### AC-12

The system identifies flood hotspots before threshold crossing where the forecast permits.

### AC-13

Road accessibility is dynamically updated with forecast time.

### AC-14

Routes consider predicted conditions at the time of road traversal.

### AC-15

The system can evaluate at least one hypothetical intervention.

### AC-16

Forecasts can be replayed against historical events.

### AC-17

Performance is compared against baseline models.

### AC-18

Every forecast retains complete data/model/configuration provenance.

### AC-19

The platform explicitly reports degraded data conditions.

### AC-20

The system does not claim an absolute “safe route” under uncertain forecasts.

---

# 30. Technical Benchmark

The project should publish the following benchmark table for its selected pilot area:

| Metric                   | Baseline | Proposed |
| ------------------------ | -------: | -------: |
| Flood-depth MAE          | measured | measured |
| Spatial IoU              | measured | measured |
| CSI                      | measured | measured |
| Peak-time error          | measured | measured |
| Median lead time         | measured | measured |
| False alarms             | measured | measured |
| Missed hotspots          | measured | measured |
| Runtime                  | measured | measured |
| Forecast update interval | measured | measured |
| Probability calibration  | measured | measured |

No fabricated performance figures shall be used.

---

# 31. Core Research Hypotheses

The system shall be capable of testing the following hypotheses:

### H1

Adding drainage hydraulics improves street-level flood localization compared with rainfall + terrain alone.

### H2

Data assimilation reduces forecast error under imperfect model parameters.

### H3

Adaptive high-fidelity refinement achieves similar decision quality at lower computational cost.

### H4

Probabilistic forecasting produces better operational decisions than deterministic flood labels.

### H5

Hydraulic anomaly detection can identify potential drainage degradation before conventional threshold alerts.

### H6

Intervention simulation can identify actions that materially reduce projected flood impacts.

---

# 32. Final System Identity

The product shall not be marketed as:

> “an AI flood prediction dashboard.”

It shall be positioned as:

> **An adaptive, closed-loop urban flood operating system that continuously synchronizes a physics-based digital twin with real-world observations, predicts probabilistic street-level inundation, diagnoses hidden drainage degradation, dynamically allocates computational fidelity, and recommends risk-aware interventions and routes before flooding peaks.**

---

# 33. Final Architecture

```text
                 REAL CITY
                    │
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
   RAIN           DRAIN          SURFACE
  SENSORS         SENSORS        SENSORS
     │              │              │
     └──────────────┼──────────────┘
                    ▼
             DATA FUSION / QC
                    │
                    ▼
             STATE ASSIMILATION
                    │
                    ▼
              DIGITAL TWIN
             /             \
            /               \
     HYDROLOGY             HYDRAULICS
          │                 │
          └───────┬─────────┘
                  ▼
          ADAPTIVE FORECAST
                  │
        ┌─────────┼──────────┐
        ▼         ▼          ▼
     DEPTH     PROBABILITY  IMPACT
        │         │          │
        └─────────┼──────────┘
                  ▼
          DIAGNOSTIC ENGINE
                  │
          ┌───────┴────────┐
          ▼                ▼
     ROUTING ENGINE    ACTION ENGINE
          │                │
          └───────┬────────┘
                  ▼
              DECISION
                  │
                  ▼
              RESPONSE
                  │
                  ▼
            NEW OBSERVATIONS
                  │
                  └───────────► DIGITAL TWIN
```

# 34. One-Sentence Product Definition

**A real-time, uncertainty-aware urban flood intelligence system that closes the loop between rainfall, surface water, drainage infrastructure and real-world observations to forecast not only where flooding will occur, but why it is occurring, how certain the forecast is, what infrastructure may be failing, and which intervention or route change can reduce the impending impact.**
