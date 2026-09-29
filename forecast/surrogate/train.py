"""Train the flood surrogate on the v2 physics dataset, evaluate, export to ONNX.

    python -m forecast.surrogate.train --epochs 12

Streaming: scenarios are held once as compact float16 arrays and every training window
(t0, history, future rain, targets) is assembled on the fly in `__getitem__` — the old
`models/train_full.py` materialised every window up front and ran out of memory.

Reports per-lead RMSE and CSI (0.05 m / 0.10 m) on held-out test and OOD scenarios, against
the persistence baseline (depth stays as it is now), into forecast/models/surrogate_v2.json.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import time

import numpy as np
import torch
import torch.nn as nn

from models.baseline_unet import BaselineUNet

from .features import HIST, IDX_DEPTH_NOW, IDX_WET, LEAD_MIN, LEADS, N_CH, N_FUT, SCALE, CROP, STATIC, \
    build_inputs, static_stack

DATA = os.path.join("outputs", "datasets", "v2")
OUT_DIR = os.path.join("forecast", "models")


class Surrogate(nn.Module):
    """depth(t0 + lead) = relu(depth(t0) + 0.1 * U-Net(x)), masked to wet cells."""

    def __init__(self, base=24):
        super().__init__()
        self.unet = BaselineUNet(in_ch=N_CH, n_leads=len(LEADS), base=base)

    def forward(self, x):
        d0 = x[:, IDX_DEPTH_NOW:IDX_DEPTH_NOW + 1] * SCALE["depth_m"]
        wet = x[:, IDX_WET[0]:IDX_WET[0] + 1] * (1.0 - x[:, IDX_WET[1]:IDX_WET[1] + 1])
        return torch.relu(d0 + 0.1 * self.unet(x)) * wet


class WindowSet(torch.utils.data.Dataset):
    def __init__(self, files, static, stride=1):
        self.static = static
        self.S = []
        for f in files:
            z = np.load(f)
            self.S.append((z["rain"], z["depth"], float(z["blockage"])))
        T = self.S[0][0].shape[0] if self.S else 0
        self.idx = [(s, k0) for s in range(len(self.S)) for k0 in range(HIST - 1, T - N_FUT, stride)]

    def __len__(self):
        return len(self.idx)

    def __getitem__(self, n):
        s, k0 = self.idx[n]
        rain, depth, blk = self.S[s]
        x = build_inputs(self.static, rain[k0 - HIST + 1:k0 + 1].astype(np.float32),
                         depth[k0 - HIST + 1:k0 + 1].astype(np.float32),
                         rain[k0 + 1:k0 + 1 + N_FUT].astype(np.float32), blk)[0]
        y = depth[[k0 + l for l in LEADS]].astype(np.float32)
        return torch.from_numpy(x), torch.from_numpy(y)


def _loss(pred, y, wet):
    w = wet * (1.0 + 4.0 * (y > 0.05).float())
    return (w * ((pred - y) / 0.1) ** 2).sum() / w.sum().clamp_min(1.0)


@torch.no_grad()
def evaluate(model, ds, wet_np, batch=32):
    """Per-lead RMSE (m) over wet cells and CSI at 0.05 / 0.10 m, model vs persistence."""
    model.eval()
    L = len(LEADS)
    acc = {k: np.zeros(L) for k in ("se", "se_p", "n")}
    ct = {thr: {m: np.zeros((L, 3)) for m in ("model", "persist")} for thr in (0.05, 0.10)}
    wet = torch.from_numpy(wet_np.astype(np.float32))
    loader = torch.utils.data.DataLoader(ds, batch_size=batch, shuffle=False)
    for x, y in loader:
        p = model(x)
        d0 = (x[:, IDX_DEPTH_NOW] * SCALE["depth_m"]).unsqueeze(1).expand_as(y) * wet
        for name, q in (("model", p), ("persist", d0)):
            if name == "model":
                acc["se"] += (((q - y) ** 2) * wet).sum((0, 2, 3)).numpy()
            else:
                acc["se_p"] += (((q - y) ** 2) * wet).sum((0, 2, 3)).numpy()
            for thr in ct:
                pf, of = (q >= thr) & (wet > 0), (y >= thr) & (wet > 0)
                ct[thr][name] += np.stack([(pf & of).sum((0, 2, 3)).numpy(), (pf & ~of).sum((0, 2, 3)).numpy(),
                                           (~pf & of).sum((0, 2, 3)).numpy()], 1)
        acc["n"] += float(wet.sum()) * x.shape[0]
    csi = lambda c: (c[:, 0] / np.maximum(c.sum(1), 1)).round(3).tolist()
    return {"lead_min": LEAD_MIN,
            "rmse_m": np.sqrt(acc["se"] / acc["n"]).round(4).tolist(),
            "rmse_persistence_m": np.sqrt(acc["se_p"] / acc["n"]).round(4).tolist(),
            **{f"csi_{int(thr * 100)}cm": csi(ct[thr]["model"]) for thr in ct},
            **{f"csi_{int(thr * 100)}cm_persistence": csi(ct[thr]["persist"]) for thr in ct},
            "windows": len(ds)}


def export_onnx(model, path):
    model.eval()
    h, w = CROP[0].stop - CROP[0].start, CROP[1].stop - CROP[1].start
    dummy = torch.zeros(2, N_CH, h, w)
    kw = dict(input_names=["input"], output_names=["depth"],
              dynamic_axes={"input": {0: "batch"}, "depth": {0: "batch"}}, opset_version=17)
    try:
        torch.onnx.export(model, dummy, path, dynamo=False, **kw)
    except TypeError:
        torch.onnx.export(model, dummy, path, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--base", type=int, default=24)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--max-train", type=int, default=0, help="debug: cap training scenarios")
    ap.add_argument("--out", default=OUT_DIR)
    a = ap.parse_args()
    torch.manual_seed(0); np.random.seed(0)
    torch.set_num_threads(a.threads)

    from simulation import config as C
    from simulation.terrain.twin import Twin
    twin = Twin(C.load("terrain"))
    static = static_stack(twin)
    wet_np = (twin.in_domain & ~twin.is_building)[CROP]
    files = {s: sorted(glob.glob(os.path.join(a.data, s, "*.npz"))) for s in ("train", "val", "test", "ood")}
    if a.max_train:
        files["train"] = files["train"][:a.max_train]
    ds = {s: WindowSet(f, static) for s, f in files.items()}
    print({s: (len(files[s]), len(d)) for s, d in ds.items()}, flush=True)

    model = Surrogate(base=a.base)
    n_par = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * ((len(ds["train"]) + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(steps, 1))
    wet_t = torch.from_numpy(wet_np.astype(np.float32))
    loader = torch.utils.data.DataLoader(ds["train"], batch_size=a.batch, shuffle=True, drop_last=True)
    best, best_state, log = np.inf, None, []
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        tot, nb = 0.0, 0
        for x, y in loader:
            loss = _loss(model(x), y, wet_t)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            tot += float(loss); nb += 1
        val = evaluate(model, ds["val"], wet_np)
        vscore = float(np.mean(val["rmse_m"]))
        log.append({"epoch": ep + 1, "train_loss": round(tot / max(nb, 1), 4), "val_rmse_mean_m": round(vscore, 4),
                    "elapsed_s": round(time.time() - t0)})
        print(log[-1], flush=True)
        if vscore < best:
            best, best_state = vscore, {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    os.makedirs(a.out, exist_ok=True)
    onnx_path = os.path.join(a.out, "surrogate_v2.onnx")
    export_onnx(model, onnx_path)
    man = os.path.join(a.data, "manifest.json")
    meta = {
        "model": "surrogate_v2", "arch": f"residual U-Net (base {a.base})", "params": n_par,
        "inputs": {"channels": N_CH, "static": STATIC, "hist_steps": HIST, "leads_steps": LEADS,
                   "lead_min": LEAD_MIN, "future_rain": "cumulative mm to each lead", "scales": SCALE,
                   "crop": [[CROP[0].start, CROP[0].stop], [CROP[1].start, CROP[1].stop]]},
        "output": "surface depth (m) at each lead",
        "training": {"epochs": a.epochs, "batch": a.batch, "lr": a.lr, "log": log,
                     "train_windows": len(ds["train"]), "wall_s": round(time.time() - t0)},
        "dataset": {"path": a.data, "manifest_sha1": hashlib.sha1(open(man, "rb").read()).hexdigest()
                    if os.path.exists(man) else None, "provenance": "synthetic (Task-1 physics)"},
        "metrics": {"test": evaluate(model, ds["test"], wet_np), "ood": evaluate(model, ds["ood"], wet_np)},
        "torch": torch.__version__,
        "limits": "Emulates network variant 0 with nominal pumps and free outfalls; other drainage "
                  "states are handled by the adaptive physics refinement (Module M local level).",
    }
    json.dump(meta, open(os.path.join(a.out, "surrogate_v2.json"), "w"), indent=1)
    for s in ("test", "ood"):
        m = meta["metrics"][s]
        print(s, "RMSE", m["rmse_m"], "\n   persist", m["rmse_persistence_m"],
              "\n   CSI10", m["csi_10cm"], "\n   persist", m["csi_10cm_persistence"])
    print("saved", onnx_path, os.path.getsize(onnx_path) // 1024, "KB")


if __name__ == "__main__":
    main()
