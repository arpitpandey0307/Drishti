# Drishti — Demo Script & Explainer

**SIH 2026 · PS SIH26085 · Team LLMao**
*Use this document to present, demo and defend Drishti. Every number in it comes from the model runs in
this repository. Lines in "Say" blocks are meant to be spoken; everything else is for you.*

---

## How to use this document

| If you have… | Use |
|---|---|
| 2 minutes | [§1 The 60-second pitch](#1-the-60-second-pitch) + the loop diagram |
| 7 minutes (slides) | [§5 Slide-by-slide talk track](#5-slide-by-slide-talk-track) |
| 10 minutes (live) | [§4 Live demo walkthrough](#4-live-demo-walkthrough) |
| Judges' questions | [§7 Q&A bank](#7-qa-bank) |
| A technical reviewer | [§6 Technical deep dive](#6-technical-deep-dive) |

```mermaid
pie showData
    title Suggested 15-minute slot
    "Problem & idea (slides 1-2)" : 3
    "How it works (slide 3)" : 3
    "Live demo" : 6
    "Feasibility & impact (slides 4-5)" : 2
    "References & close (slide 6)" : 1
```

---

## Contents

1. [The 60-second pitch](#1-the-60-second-pitch)
2. [The problem, explained](#2-the-problem-explained)
3. [The solution, explained](#3-the-solution-explained)
4. [Live demo walkthrough](#4-live-demo-walkthrough)
5. [Slide-by-slide talk track](#5-slide-by-slide-talk-track)
6. [Technical deep dive](#6-technical-deep-dive)
7. [Q&A bank](#7-qa-bank)
8. [Pre-demo checklist & fallbacks](#8-pre-demo-checklist--fallbacks)
9. [Glossary](#9-glossary)

---

## 1. The 60-second pitch

> **Say:** "Every monsoon, Indian cities flood in minutes. The warnings people get are city-wide —
> *heavy rain expected*. But a traffic officer, an ambulance dispatcher or a drainage engineer needs to
> know **which street**, **when**, **how deep**, **why**, and **what to do**.
>
> Drishti is a digital twin of a campus's streets and drains. Every five minutes it takes the rain it can
> see, forecasts twenty possible rain futures for the next three hours, runs them through a physics model
> of how water flows over the ground and through the pipes, and turns that into street-level flood
> forecasts — with a confidence band, a reason, and a recommended action.
>
> It runs a full cycle in about 19 seconds on a laptop CPU. In replayed storms it warned 67% of the
> cells that later flooded, with 2% false alarms. And when the radar fails, it doesn't guess silently —
> it falls back to gauges and says DEGRADED on screen."

```mermaid
flowchart LR
    O(["OBSERVE<br/>rain"]) --> Q(["CHECK<br/>quality"]) --> F(["FORECAST<br/>20 futures"]) --> W(["WARN<br/>street by street"]) --> A(["ACT<br/>human approves"]) --> O
    style O fill:#EFF6FF,stroke:#2563EB
    style Q fill:#FEF2F2,stroke:#DC2626
    style F fill:#FFFBEB,stroke:#D97706
    style W fill:#F5F3FF,stroke:#7C3AED
    style A fill:#ECFDF5,stroke:#059669
```

---

## 2. The problem, explained

### 2.1 Why urban floods are hard to predict

```mermaid
mindmap
  root((Urban flash flood))
    Rain
      Convective cells move and grow
      60-115 mm days every year in Ghaziabad
      Radar can fail or be biased
    Ground
      Water follows terrain to low points
      Roads and roofs are impervious
      Buildings block and divert flow
    Drains
      Sized for about 40 mm/h
      Blockage from silt and garbage
      Surcharge pushes water back up
      Backwater from the receiving nala
    People
      Need street-level answers
      Need lead time, not hindsight
      Lose trust after false alarms
```

> **Say:** "Flooding on a street is the result of three systems interacting: the rain, the ground, and the
> drains. You can't predict it from rainfall alone — our own baseline that uses only a rainfall
> threshold gets a CSI of 0.11 and nine false alarms out of ten. You need all three, coupled."

### 2.2 Who needs the answer

```mermaid
flowchart TB
    D((Drishti forecast))
    D --> OP["Flood control operator<br/>WHERE and WHEN will it flood?"]
    D --> DI["Emergency dispatcher<br/>Which route stays open for the ambulance?"]
    D --> IE["Infrastructure engineer<br/>Which drain is blocked? What should we fix first?"]
    D --> ME["Model engineer<br/>How good is the forecast? Can I replay it?"]
    D --> AD["Administrator<br/>Who can see and change what?"]
    D --> PU["Public<br/>Is my road safe to use in 30 minutes?"]
```

These six roles are real in the dashboard: the **role selector** in the header locks views per role
(for example, a public viewer only sees Situation, Forecast and Roads).

### 2.3 The five questions

| # | Question | Drishti's answer | Where it is shown |
|---|---|---|---|
| Q1 | **WHERE?** | Flood depth on a 5 m grid, per road segment | Forecast view (B), map |
| Q2 | **WHEN?** | Time to 10 cm, peak time, duration | Click any cell in view B |
| Q3 | **HOW BAD?** | Expected / P10 / P50 / P90 depth, P(depth > 10/20/30 cm) | Views B and C |
| Q4 | **WHY?** | Rainfall / runoff / terrain / drainage / asset / boundary factors | "Why here?" panel in view B |
| Q5 | **WHAT NOW?** | Ranked interventions, 3 alternative routes, work orders | Views E and F |

---

## 3. The solution, explained

### 3.1 The closed loop

```mermaid
flowchart TB
    subgraph LOOP["Every 5 minutes"]
        direction LR
        A[Observe] --> B[Ingest + QC] --> C[Estimate state] --> D[Forecast] --> E[Quantify uncertainty]
        E --> F[Identify impact] --> G[Diagnose drains] --> H[Simulate interventions] --> I[Recommend]
    end
    I -. "operator approves" .-> J[Act]
    J -. "new observations" .-> A
    G -. "update the twin" .-> C
```

> **Say:** "This is the difference between a dashboard and a digital twin. A dashboard shows you data.
> A twin keeps a running model of the physical system, corrects it with every new observation, and uses
> it to look ahead."

### 3.2 System architecture

```mermaid
flowchart TB
    subgraph L1["1 · Data sources"]
        DEM[Copernicus DEM<br/>30 m]
        OSM[OpenStreetMap]
        RD[Radar / gauges /<br/>GPM-IMERG]
        SEN[Water-level sensors]
    end
    subgraph L2["2 · Twin + physics"]
        TW[Terrain twin<br/>160 x 110 cells, 5 m]
        NET[Drain network graph<br/>63 nodes, 61 links]
        PHY[Coupled 1D/2D solver]
    end
    subgraph L3["3 · Forecast + learning"]
        QC[Quality engine]
        ST[STEPS nowcast]
        SU[U-Net surrogate]
        AD[Hotspot refinement]
        DA[Assimilation +<br/>drainage health]
    end
    subgraph L4["4 · Decisions"]
        IM[Road + facility impact]
        RO[Time-dependent routing]
        WI[What-if + action lab]
        SP[Sensor placement]
    end
    subgraph L5["5 · Platform"]
        UI[Dashboard A-H]
        API["/api/v1 + CAP 1.2"]
        SEC[RBAC + audit]
    end
    DEM & OSM --> TW --> NET --> PHY
    RD --> QC --> ST --> SU
    PHY --> SU
    SU --> AD --> IM
    SEN --> DA --> PHY
    IM --> RO & WI & SP
    RO & WI & SP --> UI & API
    UI --- SEC
```

### 3.3 The tech inside each box

| Box | Method | Code |
|---|---|---|
| Terrain twin | Copernicus GLO-30 → bilinear to 5 m, priority-flood fill, D8 flow, low points; OSM roads and buildings rasterised | `simulation/terrain/twin.py` |
| Drain network | Inlets placed by flow accumulation + low points + road proximity; Dijkstra tree to outfalls; Rational-method sizing | `simulation/drainage/network.py` |
| Coupled physics | 2D diffusive-wave storage cells + 1D local-inertial pipes + weir/orifice exchange | `simulation/hydraulics/simulate.py` |
| Quality engine | Range, spike, frozen, drift, stale, coverage, gauge-vs-radar checks | `forecast/quality.py` |
| STEPS nowcast | Optical flow + 6-level FFT cascade with AR(2) + spectral noise + NWP blend | `forecast/steps.py`, `forecast/motion.py` |
| Surrogate | Residual U-Net, 36 input channels → depth at 14 leads, exported to ONNX | `forecast/surrogate/` |
| Hotspots | 80 m tiles; full physics for the P50 and P90 members where risk or spread is high | `forecast/adaptive.py` |
| Probabilistic forecast | Per cell and per road: P10/P50/P90, peak, time-to-10 cm, duration, exceedance | `forecast/probabilistic.py` |
| Assimilation + health | Per-sensor Kalman bias update, innovation-based fault isolation, residual z-scores | `tools/export_dashboard.py` |
| Routing | Time-dependent A* — each edge is costed at the predicted arrival time | `dashboard/app.js`, `api/route.py` |

### 3.4 What makes it different

```mermaid
flowchart LR
    subgraph T["Typical flood dashboard"]
        T1[Rainfall threshold] --> T2[City-wide alert]
    end
    subgraph P["Pure AI model"]
        P1[Rain history] --> P2[Black-box depth map]
    end
    subgraph DR["Drishti"]
        D1[QC'd rain ensemble] --> D2[Physics twin] --> D3[AI copy for speed] --> D4[Physics re-check at hotspots] --> D5[Probability + reason + action]
        S1[Sensors] -.-> D2
    end
```

---

## 4. Live demo walkthrough

### 4.0 Setup (do this before you walk in)

```bash
cd Drishti
python -m http.server 8123
# open two tabs:
#   http://localhost:8123/                         (landing page, 3D replay)
#   http://localhost:8123/dashboard/               (operator dashboard)
```

Backup: the same pages are hosted at `https://drishti-sand.vercel.app/` and
`https://drishti-sand.vercel.app/dashboard/`. The 4:51 explainer video is `brag-output/brag.mp4`.

```mermaid
journey
    title The demo path (about 6 minutes)
    section Hook
      3D storm replay on the homepage: 5: Presenter
    section Forecast
      Situation and health card: 4: Presenter
      Forecast slider and Why here: 5: Presenter
      Hotspots and early warnings: 5: Presenter
    section Diagnose
      Drainage health and suspected faults: 5: Presenter
    section Decide
      Roads and three routes: 5: Presenter
      Action lab what-ifs: 4: Presenter
    section Trust
      Radar outage drill: 5: Presenter
      Validation view: 4: Presenter
```

### Step 1 — The hook: the 3D replay (30 s)

![Homepage](images/screenshots/home.jpg)

**Do:** open the landing page and let the storm play. Drag to orbit.

> **Say:** "This is the real KIET campus terrain, the real buildings from OpenStreetMap, and our drain
> network in green. The rain falling is a simulated squall moving across campus. Watch the water collect
> — it doesn't spread evenly, it runs to the low points and backs up where the drains can't take it.
> The water columns are drawn twelve times taller than life so you can see them. The panel on the right
> is live: rain rate, flooded area, the deepest street cell."

**Do:** click **Open the operations dashboard**.

### Step 2 — Situation (view A) (45 s)

![Situation view](images/screenshots/dash_live.jpg)

**Point at:** the **Forecast health** card (top right of the map, always visible), the header's
**Forecast issued** selector and the green **OPERATIONAL · radar** pill.

> **Say:** "This is what an operator sees first. Top right is the forecast health card — rain source,
> how many gauges are valid, how many sensors we trust, the uncertainty level and when the forecast was
> issued. It never leaves the screen, because a forecast is only as good as the data behind it.
> The header lets me replay three forecast cycles of the same storm: before it arrived, once it was
> established, and later."

### Step 3 — Forecast (view B) and "Why here?" (90 s)

![Forecast view](images/screenshots/dash_forecast.jpg)

**Do:** press **B**. Drag the lead-time slider from +5 to +180 min. Switch **Expected / P10 / P50 / P90 /
Peak**. Then click a coloured cell near a building.

> **Say:** "Now I'm looking ahead. This slider runs from five minutes to three hours. Blue is shallow,
> orange is deep. These buttons switch between the expected depth and the pessimistic P90 — the depth we
> are 90% sure won't be exceeded. When I click a street cell I get its own forecast: depth now, depth at
> my chosen lead, expected peak and when, and **when it reaches 10 centimetres**. The grey lines are the
> twenty ensemble members — that spread is our uncertainty, shown, not hidden.
>
> And underneath: **Why here?** Drishti breaks the risk into rainfall, runoff, terrain, drainage, known
> faults and the downstream boundary, and names the main driver. That answers the question every
> engineer asks: *why is this street flooding?*"

### Step 4 — Hotspots (view C) (45 s)

![Hotspots view](images/screenshots/dash_prob.jpg)

**Do:** press **C**. Toggle **> 10 / > 20 / > 30 cm**. Point at the hotspot list and the radar mini-map.

> **Say:** "This is the probability view — the chance each cell goes above 10, 20 or 30 centimetres. The
> outlined tiles are hotspots: places with high risk, high uncertainty, or next to a building. For those,
> Drishti re-runs the full physics model instead of trusting the AI copy. Some are marked **early
> warning**: still dry now, but more likely than not to cross 10 cm. At the forecast issued before the
> squall, these warnings came a median of 50 minutes ahead."

### Step 5 — Drainage health (view D) (60 s)

![Drainage view](images/screenshots/dash_drain.jpg)

**Do:** press **D**. Point at the **Assimilation** chart, the **Suspected faults** list and **Sensor trust**.

> **Say:** "This is the part a normal flood map can't do. We hid two blocked pipes in the 'true' storm,
> and put nine virtual water-level sensors in the drains — one of them stuck. The chart compares the
> model running blind — the open loop — against the model corrected by sensors. Sensor-level error
> drops from 19.9 cm to 2.7 cm.
>
> Then it diagnoses. Sensor S-27 has been reading the same value for 20 minutes while the model says the
> level is changing — trust drops to 0.28 and it is ignored. Pipe P-49 reads 30 cm higher than it should
> under the same rain — likely blocked, and it was one of the two we hid. Each fault comes with evidence,
> a likelihood and a work order — never a definitive claim, and never automatic control."

### Step 6 — Roads & routes (view E) (60 s)

![Roads view](images/screenshots/dash_impact.jpg)

**Do:** press **E**. Change the vehicle class (car → ambulance). Pick **From** and **To** blocks, set
**Leave: in 30 min**, press **Find three routes**. Toggle the **emergency policy**.

> **Say:** "Floods matter because of what they cut off. Every road segment gets a status — passable,
> degraded, high risk, impassable — and the thresholds depend on the vehicle: a two-wheeler is in trouble
> at 7 cm, a fire truck can go through 35. The route planner is time-dependent: if I leave in 30 minutes,
> each road is costed at the water level **when I'm predicted to reach it**, not now. I get three routes
> with ETA and the probability of hitting deep water. Notice we never call a route 'safe' — only lower
> risk."

### Step 7 — Action lab (view F) (45 s)

![Action lab](images/screenshots/dash_actions.jpg)

**Do:** press **F**. Pick **Pump P-60 fails**, tick **show change vs baseline**. Then point at the
**Interventions** table and **Request approval**.

> **Say:** "What if? Each of these is a full physics run of the same storm. If the pump fails, flooded
> area goes from 5,800 to 8,000 square metres and 3,400 cubic metres overflow from the drains. If the
> receiving nala backs up by two metres, flooded area doubles. Below, the interventions — run the pump,
> jet the drains, or both — ranked by effect and cost. The recommendation needs a human to approve it.
> And at the bottom: where to put the next sensor to cut uncertainty the most."

### Step 8 — The honesty moment: radar outage drill (30 s)

![Degraded mode](images/screenshots/dash_degraded.jpg)

**Do:** tick **Radar outage drill** in the header.

> **Say:** "Now the radar goes down. This isn't a fake banner — it switches to a real forecast computed
> with no radar and a frozen gauge. Drishti falls back to the gauges, rejects the frozen one, widens the
> uncertainty and says **DEGRADED** at the top of every view. Skill drops — early-warning hits fall from
> 67% to 26% — but there are still zero false alarms, and the operator knows exactly how far to trust it."

**Do:** untick the drill.

### Step 9 — Validation (view G) (30 s)

![Validation view](images/screenshots/dash_validation.jpg)

> **Say:** "Finally, how good is it? Top: which parts of the model matter — rainfall alone scores 0.11,
> adding terrain 0.43, runoff 0.53, the full coupled model is the reference. Middle: the AI surrogate
> against persistence — at three hours it scores 0.79 where persistence falls to 0.24. Bottom: the
> forecast issued at T+115 — 67% of later-flooded cells warned in time, 2% false alarms. One honest
> caveat on screen: these are scored against our synthetic truth, not observed floods yet."

### Optional — System (view H)

![System view](images/screenshots/dash_system.jpg)

> **Say:** "For the IT team: the five-minute loop and how long each stage takes, the API endpoints with
> their real responses, CAP 1.2 alert export for India's alerting systems, GeoJSON for navigation apps,
> the role matrix and the audit log."

---

## 5. Slide-by-slide talk track

The deck is `ppt/Drishti_SIH26085.pptx` (6 slides, SIH 2026 template). Speaker notes are embedded in
each slide.

```mermaid
flowchart LR
    S1["1 · Title<br/>PS, theme, team"] --> S2["2 · The idea<br/>6-step flow, 5 questions,<br/>drainage watchdog"]
    S2 --> S3["3 · Technical approach<br/>9 blocks, forecast cycle"]
    S3 --> S4["4 · Feasibility & viability<br/>cost, readiness, risks"]
    S4 --> S5["5 · Impact & benefits<br/>benefit flow, metrics"]
    S5 --> S6["6 · Research & references<br/>papers, standards, links"]
```

| Slide | Time | Key line | Point at |
|---|---|---|---|
| 1 · Title | 15 s | "Drishti tells a city where water will stand on its streets, up to three hours before it does." | PS ID and title |
| 2 · Idea | 60 s | "Observe, check, forecast twenty futures, run physics, run the AI copy, decide — every five minutes." | The six cards left → right, then the five-question ladder |
| 3 · Technical | 90 s | "Physics where it matters, AI where it's fast." | Block 4 (the cycle) top to bottom, then the *Why hybrid?* box |
| 4 · Feasibility | 45 s | "It runs today — 19 seconds, on a laptop, with open data." | Readiness bars, the rainfall chart, the challenge table |
| 5 · Impact | 45 s | "Warnings before the water, routes for the ambulance, the right pipe fixed first." | The benefit flow row |
| 6 · References | 15 s | "Every method traces to published work; the links open the live system." | The app thumbnails |

**Slide 3 in detail** — walk the centre column:

1. *Rain observations* → *Quality check* ("a faulty reading is rejected, and logged").
2. *Radar usable?* → if not, "gauges only, and we say DEGRADED".
3. *Ensemble nowcast* → "20 possible rain futures".
4. *Twin state at t0* → *AI surrogate depths* → "0.2 seconds for all 20".
5. *Hotspot risk?* → "full physics refine only where it matters".
6. *Probabilistic forecast* → *Crosses 10 cm?* → early warning.
7. *Impact · routes · alert* → audit ledger.

---

## 6. Technical deep dive

### 6.1 One physics time step

```mermaid
flowchart TD
    R["Rain for this 5-min step<br/>split into 150 x 2 s substeps"] --> IC["Interception<br/>open ground 1 mm"]
    IC --> INF["Infiltration<br/>Horton f = fc + (f0 - fc) e^-kt<br/>or SCS-CN"]
    INF --> DEP["Depression storage<br/>open 2.5 mm, road 1.0 mm"]
    DEP --> SURF["2D surface flux per face<br/>q = h^5/3 / n * sqrt(S) * dx<br/>S capped at 0.05, 1/8-volume limiter"]
    SURF --> EX{"Node head<br/>vs ground?"}
    EX -- "below ground" --> CAP["Capture: min(weir, orifice)<br/>capped by inlet rating"]
    EX -- "pressurised" --> SUB["Submerged orifice<br/>on head difference"]
    EX -- "above ground" --> SUR["Surcharge: water returns<br/>to the street cell"]
    CAP & SUB --> PIPE["1D local-inertial momentum per pipe<br/>node continuity with storage"]
    PIPE --> OUT["Outfalls / pump station"]
    SUR --> SURF
    OUT --> MB["Mass balance check<br/>relative error ~1e-8"]
```

**Key equations**

| Process | Equation | Parameters |
|---|---|---|
| Surface flux (Manning, wide channel) | `q = h_flow^(5/3) / n · √S · dx` | `S = min(|Δws|/dx, 0.05)`, dt = 2 s |
| Stability limiter | `q_face ≤ 0.125 · h_upwind · dx² / dt` | conservative, explicit |
| Horton infiltration | `f(t) = fc + (f0 − fc) · e^(−k t)` | road 5/1 mm/h, open 35/8 mm/h |
| SCS-CN | `Q = (P − Ia)² / (P − Ia + S)`, `S = 25400/CN − 254` mm | chosen in `config/hydraulics.yaml` |
| Pipe full capacity | `Qcap = (1/n) · (πD²/4) · (D/4)^(2/3) · √S` | n = 0.013 concrete |
| Inlet exchange | weir `Cw · P · h^1.5`, orifice `Co · Ao · √(2 g h)` | min of the two, capped |
| Mass balance | `rain + inflow = infiltration + outflow + surface + depression + interception + node storage` | reported per run |

### 6.2 Rain nowcast (STEPS)

```mermaid
flowchart LR
    A["Last radar frames<br/>1 km, 192 x 192 km"] --> B["Gauge bias correction<br/>60 min window, clipped 0.33-3"]
    B --> C["Motion field<br/>pyramidal Lucas-Kanade on dBR"]
    C --> D["Lagrangian alignment<br/>of the last 3 frames"]
    D --> E["6-level FFT cascade<br/>AR(2) per level"]
    E --> F["Per-member spectral noise<br/>+ motion perturbation"]
    F --> G["Probability matching<br/>semi-Lagrangian extrapolation"]
    G --> H["Blend with NWP / climatology<br/>weight 1.0 to 30 min, 0.85 at 60,<br/>0.45 at 120, 0.2 at 180"]
    H --> I["20-member rain ensemble<br/>0-180 min"]
```

pysteps has no Python 3.14 wheel, so the algorithm is re-implemented in NumPy following pysteps.
Member 0 is the unperturbed control.

### 6.3 AI surrogate: data → model → deployment

```mermaid
flowchart TB
    subgraph DATA["Training data from our own physics"]
        A["290 storms x 6 h<br/>260 in-distribution + 30 out-of-distribution"]
        B["Rain families: regional storms,<br/>spec patterns, random pulses<br/>blockage 0-0.5 (OOD: 1.8-2.5x rain, 0.75)"]
    end
    subgraph MODEL["Residual U-Net"]
        C["36 inputs: 9 static + 6 steps of rain and depth history<br/>+ cumulative future rain per lead + blockage plane"]
        D["depth(t0 + lead) = relu(depth(t0) + delta)"]
        E["14 outputs: 5, 10, 15, 20, 30, 40, 50, 60,<br/>75, 90, 105, 120, 150, 180 min"]
    end
    subgraph SHIP["Deployment"]
        F["ONNX, 1 MB, 270,182 parameters"]
        G["0.2 s for 20 members on CPU"]
    end
    A --> B --> C --> D --> E --> F --> G
```

Splits are **by scenario, never by window**, so the test set contains storms the model has never seen.

### 6.4 Adaptive fidelity (hotspot refinement)

```mermaid
flowchart TD
    A["Surrogate ensemble<br/>20 members"] --> B["Split domain into<br/>16 x 16-cell tiles (80 m)"]
    B --> C{"Any of:<br/>P(depth > 20 cm) >= 0.3<br/>P90 - P10 peak >= 10 cm<br/>P(> 10 cm) >= 0.1 within 25 m of a building"}
    C -- "no" --> K[Keep surrogate result]
    C -- "yes: hotspot" --> D["Run full coupled physics for the<br/>P50 and P90 rain members (2 processes)"]
    D --> E["Replace those members inside hotspot tiles;<br/>shift the rest by the nearest physics-minus-surrogate correction"]
    E --> F{"Dry now but<br/>P(reach 10 cm) >= 0.5?"}
    F -- "yes" --> G[Mark EARLY WARNING]
```

### 6.5 Forecast cycle as a sequence

```mermaid
sequenceDiagram
    autonumber
    participant S as Sources (radar, gauges)
    participant Q as Quality engine
    participant N as STEPS nowcast
    participant T as Physics twin
    participant M as Surrogate (ONNX)
    participant H as Hotspot refiner
    participant P as Probabilistic forecast
    participant O as Operator
    S->>Q: observations at t0
    Q->>Q: VALID / SUSPECT / STALE / MISSING / FAULT
    Q->>N: usable radar + valid gauges (or DEGRADED)
    N->>M: 20 rain members, 0-180 min
    T->>M: twin state at t0 (physics on observed rain)
    M->>H: 20 depth members, 14 leads
    H->>T: re-run P50 and P90 members on hotspot tiles
    T-->>H: refined depths
    H->>P: merged ensemble
    P->>O: maps, exceedance, early warnings, road impact, health card
    Note over P,O: whole cycle about 19 s on a laptop CPU
```

### 6.6 Degraded modes

```mermaid
stateDiagram-v2
    [*] --> Operational
    Operational: OPERATIONAL<br/>radar + gauge bias correction
    GaugeOnly: DEGRADED<br/>gauge IDW, noise x1.5, nowcast weight x0.6
    Climatology: DEGRADED<br/>NWP / climatology only
    Operational --> GaugeOnly: radar missing, stale or faulty and >= 3 valid gauges
    GaugeOnly --> Climatology: fewer than 3 valid gauges
    Operational --> Climatology: no radar and fewer than 3 gauges
    GaugeOnly --> Operational: last 3 radar frames usable again
    Climatology --> GaugeOnly: gauges recover
    Climatology --> Operational: radar and gauges recover
```

Every cause is listed in `health.reasons` (e.g. `radar MISSING`, `G3 = FAULT (frozen)`).

### 6.7 Closed loop: assimilation and diagnosis

```mermaid
sequenceDiagram
    participant TR as Hidden truth (2 blocked pipes)
    participant VS as 9 virtual sensors
    participant TW as Open-loop twin
    participant KF as Kalman update
    participant DX as Diagnosis
    participant EN as Engineer
    TR->>VS: true water levels + noise, dropouts, 1 stuck sensor
    TW->>KF: modelled level at each sensor
    VS->>KF: observed level
    KF->>KF: innovation check, trust score per sensor
    KF-->>DX: S-27 constant for 20+ min, trust 0.28, isolated
    KF->>TW: bias-corrected state (error 19.9 cm to 2.7 cm)
    TW->>DX: residuals under the same rain and boundary
    DX->>EN: P-49 likely blocked (likelihood 0.65, +30 cm), CCTV / rodding
    EN-->>DX: approve or reject the work order
```

### 6.8 Routing

```mermaid
flowchart LR
    A["Origin, destination,<br/>vehicle, departure time,<br/>risk tolerance"] --> B["Road graph from OSM"]
    B --> C["A* search: for each edge,<br/>predict arrival time t"]
    C --> D["Look up forecast depth and<br/>P(depth > vehicle threshold) at t"]
    D --> E["Cost = travel time + flood exposure<br/>+ failure probability (weighted by tolerance)"]
    E --> F["3 alternative routes<br/>ETA + risk, never 'safe'"]
```

| Vehicle | Degraded above | Impassable above |
|---|---|---|
| Two-wheeler | 7 cm | 15 cm |
| Car | 10 cm | 30 cm |
| Ambulance | 15 cm | 35 cm |
| Bus | 25 cm | 45 cm |
| Fire truck | 35 cm | 60 cm |

The **emergency policy** toggle lets emergency vehicles use 5–10 cm deeper water and restricts public
traffic earlier.

### 6.9 Roles and access

```mermaid
flowchart LR
    ADM[System administrator] --> ALL["A-H: all views"]
    OPR[Flood control operator] --> ALL
    DIS[Emergency dispatcher] --> V1["A Situation · B Forecast<br/>C Hotspots · E Roads"]
    MOD[Model engineer] --> V2["A · B · C · D Drainage<br/>G Validation · H System"]
    INF[Infrastructure engineer] --> V3["A · D Drainage<br/>F Action lab · G Validation"]
    PUB[Public viewer] --> V4["A · B · E Roads"]
```

### 6.10 Provenance: every run is replayable

```mermaid
erDiagram
    FORECAST_RUN ||--o{ INPUT_VERSION : uses
    FORECAST_RUN ||--|| MODEL_VERSION : runs
    FORECAST_RUN ||--|| CONFIG : "hashed with"
    FORECAST_RUN ||--|| HEALTH : reports
    FORECAST_RUN ||--o{ OUTPUT : produces
    FORECAST_RUN {
        string forecast_id
        float t0_min
        string code_commit
        float cycle_seconds
    }
    INPUT_VERSION {
        string source
        string status
        string provenance
    }
    MODEL_VERSION {
        string surrogate
        int parameters
    }
    HEALTH {
        string status
        string reasons
        float uncertainty_inflation
    }
    OUTPUT {
        string kind
        string label
    }
```

`label` is always one of *observed / derived / modelled / synthetic*, and the dashboard shows it as a
tag on every panel.

### 6.11 Deployment

```mermaid
flowchart LR
    subgraph DEV["Build machine"]
        PY["Python models<br/>simulation/ + forecast/"]
        EXP["tools/export_dashboard.py"]
    end
    subgraph STATIC["Static hosting (today)"]
        V["Vercel / Render<br/>index.html · dashboard/ · data bundle"]
        HF["Hugging Face Space<br/>in-browser ONNX demo"]
    end
    subgraph NEXT["Planned (Task 5 backend)"]
        API["FastAPI /api/v1"]
        DB[("PostGIS")]
        SCH["Scheduler: 5-min loop"]
        AUTH["JWT + RBAC + audit"]
    end
    PY --> EXP --> V
    PY --> HF
    SCH --> PY
    PY --> DB --> API
    AUTH --- API
    API -. "same JSON as the bundle" .-> V
```

---

## 7. Q&A bank

| Likely question | Answer |
|---|---|
| **Are these real drains?** | No. KIET has no surveyed drain map, so the network is generated from terrain and roads and every asset is tagged `verified=false`. A surveyed network drops in with the same JSON schema — no code change. |
| **Can a 30 m DEM drive a 5 m model?** | It gives the broad fall of the land, not kerb-level detail — and the UI says so (data tier 1). A LiDAR or drone DEM replaces it directly. |
| **How do you know the model is right without flood data?** | Three ways: the physics conserves mass to ~1e-8 and passes 31 tests; twin experiments score the forecast against a hidden simulated truth; and the replay/validation view is ready for observed events. We do not claim real-world skill yet. |
| **Why not just train an AI on rainfall?** | Our rainfall-threshold baseline scores CSI 0.11. Flooding depends on terrain and drains; an AI trained on our own physics learns that coupling, and hotspots are re-checked with the physics. |
| **Why is the AI needed if you have physics?** | 20 members × ~12 s of physics ≈ 4 minutes; the surrogate does all 20 in 0.2 s, so the cycle fits in 19 s. |
| **How accurate is the surrogate?** | CSI at 10 cm of 0.82 at +30 min and 0.79 at +180 min on held-out storms, vs 0.58 and 0.24 for persistence; it holds up on out-of-distribution storms (0.78 at +180). |
| **What happens when the radar fails?** | Gauge-only forecast, uncertainty ×1.5, DEGRADED banner. In our drill, early-warning hits fell from 67% to 26% but false alarms stayed at 0%. |
| **Are the probabilities calibrated?** | Not yet — the ensemble is under-dispersive (P10–P90 covers the truth in 5–50% of active cells). Calibration needs assimilation of real data over many events; it is on the roadmap and stated on screen. |
| **Does it control pumps automatically?** | No. It recommends; a human approves. That is a design rule, not a missing feature. |
| **How does it scale to a city?** | The terrain twin, network and configs are per area; a ward is a config. The heavy work is offline training; the live loop is CPU-only. |
| **What does it cost?** | Indicatively ₹7–12.5 lakh for one ward, mostly sensors and a drain survey. Software and data are open; no GPU or per-forecast cloud bill. |
| **What's not built yet?** | The FastAPI server, database and authentication (the dashboard shows the exact responses each endpoint will return), and a full ensemble Kalman filter in place of the per-sensor update. |
| **Which standards do you follow?** | OASIS CAP 1.2 for alerts, GeoJSON for roads and routes, a SensorThings-style observation schema, EPA SWMM `.inp` export for cross-checking the drains. |

---

## 8. Pre-demo checklist & fallbacks

```mermaid
flowchart TD
    A[30 min before] --> B{Laptop online?}
    B -- "yes" --> C[Open Vercel links as backup tabs]
    B -- "no" --> D["Run python -m http.server 8123<br/>everything is local"]
    C & D --> E{Map tiles load?}
    E -- "yes" --> F[Satellite 3D map]
    E -- "no" --> G["Switch map to Chart mode<br/>(2D/3D and Sat toggles top-left)"]
    F & G --> H{Browser WebGL OK?}
    H -- "yes" --> I[Live demo]
    H -- "no" --> J["Play brag-output/brag.mp4<br/>then use screenshots in this doc"]
```

- [ ] `python -m http.server 8123` running from the repo root
- [ ] Landing page and `dashboard/` open in two tabs; browser zoom 100%
- [ ] Forecast issued = **T+115 min**; Radar outage drill **off**; role = Flood Control Operator
- [ ] Deep links ready: `dashboard/#forecast&lead=6`, `#prob`, `#drain`, `#impact`,
      `#actions&scen=pump_failure&diff=1`, `#live&drill=1`, `#valid`
- [ ] `brag-output/brag.mp4` downloaded locally
- [ ] Deck `ppt/Drishti_SIH26085.pptx` open in presenter view (speaker notes on)

---

## 9. Glossary

| Term | Meaning |
|---|---|
| **Nowcast** | A forecast for the next 0–3 hours, built mostly from current observations |
| **Ensemble / member** | One of 20 equally plausible rain futures; their spread is the uncertainty |
| **P10 / P50 / P90** | Depth that 10 / 50 / 90% of members stay below |
| **CSI** | Critical Success Index: hits ÷ (hits + misses + false alarms); 1 is perfect |
| **Persistence** | The baseline "whatever is flooded now stays flooded" |
| **Surrogate** | A neural network trained to imitate the physics model, much faster |
| **Surcharge** | A drain so full that water is pushed back up onto the street |
| **Backwater** | Water in the receiving nala or river stopping the drains from emptying |
| **Assimilation** | Correcting the model's state with live sensor readings |
| **Open loop** | The model running without any sensor correction |
| **STEPS** | Short-Term Ensemble Prediction System — the rain nowcasting method |
| **DEM / DSM** | Digital elevation / surface model (a DSM includes buildings and trees) |
| **CAP 1.2** | Common Alerting Protocol — the standard format for public warnings |
| **Level-1 data** | Demonstration tier: public rain and terrain, synthetic drains and sensors |
