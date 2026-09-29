# 09 — How to Run / Reproduce / Demo

## 1. Setup (FACT README.md:26-29 + knowledge.md:98-121 + environment.md)

- Dir `/home/devdevil/development/drishti`, linux, Python 3.12.3 pip 24.0.
- `pip install --break-system-packages h5py pyyaml matplotlib scipy` (+ `torch` for training; `onnxruntime numpy` for CLI; `hf_hub_download` for fetch).
- No GDAL/rasterio (PIL+numpy only); no torch on base env (Colab for training).

## 2. Physics + tests

```
python3 -m dataset.generator.run --split test        # v0 10 scn (legacy)
python3 -m pytest tests/test_simulator.py -q        # 8 physics/graph (~2 min)
python3 -m pytest tests/test_route.py tests/test_route_nowcast.py -q  # routing (needs /tmp/space fixtures for nowcast)
python3 dataset/generator/run_v2.py --smoke --workers 2   # v1 smoke
python3 -m dataset.generator.run_v2 --prod-n 240 --ood-n 36 --seed 26085 --workers 2  # full v1 (Colab CPU)
python3 -m dataset.stats --manifest outputs/datasets/v1/dataset_manifest.csv
python3 -m dataset.verify_transfer --dir outputs/datasets/v1   # must PASS + SHA256SUMS
```

## 3. Viewer (physics)

```
python3 -m visualization.data_adapter.export_viz --split test            # → outputs/viz/
python3 -m visualization.data_adapter.export_viz --split v1demo --max 2 # → +2 v1
python3 -m visualization.data_adapter.validate_viz   # must print ALL CHECKS PASSED
python3 -m http.server 8123   # then /flood_viewer.html (NOT file://) ; prod ?bank=demo
```

6 toggles, scrub/play, click cells/nodes/pipes, surcharge alarms, legend 0–50+ cm, CSV export (⤓t timeline / ⤓s series).

## 4. Model (train → export → Space)

```
python3 -m models.train_baseline --smoke                     # 8 windows npz
python3 -m models.train_baseline --train-h5 outputs/datasets/v1/kiet_flood_train.h5 --val-h5 .../val.h5 --epochs 5 --batch 4 --out outputs/models/baseline.pt
# full100: see models/train_full.py (100 scn bulk; 227 OOM — needs streaming DataLoader)
# export: dynamo → drishti.onnx single-file (maxdiff 3e-07) → upload Aman34243/drishti-flood-nowcaster
hf upload Aman34243/drishti-flood-nowcaster /tmp/hf_model
hf upload Aman34243/drishti-flood-nowcast /tmp/space --type space
```

## 5. Demos (SIH_DEMO.md:1-61)

1. Live model (no install): `https://aman34243-drishti-flood-nowcast.static.hf.space/` → window+lead → Predict+route; deep-link `?window=0&lead=30`.
2. Planner: `/flood_planner.html` (or Vercel) → storm+H slider → tap depth/peak/onset/risk → origin/destination normal vs flood-aware; `?storm=1&h=9&selftest=1`.
3. Physics viewer localhost: `:8123/flood_viewer.html` (10+2 scn) + landing `/index.html`.
4. CLI route on live HF: `python3 -m api.route_nowcast --window 0 --lead-min 30 --from 20,20 --to 90,140` → `{scenario,max_depth_m,flooded_m2,route_blocked,route_length_m}` (caches /tmp/space_cache).
5. Fresh-clone blobs: `python3 tools/fetch_demo_data.py` ← `Aman34243/drishti-demo-data`.

## 6. Maps + deploy

`python3 -m http.server 8000 → /kiet_road_map.html` (README_ROADMAP); `:8123/kiet_terrain_map.html`, `/kiet_3d_standalone.html` (double-click OK, CDN once), `/index.html`. Rebuild: `scripts/build_road_data.py`, `build_accurate_geojson.py`, `build_standalone_3d.py`. Guards: `check_*.py` + `validate_geojson.py`. Deploys auto on main: Vercel `drishti-sand` + Render `drishti-cl8r` (200s).
