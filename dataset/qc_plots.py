"""Visual QC: representative-scenario PNGs (max-depth map + hydrograph).

Verifies the saved dataset matches the physics simulation by rendering
directly from the HDF5 archive. Run after generation; inspect PNGs in
outputs/figures/qc/.
"""
from __future__ import annotations
import os, json
import numpy as np
import h5py


def qc_scenario(h5_path, sid, out_dir="outputs/figures/qc"):
    os.makedirs(out_dir, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with h5py.File(h5_path, "r") as f:
        g = f[sid]
        depth = np.asarray(g["depth"])
        rain = np.asarray(g["rain"])
        maxd = np.asarray(g["max_depth"])
        dem = np.asarray(f["dem"])
        in_dom = np.asarray(f["in_domain"]).astype(bool)
        spec = json.loads(g.attrs["spec"])
        mass = json.loads(g.attrs["mass"])
        T = depth.shape[0]
    fig, ax = plt.subplots(1, 3, figsize=(16, 5))
    im = ax[0].imshow(np.where(in_dom, maxd, np.nan), vmin=0, vmax=0.5)
    ax[0].set_title("max depth (m)")
    plt.colorbar(im, ax=ax[0], shrink=0.8)
    ax[1].imshow(np.where(in_dom, dem, np.nan))
    ax[1].set_title("DEM (m)")
    wet = in_dom
    rain_ts = rain.reshape(T, -1)[:, wet.ravel()].mean(axis=1)
    pond_ts = depth.reshape(T, -1)[:, wet.ravel()].mean(axis=1) * 1000
    ax[2].plot(np.arange(T) * 5, rain_ts, label="rain mean (mm/5min)")
    ax[2].plot(np.arange(T) * 5, pond_ts, label="ponded mean (mm)")
    ax[2].set_xlabel("min"); ax[2].legend(); ax[2].set_title("hyetograph vs ponding")
    fig.suptitle(f"{sid} | {spec.get('total_mm')}mm {spec.get('duration_h')}h "
                 f"{spec.get('temporal')}/{spec.get('spatial')} "
                 f"blk={spec.get('blockage_level')}/{spec.get('blockage_mode')} "
                 f"net={spec.get('network_variant')} drain_eff={spec.get('drain_eff')} "
                 f"rec={spec.get('recession_h')}h maxd={maxd.max():.2f}m")
    fig.tight_layout()
    p = f"{out_dir}/{sid}.png"
    fig.savefig(p, dpi=80)
    plt.close(fig)
    print(f"wrote {p} (T={T}, rain={mass['rain_mm']:.1f}mm, ponded={mass['ponded_mm']:.1f}mm)")
    return p


def auto_pick(manifest_rows, h5_files, out_dir="outputs/figures/qc", per_class=2):
    """Pick representative scenarios: no-flood, minor, severe, blocked, moving, surcharge."""
    import csv
    picks = {"no-flood": [], "minor": [], "severe": [], "blocked": [],
             "moving": [], "recession": []}
    for r in manifest_rows:
        if r["status"] != "valid":
            continue
        md = float(r["max_depth_m"] or 0)
        cat = "severe" if md >= 0.4 else ("minor" if md >= 0.05 else "no-flood")
        if len(picks[cat]) < per_class:
            picks[cat].append(r)
        if float(r["blockage_level"] or 0) >= 0.5 and len(picks["blocked"]) < per_class:
            picks["blocked"].append(r)
        if r["spatial"] == "moving_cell" and len(picks["moving"]) < per_class:
            picks["moving"].append(r)
        if float(r.get("recession_h") or 0) > 0 and md >= 0.05 and len(picks["recession"]) < per_class:
            picks["recession"].append(r)
    done = set()
    for cat, rs in picks.items():
        for r in rs:
            if r["scenario_id"] in done:
                continue
            done.add(r["scenario_id"])
            qc_scenario(r["file_path"], r["scenario_id"], out_dir)


if __name__ == "__main__":
    import argparse, csv
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="outputs/datasets/dataset_manifest.csv")
    ap.add_argument("--h5", default=None, help="single file + --sid for one-off QC")
    ap.add_argument("--sid", default=None)
    a = ap.parse_args()
    if a.h5 and a.sid:
        qc_scenario(a.h5, a.sid)
    else:
        rows = list(csv.DictReader(open(a.manifest)))
        auto_pick(rows, None)
