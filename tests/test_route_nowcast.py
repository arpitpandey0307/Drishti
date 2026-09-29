def test_nowcast_route_local_files():
    # file://-style base: serve /tmp/space layout from a local copy (no network)
    import os
    import shutil
    import numpy as np
    d = "/tmp/route_nc_test"
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d + "/windows", exist_ok=True)
    for f in ["drishti.onnx", "drishti.onnx.data", "windows/meta.json", "windows/w0.bin"]:
        shutil.copy("/tmp/space/" + f, d + "/" + f)
    # monkeypatch urlopen to read local files
    import urllib.request
    from api import route_nowcast as rn
    real = urllib.request.urlopen

    class _R:
        def __init__(self, p):
            self._f = open(p, "rb")
        def read(self):
            return self._f.read()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            self._f.close()

    urllib.request.urlopen = lambda url, timeout=120: _R(d + "/" + url.split("LOCALBASE/")[1])
    try:
        out = rn.nowcast_route(base="LOCALBASE", cache=d + "/cache", window=0,
                               lead_min=30, start=(20, 20), end=(90, 140))
    finally:
        urllib.request.urlopen = real
    assert out["scenario"] == "val_v1_00213" and out["lead_min"] == 30
    assert out["max_depth_m"] > 0 and out["flooded_m2"] >= 0
    assert isinstance(out["route_blocked"], bool) and out["route_length_m"] >= 0
