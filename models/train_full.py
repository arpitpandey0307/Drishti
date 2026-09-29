"""Full-scale baseline trainer: fast bulk preload + per-lead RMSE/CSI eval."""
import argparse
import json
import os
import time

import numpy as np

HIST = 6
LEADS = [1, 2, 4, 6, 8, 12, 18, 24, 36]
STATIC_KEYS = ["dem", "slope", "flow_accum_log", "low_points", "imperv",
               "manning", "is_road", "is_building", "in_domain"]


def load_split(h5_path, norm, max_windows=None):
    import h5py
    Xs, Ys = [], []
    with h5py.File(h5_path, "r") as f:
        fa = np.log1p(np.maximum(np.asarray(f["flow_accum"][:], dtype=np.float32), 0))
        statics = []
        for c in STATIC_KEYS:
            if c == "flow_accum_log":
                statics.append(fa)
            else:
                statics.append(np.asarray(f[c][:], dtype=np.float32))
        static = np.stack(statics)
        # norm statics
        for i, c in enumerate(
            ["dem", "slope", "flow_accum_log", "low_points", "imperv",
             "manning", "is_road", "is_building", "in_domain"]
        ):
            key = f"static.{c}" if c != "flow_accum_log" else "static.flow_accum_log"
            if key in norm:
                m, s = norm[key]["mean"], norm[key]["std"]
                static[i] = (static[i] - m) / (s if s > 0 else 1.0)
        sids = [k for k in f.keys() if k.startswith(("train", "val", "test", "ood"))]
        for sid in sids:
            g = f[sid]
            try:
                depth = np.asarray(g["depth"][:], dtype=np.float32)
                rain = np.asarray(g["rain"][:], dtype=np.float32)
                vel = np.asarray(g["velocity"][:], dtype=np.float32)
            except Exception:
                continue
            T = depth.shape[0]
            t_min, t_max = HIST - 1, T - max(LEADS) - 1
            if t_max < t_min:
                continue
            for t0 in range(t_min, t_max + 1):
                hist = np.concatenate(
                    [rain[t0 - HIST + 1:t0 + 1, None] if False else rain[t0 - HIST + 1:t0 + 1],
                     depth[t0 - HIST + 1:t0 + 1],
                     vel[t0 - HIST + 1:t0 + 1]], axis=0,
                ) if False else None
                # explicit: (3,H,Y,X)
                h = np.stack([
                    rain[t0 - HIST + 1:t0 + 1],
                    depth[t0 - HIST + 1:t0 + 1],
                    vel[t0 - HIST + 1:t0 + 1],
                ])  # (3,H,Y,X)
                h_flat = h.reshape(-1, *h.shape[2:])  # (18,Y,X)
                fut_rain = np.stack([rain[t0 + l] for l in LEADS])
                fut_depth = np.stack([depth[t0 + l] for l in LEADS])
                # norm dynamics
                for i, c in enumerate(["rain", "depth", "velocity"]):
                    key = f"dyn.{c}"
                    if key in norm:
                        m_, s_ = norm[key]["mean"], norm[key]["std"]
                        h[i] = (h[i] - m_) / (s_ if s_ > 0 else 1.0)
                if "dyn.rain" in norm:
                    m_, s_ = norm["dyn.rain"]["mean"], norm["dyn.rain"]["std"]
                    fut_rain = (fut_rain - m_) / (s_ if s_ > 0 else 1.0)
                    h_flat = np.concatenate([static,
                                             (h.reshape(-1, *h.shape[2:])),
                                             fut_rain], axis=0)
                else:
                    h_flat = np.concatenate([static, h.reshape(-1, *h.shape[2:]), fut_rain], axis=0)
                Xs.append(h_flat)
                Ys.append(fut_depth)
                if max_windows and len(Xs) >= max_windows:
                    return np.stack(Xs), np.stack(Ys)
    return np.stack(Xs), np.stack(Ys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-h5", default="outputs/datasets/v1/kiet_flood_train.h5")
    ap.add_argument("--val-h5", default="outputs/datasets/v1/kiet_flood_val.h5")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--out", default="/content/baseline_full.pt")
    a = ap.parse_args()
    norm = json.load(open("outputs/datasets/v1/normalization_train.json"
                          if os.path.exists("outputs/datasets/v1/normalization_train.json")
                          else "/tmp/stage/outputs/datasets/v1/normalization_train.json"))
    # resolve paths under /tmp/stage if needed
    for p in [a.train_h5, a.val_h5]:
        pass
    t0 = time.time()
    print("loading train...", flush=True)
    X, Y = load_split(a.train_h5, norm)
    print(f"train {X.shape} {Y.shape} load {time.time()-t0:.1f}s", flush=True)
    t1 = time.time()
    print("loading val...", flush=True)
    Xv, Yv = load_split(a.val_h5, norm)
    print(f"val {Xv.shape} {Yv.shape} load {time.time()-t1:.1f}s", flush=True)

    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    from models.baseline_unet import BaselineUNet

    dl = DataLoader(TensorDataset(torch.from_numpy(X), torch.from_numpy(Y)),
                    batch_size=a.batch, shuffle=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "", flush=True)
    m = BaselineUNet(in_ch=X.shape[1], n_leads=len(LEADS)).to(dev)
    opt = torch.optim.Adam(m.parameters(), 1e-3)
    mse, bce = nn.MSELoss(), nn.BCEWithLogitsLoss()
    for ep in range(a.epochs):
        m.train()
        tot = 0.0
        for xb, yb in dl:
            xb, yb = xb.to(dev), yb.to(dev)
            pred = m(xb)
            loss = mse(pred, yb) + 0.2 * bce(pred, (yb >= 0.05).float())
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(xb)
        # val per-lead RMSE
        m.eval()
        with torch.no_grad():
            pv = m(torch.from_numpy(Xv[:64]).to(dev)).cpu().numpy()
            rmse = np.sqrt(((pv - Yv[:64]) ** 2).mean(axis=(0, 2, 3)))
        print(f"epoch {ep+1}/{a.epochs} loss={tot/len(dl.dataset):.4f} "
              f"val_rmse30={rmse[5]:.4f} val_rmse180={rmse[8]:.4f}", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    torch.save({"model": m.state_dict(), "in_ch": X.shape[1]}, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
