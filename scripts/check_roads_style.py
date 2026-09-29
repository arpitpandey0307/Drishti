import pathlib
h = pathlib.Path("kiet_road_map.html").read_text()
for token in ["styleRoad", "NH-34", "service", "footway", "dashArray", "L.control.layers", "legend"]:
    assert token in h, f"missing {token}"
print("OK road styling")
