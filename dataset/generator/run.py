"""Resumable, seeded HDF5 dataset generator."""
from __future__ import annotations
import os, json, yaml, h5py, numpy as np
from simulation.terrain.twin import Twin
from simulation.drainage.network import generate as gen_net
from simulation.scenarios.spec import make_suite
from simulation.hydraulics.simulate import simulate
from simulation.validation.checks import check_surface, check_mass, check_graph, check_lowpoints_accumulate

def _blockage_for_edges(nE, level, mode, rng):
    import numpy as np
    b = np.zeros(nE)
    if level and level > 0:
        if mode == "pipe_uniform": b[:] = level
        elif mode == "inlet_subset":
            idx = rng.choice(nE, size=max(1, int(nE * min(level + 0.15, 1.0))), replace=False)
            b[idx] = min(0.95, level + 0.2)
        else: b[:] = level * 0.6
    return b

def run(split="test", n=None, seed=None, out_dir="outputs/datasets", resume=True):
    sim_cfg = yaml.safe_load(open("config/simulation.yaml"))
    ter_cfg = yaml.safe_load(open("config/terrain.yaml"))
    dra_cfg = yaml.safe_load(open("config/drainage.yaml"))
    rain_cfg = yaml.safe_load(open("config/rainfall.yaml"))
    hyd_cfg = yaml.safe_load(open("config/hydraulics.yaml"))
    ds = sim_cfg["dataset"]
    n = n or ds.get(f"{split}_n", 10)
    seed = ds.get("seed", 26085) if seed is None else seed
    nvar = ds.get("network_variants", 3)
    os.makedirs(out_dir, exist_ok=True)
    twin = Twin(ter_cfg)
    nets = [gen_net(twin, dra_cfg, seed=seed, variant=v) for v in range(nvar)]
    for net in nets:
        errs = check_graph(net)
        assert not errs, f"graph invalid: {errs[:3]}"
    specs = make_suite(n, seed + hash(split) % 10000, rain_cfg, nvar)
    path = os.path.join(out_dir, f"kiet_flood_{split}.h5")
    manifest = os.path.join(out_dir, f"kiet_flood_{split}_manifest.json")
    done = set()
    if resume and os.path.exists(manifest):
        try: done = set(json.load(open(manifest)).get("done", []))
        except Exception: done = set()
    mode = "a" if os.path.exists(path) else "w"
    results = []
    with h5py.File(path, mode) as f:
        f.attrs["synthetic"] = True
        f.attrs["note"] = "SYNTHETIC physics-based training data — NOT observations"
        for sp in specs:
            sid = f"scenario_{sp['id']:04d}"
            if sid in done and sid in f:
                continue
            net = nets[sp["network_variant"]]
            res = simulate(twin, net, sp, hyd_cfg, rain_cfg)
            errs = check_surface(res, twin)
            merr, ok = check_mass(res)
            låg, *_ = check_lowpoints_accumulate(twin, res)
            if errs:
                print(f"[WARN] {sid} surface issues: {errs}")
            g = f.require_group(sid)
            for k in ["rain", "depth", "velocity", "node_depth", "pipe_flow",
                      "pipe_capacity", "surcharge", "overflow", "time_to_flood_min",
                      "max_depth", "blockage"]:
                if k in g: del g[k]
                data = res[k]
                g.create_dataset(k, data=np.asarray(data), compression="gzip", shuffle=True)
            if "flooded" in g: del g["flooded"]
            g.create_dataset("flooded", data=np.asarray(res["depth"] >= 0.05, dtype="u1"),
                             compression="gzip", shuffle=True)
            g.attrs["flood_threshold_m"] = 0.05
            g.attrs["spec"] = json.dumps(sp)
            g.attrs["mass"] = json.dumps(res["mass"])
            g.attrs["mass_err"] = float(merr)
            g.attrs["network_variant"] = sp["network_variant"]
            done.add(sid)
            results.append((sid, merr, ok))
            json.dump({"done": sorted(done)}, open(manifest, "w"))
            print(f"[{split}] {sid} rain={sp['total_mm']:.0f}mm blk={sp['blockage_level']} "
                  f"maxd={res['max_depth'].max():.3f}m mass_err={merr:.3f}")
    # static grids once
    with h5py.File(path, "a") as f:
        for k, arr in [("dem", twin.dem), ("manning", twin.manning), ("imperv", twin.imperv),
                       ("in_domain", twin.in_domain.astype("u1")), ("is_road", twin.is_road.astype("u1")),
                       ("is_building", twin.is_building.astype("u1")), ("X", twin.X), ("Y", twin.Y)]:
            if k not in f: f.create_dataset(k, data=arr, compression="gzip")
        f.attrs["crs_calc"] = "EPSG:32643"
    # save networks
    import numpy as _np
    def _coerce(o):
        if isinstance(o, (_np.integer,)): return int(o)
        if isinstance(o, (_np.floating,)): return float(o)
        if isinstance(o, (_np.ndarray,)): return o.tolist()
        if isinstance(o, dict): return {k: _coerce(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [_coerce(v) for v in o]
        return o
    json.dump(_coerce(nets), open(os.path.join(out_dir, f"kiet_networks_{split}.json"), "w"))
    return path

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test"); ap.add_argument("--n", type=int, default=None)
    a = ap.parse_args()
    run(a.split, a.n)
