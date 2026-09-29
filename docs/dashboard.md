# Operator dashboard (`dashboard/`) — demo of Tasks 1–5

```
python -m tools.export_dashboard      # ~70 s: re-run the models and rebuild dashboard/data/
python -m http.server 8123            # from the repository root
# open http://localhost:8123/dashboard/
```

The page is static: Leaflet + Chart.js, no build step, and it deploys on Vercel as-is. Every
number comes from real model runs, exported by `tools/export_dashboard.py`:

- a Task-1 physics storm run and baselines B1–B5
- a Task-2 `run_forecast` cycle at T+115 min, plus a degraded cycle (radar outage and frozen gauge G3)
- a Task-3 twin experiment: hidden blockage of 2 trunk pipes, 9 virtual sensors (one stuck), and a per-sensor Kalman update
- Task-4 what-if and action runs, each a full coupled-physics simulation

## Views
| | View | SRS modules | Interaction |
|---|---|---|---|
| A | Live situation | V, B, D | twin time slider, health card, observation QC, rainfall chart, alerts |
| B | Forecast | N, W | lead slider; Expected/P10/P50/P90/Peak; click a cell for its forecast, member spaghetti and the **WHY?** diagnosis |
| C | Probability & hotspots | N, M, C | P(>10/20/30 cm) maps, hotspot tiles with early warnings, radar ensemble mini-map, rainfall ensemble |
| D | Drainage health & twin | J, K, L, U, V | pipe utilisation over time, sensors + trust, open loop vs assimilated vs observed, anomaly list, work orders |
| E | Impact & routing | O, P, Q, R | road status per vehicle class and lead; time-dependent 3-route planner (A/B on the map or by block); facility access risk |
| F | Action lab | X, S, T | 5 physics what-ifs (with change vs baseline), action ranking with cost and human approval, road closure, sensor placement advisor |
| G | Validation | Y, Z, §7 | B1–B7 table, surrogate skill vs persistence, forecast verification, provenance record |
| H | System & API | §12–§18 | processing loop timings, `/api/v1/*` response explorer, CAP 1.2 / GeoJSON / SensorThings export, RBAC matrix, audit log |

The header also has a **forecast issue-time selector** for historical replay: cycles at
T+90 (before the squall), T+115 and T+140 min, each verified against the synthetic truth in
view G. The **forecast health card** stays on the map in every view. Also in the header: the
**radar outage drill** (it switches to the real degraded forecast and shows
the DEGRADED banner) and a role selector that locks views per role.

## What is live vs pre-computed
- **Computed in the browser:**
  - routing: time-dependent A* over the forecast depth and exceedance maps at the predicted arrival time
  - road status per vehicle class
  - facility access risk
  - sensor placement: greedy selection on forecast spread
  - the WHY? factors
  - the CAP alert, the exports and the audit log
- **Pre-computed by the exporter:** everything that needs the physics or the ensemble. The dashboard replays three forecast cycles. It does not run a 5-minute server loop.
- **Not built yet:** the FastAPI server, database and authentication (Task 5 backend) and a full EnKF (Task 3). The API explorer shows the response each endpoint will return, taken from the bundle.
