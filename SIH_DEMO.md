# SIH 26085 — Working Demo Runbook (Drishti Flood Nowcasting)

All drainage is **SYNTHETIC / unverified** — demo only, never engineering truth.

## 1. Live model demo (no install, runs in browser)

Open **https://aman34243-drishti-flood-nowcast.static.hf.space/**
→ pick storm window + lead time → Predict + route.
Model (476k-param U-Net → ONNX) runs on-device; free HF static hosting, never sleeps.
Deep-linkable: `?window=0&lead=30`. Weights: `Aman34243/drishti-flood-nowcaster`.

## 1b. End-user product: Flood Risk & Safe Route Planner

Open **`flood_planner.html`** (landing card “Interactive Flood Risk & Safe Route Planner”,
placed after Flood Nowcasting Demo — all older cards unchanged).
Tap any location for depth/peak/onset/risk NOW→+180 min, set origin/destination for
normal vs flood-aware routes on the OSM road graph. Data: `planner/storms/` (baked
baseline-U-Net predictions, int16-mm bins + meta; regen: snippet in §4 flow).
Deep-linkable: `?storm=1&h=9&selftest=1`.

## 2. Physics viewer (localhost)

```
python3 -m http.server 8123
# open http://localhost:8123/flood_viewer.html   (10 sim scenarios + 2 v1 + model nowcasts)
# landing: http://localhost:8123/index.html
```

## 3. Route on live HF predictions (CLI, needs `pip install onnxruntime numpy`)

```
python3 -m api.route_nowcast --window 0 --lead-min 30 --from 20,20 --to 90,140
# → JSON {scenario, max_depth_m, flooded_m2, route_blocked, route_length_m}
# Downloads weights+inputs from the Space (cached in /tmp/space_cache), predicts locally.
```

## 4. Retrain / re-export (dev)

```
python3 -m models.train_baseline --smoke                       # pipeline check
python3 -m visualization.data_adapter.export_viz --split v1demo --max 2
python3 -m visualization.data_adapter.validate_viz             # ALL CHECKS PASSED
python3 -m pytest tests/test_route.py tests/test_route_nowcast.py -q
```

## 5. Refresh hosted artefacts

```
hf upload Aman34243/drishti-flood-nowcaster /tmp/hf_model       # weights + card
hf upload Aman34243/drishti-flood-nowcast /tmp/space --type space  # static demo
```

## SIH checklist mapping

| PS asks | Where it works |
|---|---|
| 0–3h street-level nowcast | Space demo (5–180 min) + `models/` |
| Rainfall + DEM + drain graph coupling | `simulation/` + `dataset/` + viewer |
| Hydraulic capacity / blockage / backflow | pipes + surcharge in viewer inspector |
| Web GIS dashboard, cm depths | `flood_viewer.html` + Space heatmap |
| Flood-safe routing API | Space route overlay + `api/route_nowcast.py` |
