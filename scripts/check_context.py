import pathlib
h = pathlib.Path("kiet_road_map.html").read_text()
for token in ["renderCampus", "kind==='building'", "kind==='pitch'", "kind==='boundary'", "kind==='label'", "bindTooltip"]:
    assert token in h, f"missing {token}"
print("OK context")
