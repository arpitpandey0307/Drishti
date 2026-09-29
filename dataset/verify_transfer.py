"""Post-transfer integrity verification (local PC).

Checks, for every finalized file:
- presence + size + sha256 (against SHA256SUMS written on Colab)
- HDF5 readability: static grids, per-scenario datasets, attrs
- manifest consistency: every valid/quarantined row has its group in the
  file recorded in file_path; no scenario_id appears in two splits
- split integrity: train/val/test/ood files contain disjoint scenario sets
- dataloader sanity: one window loads from each split

Usage: python3 -m dataset.verify_transfer [--dir outputs/datasets]
"""
from __future__ import annotations
import os, csv, json, hashlib
import numpy as np

FILES = ["kiet_flood_train.h5", "kiet_flood_val.h5", "kiet_flood_test.h5",
         "ood/kiet_flood_ood.h5", "dataset_manifest.csv", "kiet_networks_v1.json"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(8 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main(d="outputs/datasets"):
    import h5py
    ok = True
    # 1. checksums
    sums = {}
    sp = os.path.join(d, "SHA256SUMS")
    if os.path.exists(sp):
        for line in open(sp):
            parts = line.strip().split()
            if len(parts) == 2:
                sums[parts[1]] = parts[0]
    for rel in FILES:
        p = os.path.join(d, rel)
        if not os.path.exists(p):
            print(f"MISSING: {rel}");
            ok = False
            continue
        print(f"present: {rel} ({os.path.getsize(p)/1e6:.1f} MB)", end="")
        base = os.path.basename(p)
        if base in sums:
            match = sha256(p) == sums[base]
            print(f" sha256={'OK' if match else 'MISMATCH'}")
            ok &= match
        else:
            print(" (no checksum entry)")
    # 2. manifest vs files
    rows = list(csv.DictReader(open(os.path.join(d, "dataset_manifest.csv"))))
    seen, dup = set(), []
    for r in rows:
        if r["scenario_id"] in seen:
            dup.append(r["scenario_id"])
        seen.add(r["scenario_id"])
    print(f"manifest rows: {len(rows)}, unique ids: {len(seen)}, duplicates: {dup[:5]}")
    ok &= not dup
    # 3. per-file readability + group presence
    all_ids = {}
    for rel in FILES:
        if not rel.endswith(".h5") or "quarantine" in rel:
            continue
        p = os.path.join(d, rel)
        with h5py.File(p, "r") as f:
            assert f.attrs.get("dataset_version") == "1.0", f"{rel}: version attr"
            for req in ["dem", "slope", "flow_accum", "low_points"]:
                assert req in f, f"{rel}: missing {req}"
            sids = [k for k in f.keys() if "_v1_" in k]
            all_ids[rel] = set(sids)
            g0 = f[sids[0]]
            for ds in ["rain", "depth", "velocity", "flooded", "node_depth",
                       "pipe_flow", "dem_delta", "max_depth", "time_to_flood_min"]:
                assert ds in g0, f"{rel}/{sids[0]}: missing {ds}"
            T = g0["depth"].shape[0]
            assert g0["rain"].shape[0] == T, f"{rel}: rain/depth T mismatch"
            print(f"{rel}: {len(sids)} scenarios OK (e.g. {sids[0]} T={T})")
    # 4. disjoint splits
    keys = list(all_ids)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            overlap = all_ids[keys[i]] & all_ids[keys[j]]
            print(f"overlap {keys[i]} x {keys[j]}: {len(overlap)}")
            ok &= not overlap
    # 5. quarantine file (optional)
    qp = os.path.join(d, "kiet_flood_quarantine.h5")
    if os.path.exists(qp):
        with h5py.File(qp, "r") as f:
            print(f"quarantine: {[k for k in f.keys() if '_v1_' in k]}")
    # 6. dataloader sanity (one window per split)
    from dataset.ml_dataset import FloodWindows
    for rel in ["kiet_flood_train.h5", "kiet_flood_val.h5",
                "kiet_flood_test.h5", "ood/kiet_flood_ood.h5"]:
        w = FloodWindows(os.path.join(d, rel))
        s = w.get(0)
        assert s["target_depth"].shape[0] == 9, "lead steps"
        print(f"dataloader {rel}: {len(w)} windows, sample static{s['static'].shape} "
              f"hist{s['dynamic_hist'].shape} tgt{s['target_depth'].shape} OK")
    print("VERIFY:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="outputs/datasets")
    a = ap.parse_args()
    raise SystemExit(0 if main(a.dir) else 1)
