import json, sys, pathlib
for p in ["data/roads.geojson", "data/campus.geojson"]:
    fp = pathlib.Path(p)
    assert fp.exists(), f"missing {p}"
    j = json.loads(fp.read_text())
    assert j["type"] == "FeatureCollection", f"{p} not FC"
    assert len(j["features"]) > 5, f"{p} too few features"
    print(f"OK {p}: {len(j['features'])} features")
# check road props
roads = json.loads(pathlib.Path("data/roads.geojson").read_text())
hwys = set(f["properties"].get("highway","?") for f in roads["features"])
assert "service" in hwys, f"no service roads, got {hwys}"
assert "footway" in hwys or "residential" in hwys, f"no minor roads {hwys}"
print("OK road classes:", hwys)
