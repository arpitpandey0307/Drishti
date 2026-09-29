"""Assemble final v1.0 split files from multiple partial HDF5s + manifests.

Used when generation spans several Colab VMs (preemptions): each VM produced
a subset of scenario groups. Because specs+seeds are deterministic, groups are
unique by scenario_id -- merge = dedupe by ID, first occurrence wins.

Usage:
  python3 -m dataset.merge_splits --manifest-in a.csv b.csv --h5-in a1.h5 a2.h5 ... \
      --out-dir outputs/datasets [--ood ood.h5 ...]

Writes kiet_flood_{train,val,test}.h5 + dataset_manifest.csv (+ merges OOD).
Verifies: every manifest-valid row has its group; no duplicate IDs.
"""
from __future__ import annotations
import os, csv, json
import numpy as np

STATIC_KEYS = ["dem", "manning", "imperv", "in_domain", "is_road", "is_building",
               "X", "Y", "slope", "flow_accum", "low_points"]


def main(manifests, h5s, out_dir, ood_h5s=()):
    import h5py
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "ood"), exist_ok=True)
    # --- merged manifest (dedupe by scenario_id, prefer valid over failed) ---
    rows = {}
    for m in manifests:
        for r in csv.DictReader(open(m)):
            sid = r["scenario_id"]
            if sid not in rows or rows[sid]["status"] == "failed":
                rows[sid] = r
    # --- collect groups ---
    have = {}  # sid -> (src_path, split)
    for h in list(h5s) + list(ood_h5s):
        with h5py.File(h, "r") as f:
            for sid in f.keys():
                if "_v1_" in sid and sid not in have:
                    split = "ood" if h in ood_h5s else sid.split("_v1_")[0]
                    have[sid] = (h, split)
    # --- write split files ---
    by_split = {}
    for sid, (h, split) in have.items():
        by_split.setdefault(split, []).append((sid, h))
    for split, items in sorted(by_split.items()):
        d = os.path.join(out_dir, "ood") if split == "ood" else out_dir
        out = os.path.join(d, f"kiet_flood_{split}.h5")
        with h5py.File(out, "w") as fo:
            first = True
            for sid, src in sorted(items):
                with h5py.File(src, "r") as fi:
                    if first:  # static grids + attrs from first source
                        for k in STATIC_KEYS:
                            if k in fi:
                                fo.create_dataset(k, data=fi[k][:], compression="gzip", shuffle=True)
                        for ak, av in fi.attrs.items():
                            fo.attrs[ak] = av
                        first = False
                    g = fo.create_group(sid)
                    for ds in fi[sid].keys():
                        fo[sid].create_dataset(ds, data=fi[sid][ds][:],
                                               compression="gzip", shuffle=True)
                    for ak, av in fi[sid].attrs.items():
                        g.attrs[ak] = av
        print(f"wrote {out}: {len(items)} scenarios")
    # --- merged manifest ---
    mcols = list(next(iter(rows.values())).keys())
    with open(os.path.join(out_dir, "dataset_manifest.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=mcols)
        w.writeheader()
        for sid in sorted(rows):
            r = dict(rows[sid])
            if r["status"] == "valid":
                split = sid.split("_v1_")[0]
                d = os.path.join(out_dir, "ood") if split == "ood" else out_dir
                r["file_path"] = os.path.join(d, f"kiet_flood_{split}.h5")
            w.writerow(r)
    # --- verify ---
    n_missing = [sid for sid, r in rows.items()
                 if r["status"] == "valid" and sid not in have]
    print(f"manifest valid rows: {sum(1 for r in rows.values() if r['status']=='valid')}, "
          f"groups assembled: {len(have)}, missing: {len(n_missing)}{n_missing[:5]}")
    return not n_missing


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-in", nargs="+", required=True)
    ap.add_argument("--h5-in", nargs="+", required=True)
    ap.add_argument("--ood-in", nargs="*", default=[])
    ap.add_argument("--out-dir", default="outputs/datasets")
    a = ap.parse_args()
    raise SystemExit(0 if main(a.manifest_in, a.h5_in, a.out_dir, a.ood_in) else 1)
