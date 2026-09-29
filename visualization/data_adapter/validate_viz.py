"""Validate viz bundles against simulation H5 outputs (exactness proof)."""
import json
import numpy as np
import h5py

fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, info)
    if not cond:
        fails.append(name)


def b16(s):
    import base64
    return np.frombuffer(base64.b64decode(s), dtype=np.int16)


def b32(s):
    import base64
    return np.frombuffer(base64.b64decode(s), dtype=np.int32)


f = h5py.File("outputs/datasets/kiet_flood_test.h5", "r")
nets = json.load(open("outputs/datasets/kiet_networks_test.json"))
idx = json.load(open("outputs/viz/index.json"))
check("index covers 10 v0 scenarios", sum(1 for e in idx if e["id"].startswith("test_scenario_")) == 10, f"got {len(idx)} total")

sid = "test_scenario_0009"
g = f["scenario_0009"]
meta = json.load(open(f"outputs/viz/{sid}/meta.json"))
ny, nx = meta["ny"], meta["nx"]
T = meta["T"]
spec = json.loads(g.attrs["spec"])

# 1. static grids exact
dem = b16(meta["dem_cm"]["b64i16"]).reshape(ny, nx) / 100.0
check("dem matches H5 (cm)", np.abs(dem - f["dem"][:]).max() < 0.006,
      f"maxerr={np.abs(dem - f['dem'][:]).max():.4f}")
mxd = b16(meta["max_depth_mm"]["b64i16"]).reshape(ny, nx) / 1000.0
check("max_depth matches (mm)", np.abs(mxd - g["max_depth"][:]).max() < 0.0006)
ttf = b16(meta["time_to_flood_min"]["b64i16"]).reshape(ny, nx)
h5ttf = np.where(np.isfinite(g["time_to_flood_min"][:]),
                 np.round(g["time_to_flood_min"][:]).astype(int), -1)
check("time_to_flood matches (min)", np.array_equal(ttf, h5ttf))

# 2. every frame exact (sample k=0, mid, last)
for k in [0, T // 2, T - 1]:
    fr = json.load(open(f"outputs/viz/{sid}/frame_{k:03d}.json"))
    check(f"frame {k} timeline t={(k+1)*5}min", fr["t_min"] == (k + 1) * 5)
    r = b16(fr["rain_dmm"]["b64i16"]).reshape(ny, nx) / 10.0
    check(f"frame {k} rain (0.1mm)", np.abs(r - g["rain"][k]).max() < 0.06)
    d = b16(fr["depth_mm"]["b64i16"]).reshape(ny, nx) / 1000.0
    check(f"frame {k} depth (mm)", np.abs(d - g["depth"][k]).max() < 0.0006)
    nd = b16(fr["node_mm"]["b64i16"]) / 1000.0
    check(f"frame {k} node_depth (mm)", np.abs(nd - g["node_depth"][k]).max() < 0.0006)
    pf = b32(fr["pipe_e5"]["b64i32"]) / 1e5
    check(f"frame {k} pipe_flow (1e-5)", np.abs(pf - g["pipe_flow"][k]).max() < 6e-6)

# 3. network topology identical to generator output
net = nets[spec["network_variant"]]
check("node count", len(meta["nodes"]) == len(net["nodes"]))
check("edge count", len(meta["edges"]) == len(net["edges"]))
for a, b in zip(meta["nodes"], net["nodes"]):
    assert (a["i"], a["j"]) == (b["i"], b["j"]), "node cell mismatch"
check("node cells match graph", True)
for a, b in zip(meta["edges"], net["edges"]):
    assert (a["u"], a["v"]) == (b["u"], b["v"]), "edge direction mismatch"
check("edge u->v directions match graph", True)

# 4. surcharge derivation == hydraulic model report (final frame)
k = T - 1
fr = json.load(open(f"outputs/viz/{sid}/frame_{k:03d}.json"))
nd = b32(fr["node_mm"]["b64i32"]) / 1000.0 if False else b16(fr["node_mm"]["b64i16"]) / 1000.0
RIM = meta["node_maxdepth_m"] - 0.002
derived = set(int(n["id"]) for n in meta["nodes"]
              if n["kind"] != "outfall" and nd[n["id"]] >= RIM)
stored = set(meta["surcharge_final_ids"])
# stored surcharge is boolean per node at END; node order == id order
check("surcharge set matches model", derived == stored, f"derived={sorted(derived)} stored={sorted(stored)}")

# 5. per-frame summary metrics match recomputation
for k in [0, T // 2, T - 1]:
    fr = json.load(open(f"outputs/viz/{sid}/frame_{k:03d}.json"))
    d = b16(fr["depth_mm"]["b64i16"]).reshape(ny, nx) / 1000.0
    dom = f["in_domain"][:].astype(bool)
    fl = int((((d * 1000).round() >= 50) & dom).sum())
    check(f"frame {k} flooded_cells", meta["frames"][k]["flood_cells"] == fl, f"{fl}")

print("\n%d FAILURES" % len(fails) if fails else "\nALL CHECKS PASSED")
raise SystemExit(1 if fails else 0)
