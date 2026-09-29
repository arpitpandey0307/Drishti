import pathlib
h = pathlib.Path("kiet_road_map.html").read_text()
assert "leaflet@1.9.4" in h, "leaflet CDN missing"
assert "L.map('map')" in h or 'L.map("map")' in h, "map init missing"
assert "data/roads.geojson" in h, "roads fetch missing"
assert "© OpenStreetMap contributors" in h, "attribution missing"
print("OK shell")
