"""Dataset balance + distribution analysis (v1.0).

Reads dataset_manifest.csv + HDF5 files, prints balance tables and writes
histograms to outputs/figures/. Flags imbalance for targeted top-ups
(see simulation/scenarios/suite_v2.py quotas).
"""
from __future__ import annotations
import os, csv, json
import numpy as np

OUT_FIG = "outputs/figures"


def load_manifest(path="outputs/datasets/dataset_manifest.csv"):
    with open(path) as fh:
        return list(csv.DictReader(fh))


def severity(maxd):
    if maxd < 0.05:
        return "no-flood"
    if maxd < 0.15:
        return "minor"
    if maxd < 0.40:
        return "moderate"
    return "severe"


def analyze(rows, make_plots=True):
    from collections import Counter
    valid = [r for r in rows if r["status"] == "valid"]
    print(f"scenarios: {len(rows)} total, {len(valid)} valid, "
          f"{sum(1 for r in rows if r['status']=='quarantined')} quarantined, "
          f"{sum(1 for r in rows if r['status']=='failed')} failed")
    for key in ["split", "rain_class", "blockage_level", "blockage_mode",
                "temporal", "spatial", "network_variant", "edge_case"]:
        c = Counter((r[key] or "-") for r in valid)
        print(f"\n[{key}]")
        for k in sorted(c):
            print(f"  {k}: {c[k]} ({c[k]/max(len(valid),1)*100:.1f}%)")
    sev = Counter(severity(float(r["max_depth_m"] or 0)) for r in valid)
    print("\n[severity (max depth)]")
    for k in ["no-flood", "minor", "moderate", "severe"]:
        print(f"  {k}: {sev.get(k,0)} ({sev.get(k,0)/max(len(valid),1)*100:.1f}%)")
    print("\n[sim time]")
    t = np.array([float(r["sim_time_s"] or 0) for r in valid])
    if len(t):
        print(f"  mean={t.mean():.1f}s median={np.median(t):.1f}s total={t.sum()/3600:.2f}h")
    merr = np.array([float(r["mass_err"] or 0) for r in valid])
    if len(merr):
        print(f"[mass_err] max={merr.max():.2e} mean={merr.mean():.2e}")
    if make_plots:
        os.makedirs(OUT_FIG, exist_ok=True)
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib missing, skipping plots")
            return
        fig, ax = plt.subplots(2, 3, figsize=(15, 9))
        ax = ax.ravel()
        tot = np.array([float(r["total_mm"] or 0) for r in valid])
        ax[0].hist(tot, bins=25); ax[0].set_title("total rainfall (mm)")
        mx = np.array([float(r["max_depth_m"] or 0) for r in valid])
        ax[1].hist(mx, bins=25); ax[1].set_title("max depth (m)")
        ff = np.array([float(r["flood_frac"] or 0) for r in valid]) * 100
        ax[2].hist(ff, bins=25); ax[2].set_title("flooded cell-time frac (%)")
        du = np.array([float(r["duration_h"] or 0) for r in valid])
        ax[3].hist(du, bins=20); ax[3].set_title("duration (h)")
        bl = np.array([float(r["blockage_level"] or 0) for r in valid])
        ax[4].hist(bl, bins=6); ax[4].set_title("blockage level")
        ax[5].hist(t, bins=20); ax[5].set_title("sim time (s)")
        fig.suptitle("KIET flood dataset v1.0 -- distributions (SYNTHETIC data)")
        fig.tight_layout()
        fig.savefig(f"{OUT_FIG}/dataset_v1_distributions.png", dpi=90)
        print(f"wrote {OUT_FIG}/dataset_v1_distributions.png")
    # imbalance flags
    nf = sev.get("no-flood", 0) / max(len(valid), 1)
    if nf < 0.05:
        print("FLAG: no-flood <5% -- add trace-class top-up")
    if sev.get("severe", 0) / max(len(valid), 1) < 0.10:
        print("FLAG: severe <10% -- add extreme-class top-up")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="outputs/datasets/dataset_manifest.csv")
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args()
    analyze(load_manifest(a.manifest), make_plots=not a.no_plots)
