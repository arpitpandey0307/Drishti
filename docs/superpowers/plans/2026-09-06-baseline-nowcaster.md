# Baseline Flood Nowcaster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train a CPU/GPU U-Net that maps 30-min history + statics to flood depth at 9 leads (5-180 min) and report per-lead metrics.

**Architecture:** Numpy `FloodWindows` loader feeds a PyTorch small U-Net (9 static + 3*6 dyn + 9 future rain = 36 ch → 9 depth maps). Joint MSE depth + BCE mask loss, train-only norm, scenario-level splits preserved.

**Tech Stack:** Python 3.12, PyTorch 2.11+cu128 (Colab T4), numpy, h5py, pyyaml. No new infra deps locally (numpy-only smoke).

## Global Constraints

- Scenario-level splits only — never mix frames across train/val/test files in `outputs/datasets/v1/`.
- Normalization MUST come from `outputs/datasets/v1/normalization_train.json` (train-only).
- Grid is fixed 110x160 (Y,X) — model must accept (B,C,110,160).
- All drainage is SYNTHETIC `verified=false` — never label outputs as observed flooding.
- `outputs/` is gitignored — checkpoints go to `outputs/models/` (local-only, document in report.md).

---

### Task 1: Baseline U-Net model file

**Files:**
- Create: `models/baseline_unet.py`
- Test: `tests/test_baseline_unet.py`

**Interfaces:**
- Consumes: nothing (standalone torch nn.Module).
- Produces: `BaselineUNet(in_ch=30, n_leads=9)` with `forward(x)->(B,9,110,160)` depth in meters; `count_params()->int`.

- [ ] **Step 1: Write the failing test**

```python
def test_unet_forward_shape():
    import torch
    from models.baseline_unet import BaselineUNet
    m = BaselineUNet(in_ch=30, n_leads=9)
    x = torch.zeros(2, 30, 110, 160)
    y = m(x)
    assert y.shape == (2, 9, 110, 160)
    assert int(m.count_params()) > 100_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_baseline_unet.py::test_unet_forward_shape -v`
Expected: FAIL with "No module named 'models.baseline_unet'" (or collection error).

- [ ] **Step 3: Write minimal implementation**

```python
"""Baseline U-Net for flood nowcasting: (B,30,110,160) -> (B,9,110,160)."""
import torch
import torch.nn as nn

def _blk(ci, co):
    return nn.Sequential(nn.Conv2d(ci, co, 3, padding=1), nn.ReLU(inplace=True),
                         nn.Conv2d(co, co, 3, padding=1), nn.ReLU(inplace=True))

class BaselineUNet(nn.Module):
    def __init__(self, in_ch=30, n_leads=9, base=32):
        super().__init__()
        self.e1 = _blk(in_ch, base)
        self.e2 = _blk(base, base*2)
        self.e3 = _blk(base*2, base*4)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(base*4, base*2, 2, stride=2)
        self.d2 = _blk(base*4, base*2)
        self.up1 = nn.ConvTranspose2d(base*2, base, 2, stride=2)
        self.d1 = _blk(base*2, base)
        self.out = nn.Conv2d(base, n_leads, 1)
    def forward(self, x):
        f1 = self.e1(x)
        f2 = self.e2(self.pool(f1))
        f3 = self.e3(self.pool(f2))
        u = self.up2(f3)
        # pad for odd 110/160 halving mismatch
        dh, dw = f2.shape[2]-u.shape[2], f2.shape[3]-u.shape[3]
        import torch.nn.functional as F
        u = F.pad(u, (0, dw, 0, dh))
        u = self.d2(torch.cat([u, f2], 1))
        v = self.up1(u)
        dh, dw = f1.shape[2]-v.shape[2], f1.shape[3]-v.shape[3]
        v = F.pad(v, (0, dw, 0, dh))
        v = self.d1(torch.cat([v, f1], 1))
        return self.out(v)
    def count_params(self):
        return sum(p.numel() for p in self.parameters())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install torch --quiet 2>/dev/null || true; python3 -m pytest tests/test_baseline_unet.py -v`
Expected: PASS (on Colab T4 torch present; locally test is skipped if torch missing via importorskip).

- [ ] **Step 5: Commit**

```bash
git add models/baseline_unet.py tests/test_baseline_unet.py
git commit -m "feat: add baseline U-Net nowcaster"
```

### Task 2: Training script (numpy loader + torch loop)

**Files:**
- Create: `models/train_baseline.py`
- Modify: none (reads `dataset/ml_dataset.py:FloodWindows`, `outputs/datasets/v1/normalization_train.json`)

**Interfaces:**
- Consumes: `FloodWindows(h5_path).get(i, norm)` dict with `static (9,110,160)`, `dynamic_hist (3,6,110,160)`, `future_rain (9,110,160)`, `target_depth (9,110,160)`.
- Produces: CLI `python3 -m models.train_baseline --train-h5 ... --val-h5 ... --epochs N --out outputs/models/baseline.pt` + `metrics.json` with per-lead RMSE/CSI.

- [ ] **Step 1: Write the failing smoke invocation**

```bash
python3 -m models.train_baseline --smoke --epochs 1 --out /tmp/smoke.pt
# expected before impl: "No module named models.train_baseline"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m models.train_baseline --smoke --epochs 1 --out /tmp/smoke.pt`
Expected: FAIL module-not-found.

- [ ] **Step 3: Write minimal implementation**

```python
"""Train baseline U-Net. Smoke mode: 8 windows, 1 epoch, CPU, no torch required for data path."""
import argparse, json, os, numpy as np
def build_sample(windows, i, norm):
    s = windows.get(i, norm)
    xin = np.concatenate([s["static"], s["dynamic_hist"].reshape(-1, *s["static"].shape[1:]), s["future_rain"]], axis=0)
    return xin.astype(np.float32), s["target_depth"].astype(np.float32)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-h5", default="outputs/datasets/v1/kiet_flood_train.h5")
    ap.add_argument("--val-h5", default="outputs/datasets/v1/kiet_flood_val.h5")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="outputs/models/baseline.pt")
    a = ap.parse_args()
    from dataset.ml_dataset import FloodWindows
    norm = json.load(open("outputs/datasets/v1/normalization_train.json"))
    tr, va = FloodWindows(a.train_h5), FloodWindows(a.val_h5)
    print(f"windows train={len(tr)} val={len(va)}")
    if a.smoke:
        xs, ys = [], []
        for i in range(min(8, len(tr))):
            x, y = build_sample(tr, i, norm)
            xs.append(x); ys.append(y)
        xs, ys = np.stack(xs), np.stack(ys)
        print("smoke batch", xs.shape, ys.shape, "mean_depth", float(ys.mean()))
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        np.savez(a.out + ".npz", x=xs[:2], y=ys[:2])
        print("smoke OK ->", a.out + ".npz")
        return
    import torch, torch.nn as nn
    from models.baseline_unet import BaselineUNet
    from torch.utils.data import TensorDataset, DataLoader
    N = min(len(tr), 2692)
    X = np.stack([build_sample(tr, i, norm)[0] for i in range(N)])
    Y = np.stack([build_sample(tr, i, norm)[1] for i in range(N)])
    dl = DataLoader(TensorDataset(torch.from_numpy(X), torch.from_numpy(Y)), batch_size=a.batch, shuffle=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = BaselineUNet(in_ch=X.shape[1], n_leads=9).to(dev)
    opt = torch.optim.Adam(m.parameters(), 1e-3)
    mse, bce = nn.MSELoss(), nn.BCEWithLogitsLoss()
    for ep in range(a.epochs):
        tot = 0.0
        for xb, yb in dl:
            xb, yb = xb.to(dev), yb.to(dev)
            pred = m(xb)
            mask = (yb >= 0.05).float()
            loss = mse(pred, yb) + 0.2 * bce(pred, mask)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss) * len(xb)
        print(f"epoch {ep+1}/{a.epochs} loss={tot/len(dl.dataset):.4f}", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    torch.save({"model": m.state_dict(), "in_ch": X.shape[1]}, a.out)
    print("saved", a.out)
if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run smoke to verify it passes**

Run: `python3 -m models.train_baseline --smoke --epochs 1 --out /tmp/smoke.pt`
Expected: PASS prints `windows train=2692 val=...` then `smoke OK`.

- [ ] **Step 5: Commit**

```bash
git add models/train_baseline.py
git commit -m "feat: add baseline training loop"
```

### Task 3: Colab T4 full run + metrics

**Files:**
- Create: `outputs/models/` (gitignored artefacts: `baseline.pt`, `metrics.json`)
- Modify: `report.md` (append §17 baseline results)

**Interfaces:**
- Consumes: `models/train_baseline.py` + `outputs/datasets/v1/*.h5` (train file must reach Colab; files >50MB cannot use `colab upload` — chunk or regenerate subset on VM).
- Produces: per-lead RMSE/CSI printed + saved model.

- [ ] **Step 1: Provision T4 and verify torch**

Run: `colab new -s flood-train --gpu T4`
Expected: READY T4.

- [ ] **Step 2: Ship code, stage data subset on VM**

Run: `echo "import torch; print(torch.cuda.get_device_name(0))" | colab exec -s flood-train`
Expected: `Tesla T4`.

- [ ] **Step 3: Train 5 epochs, capture loss**

Run: `cat models/train_baseline.py | colab exec -s flood-train` (or exec via -f script)
Expected: epoch losses decreasing, `saved ...baseline.pt`.

- [ ] **Step 4: Stop session and log results**

Run: `colab stop -s flood-train`
Expected: `Session terminated`, results appended to report.md §17.
