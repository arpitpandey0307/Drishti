"""Train baseline U-Net. Smoke mode: 8 windows, 1 epoch, CPU, no torch required for data path."""
import argparse
import json
import os

import numpy as np


def build_sample(windows, i, norm):
    s = windows.get(i, norm)
    xin = np.concatenate(
        [s["static"], s["dynamic_hist"].reshape(-1, *s["static"].shape[1:]), s["future_rain"]],
        axis=0,
    )
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
            xs.append(x)
            ys.append(y)
        xs, ys = np.stack(xs), np.stack(ys)
        print("smoke batch", xs.shape, ys.shape, "mean_depth", float(ys.mean()))
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        np.savez(a.out + ".npz", x=xs[:2], y=ys[:2])
        print("smoke OK ->", a.out + ".npz")
        return

    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    from models.baseline_unet import BaselineUNet

    N = min(len(tr), 2692)
    X = np.stack([build_sample(tr, i, norm)[0] for i in range(N)])
    Y = np.stack([build_sample(tr, i, norm)[1] for i in range(N)])
    dl = DataLoader(
        TensorDataset(torch.from_numpy(X), torch.from_numpy(Y)),
        batch_size=a.batch,
        shuffle=True,
    )
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
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(xb)
        print(f"epoch {ep+1}/{a.epochs} loss={tot/len(dl.dataset):.4f}", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    torch.save({"model": m.state_dict(), "in_ch": X.shape[1]}, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
