# SIH Inference Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End-to-end working SIH demo: HF/local model → predicted flood grids → viewer bundles → safe-route CLI → runbook.

**Architecture:** `models/infer.py` loads weights (local `outputs/models/*.pt` first, HF Hub fallback via `hf_hub_download`) and predicts depth for any dataset window; `export_nowcast.py` reuses the viewer frame format with predicted depths at the 9 leads; `api/route_nowcast.py` routes on predicted grids. No viewer JS changes (dynamic index.json).

**Tech Stack:** Python 3.12, torch 2.14 CPU, numpy, h5py, huggingface_hub 1.30.

## Global Constraints

- All drainage SYNTHETIC `verified=false` — every demo output keeps the honesty banner/note.
- Normalization MUST come from `outputs/datasets/v1/normalization_train.json` (train-only).
- Viewer bundle format unchanged (int16/base64); nowcast bundles use dirs `nowcast_<sid>` and meta flag `"kind": "model-prediction"`.
- Grid 110x160 @5m; leads [1,2,4,6,8,12,18,24,36] steps × 5 min.

---

### Task 1: Inference module

**Files:**
- Create: `models/infer.py`
- Test: `tests/test_infer.py`

**Interfaces:**
- Consumes: `models/baseline_unet.BaselineUNet`, `dataset/ml_dataset.FloodWindows.get(i, norm)`, weights dict `{"model": state_dict, "in_ch": 36}` from local path or HF repo `Aman34243/drishti-flood-nowcaster`.
- Produces: `load_model(weights=None) -> BaselineUNet`; `predict_window(h5_path, sid, t0, model, norm) -> (9,110,160)` float32 metres, denormalized? No — depth trained unnormalized (targets raw metres), return raw metres.

- [ ] **Step 1: Write the failing test**

```python
def test_predict_window_shape():
    from models.infer import predict_window, load_model
    m = load_model("outputs/models/baseline_full100.pt")
    import json
    norm = json.load(open("outputs/datasets/v1/normalization_train.json"))
    y = predict_window("outputs/datasets/v1/kiet_flood_val.h5", "val_v1_00100", 10, m, norm)
    assert y.shape == (9, 110, 160)
    assert np.isfinite(y).all() and (y >= -0.05).all() and y.max() < 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_infer.py -v`
Expected: FAIL "No module named 'models.infer'".

- [ ] **Step 3: Write minimal implementation**

```python
"""Inference: local/HF weights -> predicted flood depths for any dataset window."""
import json, os
import numpy as np

LEADS = [1, 2, 4, 6, 8, 12, 18, 24, 36]
HF_REPO = "Aman34243/drishti-flood-nowcaster"

def load_model(weights=None):
    import torch
    from models.baseline_unet import BaselineUNet
    if weights is None:
        for p in ("outputs/models/baseline_full100.pt", "/tmp/baseline_full100.pt"):
            if os.path.exists(p):
                weights = p
                break
    if weights is None or (isinstance(weights, str) and "/" not in weights and not os.path.exists(weights)):
        from huggingface_hub import hf_hub_download
        weights = hf_hub_download(HF_REPO, "pytorch_model.bin")
    import torch as _t
    ckpt = _t.load(weights, map_location="cpu", weights_only=True)
    sd = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    m = BaselineUNet(in_ch=int(ckpt.get("in_ch", 36)) if isinstance(ckpt, dict) else 36)
    m.load_state_dict(sd)
    return m.eval()

def predict_window(h5_path, sid, t0, model, norm):
    import torch
    from dataset.ml_dataset import FloodWindows
    w = FloodWindows(h5_path)
    idx = next(i for i, (s, t, _) in enumerate(w._index) if s == sid and int(t) == t0)
    s = w.get(idx, norm)
    x = np.concatenate([s["static"], s["dynamic_hist"].reshape(-1, *s["static"].shape[1:]), s["future_rain"]], 0)
    with torch.no_grad():
        return model(torch.from_numpy(x[None]).float()).numpy()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_infer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add models/infer.py tests/test_infer.py
git commit -m "feat: model inference from local/HF weights"
```

### Task 2: Nowcast viz export

**Files:**
- Create: `visualization/data_adapter/export_nowcast.py`

**Interfaces:**
- Consumes: `models/infer.predict_window` + v1 H5 + `kiet_networks_v1.json` (topology/rain only; depth replaced by prediction).
- Produces: `outputs/viz/nowcast_<sid>/meta.json + frame_*.json` (9 frames at lead minutes) + index merge; `python3 -m visualization.data_adapter.export_nowcast --sid test_v1_00224 --t0 10`.

- [ ] **Step 1: Write script reusing export_viz writers** (import `_b64, _q16, _qi, FLOOD_THRESH_M` from export_viz; build meta from H5 spec + `"kind": "model-prediction"` + `"weights": "Aman34243/drishti-flood-nowcaster"`; frames from predicted depths, rain from H5 future rain, node/pipe from H5 at lead steps).
- [ ] **Step 2: Run export for 1 demo scenario**

Run: `python3 -m visualization.data_adapter.export_nowcast --sid test_v1_00224 --t0 10`
Expected: `exported nowcast_test_v1_00224: 9 frames`.

- [ ] **Step 3: Validate viewer loads it**

Run: `python3 -c "import json; print([e['id'] for e in json.load(open('outputs/viz/index.json')) if 'nowcast' in e['id']])"`
Expected: `['nowcast_test_v1_00224']`.

- [ ] **Step 4: Commit**

```bash
git add visualization/data_adapter/export_nowcast.py
git commit -m "feat: export model nowcasts to viewer bundles"
```

### Task 3: Route-from-nowcast CLI + landing + runbook

**Files:**
- Create: `api/route_nowcast.py`, `SIH_DEMO.md`
- Modify: `index.html` (nowcast card note)

**Interfaces:**
- Consumes: `models/infer.predict_window`, `api.route.safe_route`.
- Produces: `python3 -m api.route_nowcast --sid ... --t0 ... --lead-min 30 --from R,C --to R,C` prints JSON `{blocked, length_m, flooded_cells}` + writes GeoJSON.

- [ ] **Step 1: Write CLI** (predict → take lead slice → safe_route → lon/lat GeoJSON via X/Y metres + centre).
- [ ] **Step 2: Demo run on real prediction**

Run: `python3 -m api.route_nowcast --sid test_v1_00224 --t0 10 --lead-min 30 --from 20,20 --to 90,140`
Expected: JSON with `blocked: false/true`, `length_m`, `path_len`.

- [ ] **Step 3: Write SIH_DEMO.md** (5-command runbook: serve → viewer → nowcast → route → HF link).
- [ ] **Step 4: Commit**

```bash
git add api/route_nowcast.py SIH_DEMO.md index.html
git commit -m "feat: nowcast routing CLI + SIH demo runbook"
```
