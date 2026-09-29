import json, csv
acc = json.load(open("data/campus_accurate.geojson"))
kinds = set(f["properties"].get("kind") for f in acc["features"])
# shipped file must contain ONLY verified geometry: snapped buildings, labels, khasra
assert kinds <= {"sanctioned_building", "label_accurate", "boundary_khasra"}, f"unverified kind shipped: {kinds}"
for f in acc["features"]:
    p = f["properties"]
    if p.get("kind") == "sanctioned_building":
        assert p.get("osm_match"), f"{p.get('sanctioned_name')} shipped without OSM match"
    g = f["geometry"]
    if g["type"] == "Polygon":
        c = g["coordinates"][0]
        assert c[0] == c[-1], "ring not closed"
        assert len(c) >= 5, "ring too few points"
        for lon, lat in c:
            assert 77.49 < lon < 77.51, f"lon out of range {lon}"
            assert 28.74 < lat < 28.76, f"lat out of range {lat}"
# numeric sanctioned truths live on in the unverified sketch file (areas dimension-true)
sk = json.load(open("data/campus_sanctioned_unverified.geojson"))
pk = [f for f in sk["features"] if f["properties"].get("kind") == "parking"]
ps = sum(f["properties"].get("area_sqm", 0) for f in pk)
print(f"shipped {len(acc['features'])} feats; sketch parking {len(pk)} pockets sum {ps:.2f} vs sanctioned 20232.12")
assert len(pk) >= 15, "sketch parking incomplete"
assert 15000 < ps < 26000, f"parking sum {ps} outside tolerance"
print("SUMS OK")
