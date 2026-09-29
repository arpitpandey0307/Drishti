"""Route on live HF-Space-hosted nowcasts: fetch window + ONNX weights, predict, route."""
import json
import os
import urllib.request

SPACE = "https://aman34243-drishti-flood-nowcast.static.hf.space"
LEADS = [5, 10, 20, 30, 40, 60, 90, 120, 180]


def _get(base, path, cache):
    os.makedirs(cache, exist_ok=True)
    local = os.path.join(cache, path.replace("/", "_"))
    if not os.path.exists(local):
        with urllib.request.urlopen(f"{base}/{path}", timeout=120) as r:
            open(local, "wb").write(r.read())
    return local


def nowcast_route(base=SPACE, cache="/tmp/space_cache", window=0, lead_min=30,
                  start=(20, 20), end=(90, 140)):
    import numpy as np
    import onnxruntime as ort
    from api.route import safe_route
    meta = json.load(open(_get(base, "windows/meta.json", cache)))
    w = meta["windows"][window]
    x = np.fromfile(_get(base, "windows/" + w["file"], cache), dtype="<f4")
    x = x.reshape(1, meta["channels"], meta["ny"], meta["nx"])
    onnx_path = _get(base, "drishti.onnx", cache)
    try:
        _get(base, "drishti.onnx.data", cache)  # sidecar weights, if present
    except Exception:
        pass  # single-file ONNX needs no sidecar
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    pred = np.maximum(sess.run(None, {"input": x})[0][0], 0)
    li = LEADS.index(lead_min)
    depth = pred[li]
    r = safe_route(depth, np.ones_like(depth, bool), start, end)
    return {"scenario": w["sid"], "t0": w["t0"], "lead_min": lead_min,
            "max_depth_m": round(float(depth.max()), 4),
            "flooded_m2": int((depth >= 0.05).sum()) * 25,
            "route_blocked": r["blocked"], "route_length_m": round(r["length_m"], 1),
            "route_cells": len(r["path"])}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=SPACE)
    ap.add_argument("--window", type=int, default=0)
    ap.add_argument("--lead-min", type=int, default=30)
    ap.add_argument("--from", dest="frm", default="20,20")
    ap.add_argument("--to", default="90,140")
    a = ap.parse_args()
    s = tuple(int(v) for v in a.frm.split(","))
    e = tuple(int(v) for v in a.to.split(","))
    print(json.dumps(nowcast_route(a.base, "/tmp/space_cache", a.window,
                                   a.lead_min, s, e), indent=1))


if __name__ == "__main__":
    main()
