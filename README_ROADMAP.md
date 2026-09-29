# KIET Road Map
Open via `python3 -m http.server 8000` then http://localhost:8000/kiet_road_map.html
Data: `data/roads.geojson` (OSM highways), `data/campus.geojson` (buildings/pitches + screenshot boundary + 12 labels)
Rebuild: `python3 scripts/build_road_data.py`
Sources: © OpenStreetMap contributors; boundary from user screenshot red outline (approx lat/lng).
