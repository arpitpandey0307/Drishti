"""Dataset v1.0 resumable parallel generator.

Produces scenario-level train/val/test splits + separate OOD file, a CSV
manifest (dataset_manifest.csv), quarantine file for rejected scenarios,
versioned HDF5 attrs and per-scenario static/dynamic separation.

Resume: re-running the same command skips every scenario_id already marked
valid/quarantined in the manifest. Deterministic IDs + seeds.

Examples:
  python3 -m dataset.generator.run_v2 --prod-n 240 --ood-n 36 --workers 3
  python3 -m dataset.generator.run_v2 --prod-n 240 --ood-n 36 --workers 3 --only ood
  python3 -m dataset.generator.run_v2 --smoke  # 4 quick scenarios -> outputs/datasets/smoke/
"""
from __future__ import annotations
import os, sys, json, csv, copy, time, datetime
import numpy as np

from simulation.scenarios.suite_v2 import (
    make_prod_suite, make_ood_suite, make_topup_suite, make_longdry_suite,
    assign_splits, DATASET_VERSION, SIMULATOR_VERSION, N_NETWORK_VARIANTS)

MANIFEST_COLUMNS = ["scenario_id", "seed", "split", "status", "rain_class", "edge_case",
    "temporal", "spatial", "total_mm", "duration_h", "recession_h", "network_variant",
    "drain_eff", "blockage_level", "blockage_mode", "terrain_seed", "manning_scale",
    "dep_scale", "imperv_open", "sim_time_s", "validation_status", "mass_err",
    "max_depth_m", "flood_frac", "file_path", "errors"]

# ---------------------------------------------------------------- worker side
_G = {}

def _init(cfg_paths):
    import yaml
    from simulation.terrain.twin import Twin
    from simulation.drainage.network import generate as gen_net
    ter_cfg = yaml.safe_load(open(cfg_paths["terrain"]))
    dra_cfg = yaml.safe_load(open(cfg_paths["drainage"]))
    rain_cfg = yaml.safe_load(open(cfg_paths["rainfall"]))
    hyd_cfg = yaml.safe_load(open(cfg_paths["hydraulics"]))
    twin = Twin(ter_cfg)
    nets = [gen_net(twin, dra_cfg, seed=cfg_paths["seed"], variant=v)
            for v in range(cfg_paths["nvar"])]
    _G.update(twin=twin, nets=nets, rain_cfg=rain_cfg, hyd_cfg=hyd_cfg)


def _build_overrides(twin, spec):
    r = np.random.default_rng(int(spec["terrain_seed"]))
    dem_delta = (r.normal(0.0, float(spec.get("terrain_jitter_m", 0.05)),
                          size=twin.dem.shape)).astype(np.float64)
    dem = twin.dem + dem_delta
    manning = twin.manning * float(spec.get("manning_scale", 1.0))
    return dem, manning, dem_delta.astype(np.float32)


def _lowpoint_center(twin):
    m = twin.low_points & twin.in_domain
    if not m.any():
        m = twin.in_domain
    return float(twin.X[m].mean()), float(twin.Y[m].mean())


def _run_one(spec):
    """Worker: simulate + validate one scenario. Returns small payload (arrays kept)."""
    import copy as _copy
    from simulation.hydraulics.simulate import simulate
    from simulation.validation.checks import check_surface, check_mass
    t0 = time.time()
    twin, nets = _G["twin"], _G["nets"]
    rain_cfg, hyd_cfg = _G["rain_cfg"], _G["hyd_cfg"]
    spec = _copy.deepcopy(spec)
    if spec.get("bullseye_lowpoint"):
        spec["storm_center_xy"] = _lowpoint_center(twin)
    dem, manning, dem_delta = _build_overrides(twin, spec)
    base = nets[int(spec["network_variant"])]
    net = _copy.deepcopy(base)
    deff = float(spec.get("drain_eff", 1.0))
    for e in net["edges"]:
        e["capacity_m3s"] = float(e["capacity_m3s"]) * deff
    rng = np.random.default_rng(int(spec["seed"]) + 999)
    # blockage array (same policy as v1, recorded per edge)
    nE = len(net["edges"])
    level, mode = float(spec.get("blockage_level", 0.0)), spec.get("blockage_mode", "pipe_uniform")
    b = np.zeros(nE)
    if level and level > 0:
        if mode == "pipe_uniform":
            b[:] = level
        elif mode == "inlet_subset":
            idx = rng.choice(nE, size=max(1, int(nE * min(level + 0.15, 1.0))), replace=False)
            b[idx] = min(0.95, level + 0.2)
        else:
            for e, ed in enumerate(net["edges"]):
                v = net["nodes"][ed["v"]]
                b[e] = min(0.95, level + 0.25) if v["kind"] == "outfall" else level * 0.4
    # stash blockage into net so DrainageState-free simulate path matches v1 behaviour
    spec["_blockage"] = b.tolist()
    res = simulate(twin, net, spec, hyd_cfg, rain_cfg, dem=dem, manning=manning,
                   imperv_open=spec.get("imperv_open"),
                   inlet_cap_scale=deff, dep_scale=float(spec.get("dep_scale", 1.0)))
    # override blockage actually applied (simulate recomputes its own from level/mode)
    res["blockage"] = np.asarray(spec["_blockage"], dtype=np.float32)
    # drain_eff-scaled capacities for storage
    res["pipe_capacity"] = np.array([e["capacity_m3s"] for e in net["edges"]], dtype=np.float32)
    errs = check_surface(res, twin)
    merr, ok = check_mass(res)
    if merr > 0.35:
        errs = errs + [f"mass conservation failed: err={merr:.3f}"]
    wet = twin.in_domain & (~twin.is_building)
    fl = np.asarray(res["depth"] >= 0.05)
    flood_frac = float(fl.reshape(fl.shape[0], -1)[:, wet.ravel()].mean()) if wet.any() else 0.0
    payload = {
        "spec": spec, "sim_time_s": time.time() - t0,
        "errors": errs, "mass_err": float(merr),
        "max_depth_m": float(res["max_depth"].max()), "flood_frac": flood_frac,
        "arrays": {k: np.asarray(res[k]) for k in
                   ["rain", "depth", "velocity", "node_depth", "pipe_flow",
                    "pipe_capacity", "surcharge", "overflow",
                    "time_to_flood_min", "max_depth", "blockage"]},
        "dem_delta": dem_delta,
        "mass": res["mass"],
    }
    return payload


# ---------------------------------------------------------------- parent side
def _load_manifest(path):
    done = {}
    if os.path.exists(path):
        with open(path) as fh:
            for row in csv.DictReader(fh):
                if row.get("status") in ("valid", "quarantined"):
                    done[row["scenario_id"]] = row
    return done


def _append_manifest(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in MANIFEST_COLUMNS})


STATIC_GRIDS = ["dem", "manning", "imperv", "in_domain", "is_road", "is_building",
                "X", "Y", "slope", "flow_accum", "low_points"]


def _write_static(f, twin):
    import h5py
    def _put(k, arr, dtype=None):
        if k not in f:
            f.create_dataset(k, data=np.asarray(arr) if dtype is None else np.asarray(arr, dtype=dtype),
                             compression="gzip", shuffle=True)
    _put("dem", twin.dem); _put("manning", twin.manning); _put("imperv", twin.imperv)
    _put("in_domain", twin.in_domain.astype("u1")); _put("is_road", twin.is_road.astype("u1"))
    _put("is_building", twin.is_building.astype("u1"))
    _put("X", twin.X); _put("Y", twin.Y); _put("slope", twin.slope)
    _put("flow_accum", twin.accum.astype("f4")); _put("low_points", twin.low_points.astype("u1"))
    f.attrs["crs_calc"] = "EPSG:32643"
    f.attrs["synthetic"] = True
    f.attrs["note"] = "SYNTHETIC physics-based training data — NOT observations"
    f.attrs["dataset_version"] = DATASET_VERSION
    f.attrs["simulator_version"] = SIMULATOR_VERSION
    f.attrs["generated_utc"] = datetime.datetime.utcnow().isoformat() + "Z"


def _write_scenario(f, sid, payload):
    import h5py
    spec = payload["spec"]
    # clean spec for JSON (drop helper arrays)
    spec_json = {k: (list(v) if isinstance(v, tuple) else v)
                 for k, v in spec.items() if not k.startswith("_")}
    spec_json["mass_err"] = payload["mass_err"]
    g = f.require_group(sid)
    for k, arr in payload["arrays"].items():
        if k in g:
            del g[k]
        g.create_dataset(k, data=arr, compression="gzip", shuffle=True)
    if "flooded" in g:
        del g["flooded"]
    g.create_dataset("flooded",
                     data=np.asarray(payload["arrays"]["depth"] >= 0.05, dtype="u1"),
                     compression="gzip", shuffle=True)
    if "dem_delta" in g:
        del g["dem_delta"]
    g.create_dataset("dem_delta", data=payload["dem_delta"], compression="gzip", shuffle=True)
    g.attrs["flood_threshold_m"] = 0.05
    g.attrs["spec"] = json.dumps(spec_json)
    g.attrs["mass"] = json.dumps(payload["mass"])
    g.attrs["mass_err"] = payload["mass_err"]
    g.attrs["network_variant"] = spec["network_variant"]
    g.attrs["dataset_version"] = DATASET_VERSION


def run(prod_n=240, ood_n=36, seed=26085, out_dir="outputs/datasets",
        workers=3, only="all", resume=True):
    import h5py, yaml
    from simulation.terrain.twin import Twin
    os.makedirs(out_dir, exist_ok=True)
    ood_dir = os.path.join(out_dir, "ood")
    os.makedirs(ood_dir, exist_ok=True)
    smoke = os.environ.get("DRISHTI_SMOKE", "")
    manifest_path = os.path.join(out_dir, "dataset_manifest.csv")
    done = _load_manifest(manifest_path) if resume else {}

    prod_specs = make_prod_suite(prod_n, seed, N_NETWORK_VARIANTS)
    splits = assign_splits(prod_specs, seed + 7)
    split_of = {}
    for sname, idx in splits.items():
        for k in idx:
            split_of[k] = sname
    for k, sp in enumerate(prod_specs):
        sp["ml_split"] = split_of[k]
    ood_specs = make_ood_suite(ood_n, seed + 9999, N_NETWORK_VARIANTS)

    tasks = []
    if only in ("all", "prod"):
        tasks += [("prod", sp) for sp in prod_specs]
    if only in ("all", "ood"):
        tasks += [("ood", sp) for sp in ood_specs]
    if only == "topup":
        tasks += [("topup", sp) for sp in make_topup_suite()]
        tasks += [("topup", sp) for sp in make_longdry_suite()]

    def _sid(kind, sp):
        tag = sp["ml_split"] if kind in ("prod", "topup") else "ood"
        return f"{tag}_v1_{sp['scenario_idx']:05d}", tag

    pending = []
    for kind, sp in tasks:
        sid, tag = _sid(kind, sp)
        if sid in done:
            continue
        pending.append((kind, sp, sid, tag))
    print(f"[v2] dataset v{DATASET_VERSION}: {len(tasks)} total, {len(done)} done, "
          f"{len(pending)} pending (workers={workers})")

    # file handles per tag
    handles = {}
    def _handle(tag):
        if tag not in handles:
            d = ood_dir if tag == "ood" else out_dir
            p = os.path.join(d, f"kiet_flood_{tag}.h5")
            h = h5py.File(p, "a")
            # static grids need a twin; build once lazily below
            handles[tag] = (h, p)
        return handles[tag]

    # base twin for static grids (cheap, local)
    ter_cfg = yaml.safe_load(open("config/terrain.yaml"))
    base_twin = Twin(ter_cfg)

    from concurrent.futures import ProcessPoolExecutor, as_completed
    cfg_paths = {"terrain": "config/terrain.yaml", "drainage": "config/drainage.yaml",
                 "rainfall": "config/rainfall.yaml", "hydraulics": "config/hydraulics.yaml",
                 "seed": seed, "nvar": N_NETWORK_VARIANTS}
    n_ok = n_q = 0
    t_start = time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(cfg_paths,)) as ex:
        futs = {ex.submit(_run_one, sp): (kind, sp, sid, tag)
                for kind, sp, sid, tag in pending}
        for fut in as_completed(futs):
            kind, sp, sid, tag = futs[fut]
            try:
                p = fut.result()
            except Exception as exn:  # never lose the traceback; mark failed (retryable)
                import traceback
                _append_manifest(manifest_path, {
                    "scenario_id": sid, "seed": sp["seed"], "split": tag, "status": "failed",
                    "rain_class": sp.get("rain_class"), "edge_case": sp.get("edge_case"),
                    "temporal": sp.get("temporal"), "spatial": sp.get("spatial"),
                    "total_mm": sp.get("total_mm"), "duration_h": sp.get("duration_h"),
                    "recession_h": sp.get("recession_h"), "network_variant": sp.get("network_variant"),
                    "drain_eff": sp.get("drain_eff"), "blockage_level": sp.get("blockage_level"),
                    "blockage_mode": sp.get("blockage_mode"), "terrain_seed": sp.get("terrain_seed"),
                    "manning_scale": sp.get("manning_scale"), "dep_scale": sp.get("dep_scale"),
                    "imperv_open": sp.get("imperv_open"), "sim_time_s": "",
                    "validation_status": "error", "mass_err": "", "max_depth_m": "",
                    "flood_frac": "", "file_path": "", "errors": repr(exn)[:500]})
                print(f"[v2] {sid} FAILED: {exn!r}", flush=True)
                continue
            h, hpath = _handle(tag)
            if p["errors"]:
                # quarantine: full record kept separately, never in train files
                qpath = os.path.join(out_dir, "kiet_flood_quarantine.h5")
                with h5py.File(qpath, "a") as q:
                    _write_static(q, base_twin)
                    _write_scenario(q, sid, p)
                status, vstat, fpath = "quarantined", "quarantined", qpath
                n_q += 1
            else:
                _write_static(h, base_twin)
                _write_scenario(h, sid, p)
                h.flush()
                status, vstat, fpath = "valid", "pass", hpath
                n_ok += 1
            _append_manifest(manifest_path, {
                "scenario_id": sid, "seed": sp["seed"], "split": tag, "status": status,
                "rain_class": sp.get("rain_class"), "edge_case": sp.get("edge_case"),
                "temporal": sp.get("temporal"), "spatial": sp.get("spatial"),
                "total_mm": sp.get("total_mm"), "duration_h": sp.get("duration_h"),
                "recession_h": sp.get("recession_h"), "network_variant": sp.get("network_variant"),
                "drain_eff": sp.get("drain_eff"), "blockage_level": sp.get("blockage_level"),
                "blockage_mode": sp.get("blockage_mode"), "terrain_seed": sp.get("terrain_seed"),
                "manning_scale": sp.get("manning_scale"), "dep_scale": sp.get("dep_scale"),
                "imperv_open": sp.get("imperv_open"), "sim_time_s": round(p["sim_time_s"], 1),
                "validation_status": vstat, "mass_err": round(p["mass_err"], 6),
                "max_depth_m": round(p["max_depth_m"], 4), "flood_frac": round(p["flood_frac"], 5),
                "file_path": fpath, "errors": "; ".join(p["errors"])[:500]})
            el = time.time() - t_start
            print(f"[v2] {sid} {status} rain={sp['total_mm']:.0f}mm dur={sp['duration_h']:.1f}h "
                  f"maxd={p['max_depth_m']:.3f}m merr={p['mass_err']:.4f} "
                  f"t={p['sim_time_s']:.0f}s elapsed={el/60:.1f}min", flush=True)
    for h, _ in handles.values():
        h.close()
    # networks archive (base capacities; per-scenario drain_eff in spec)
    import numpy as _np
    from simulation.drainage.network import generate as gen_net
    import yaml as _yaml
    dra_cfg = _yaml.safe_load(open("config/drainage.yaml"))
    nets = [gen_net(base_twin, dra_cfg, seed=seed, variant=v) for v in range(N_NETWORK_VARIANTS)]
    def _coerce(o):
        if isinstance(o, (_np.integer,)): return int(o)
        if isinstance(o, (_np.floating,)): return float(o)
        if isinstance(o, (_np.ndarray,)): return o.tolist()
        if isinstance(o, dict): return {k: _coerce(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [_coerce(v) for v in o]
        return o
    json.dump(_coerce(nets), open(os.path.join(out_dir, "kiet_networks_v1.json"), "w"))
    print(f"[v2] done: +{n_ok} valid, +{n_q} quarantined, elapsed={(time.time()-t_start)/60:.1f}min")
    return manifest_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod-n", type=int, default=240)
    ap.add_argument("--ood-n", type=int, default=36)
    ap.add_argument("--seed", type=int, default=26085)
    ap.add_argument("--out-dir", default="outputs/datasets")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="all", choices=["all", "prod", "ood", "topup"])
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--smoke", action="store_true",
                    help="4 quick scenarios into outputs/datasets/smoke (overrides n)")
    a = ap.parse_args()
    if a.smoke:
        a.prod_n, a.ood_n, a.out_dir = 3, 1, "outputs/datasets/smoke"
    run(a.prod_n, a.ood_n, a.seed, a.out_dir, a.workers, a.only, resume=not a.no_resume)
