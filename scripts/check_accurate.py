import json, sys
p = "data/campus_accurate.geojson"
d = json.load(open(p))
assert d["type"] == "FeatureCollection", "not FC"
kinds = [f["properties"].get("kind") for f in d["features"]]
for need in ["sanctioned_building", "boundary_khasra", "label_accurate"]:
    assert need in kinds, f"missing kind {need}"
banned = {"parking", "solar", "road_sanctioned"}
assert not (set(kinds) & banned), f"unverified kinds shipped: {set(kinds) & banned}"
for f in d["features"]:
    g = f["geometry"]
    if g["type"] == "Polygon":
        c = g["coordinates"][0]
        assert c[0] == c[-1], "ring not closed"
        assert len(c) >= 5, "ring too few points"
        for lon, lat in c:
            assert 77.49 < lon < 77.51, f"lon out of range {lon}"
            assert 28.74 < lat < 28.76, f"lat out of range {lat}"
print(f"OK {len(d['features'])} feats")
