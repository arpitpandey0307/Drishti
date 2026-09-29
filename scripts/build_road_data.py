import urllib.request, urllib.parse, json, pathlib
BBOX = (28.7480, 77.4920, 28.7585, 77.5050)  # S,W,N,E
OVERPASS = "https://overpass-api.de/api/interpreter"
OUT_ROADS = pathlib.Path("data/roads.geojson")
OUT_CAMPUS = pathlib.Path("data/campus.geojson")

def fetch(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "DrishtiKIET/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def to_line(el: dict):
    geom = el.get("geometry")
    if not geom or len(geom) < 2:
        return None
    tags = el.get("tags", {})
    coords = [[round(p["lon"], 6), round(p["lat"], 6)] for p in geom]
    return {
        "type": "Feature",
        "properties": {
            "name": tags.get("name", ""),
            "highway": tags.get("highway", ""),
            "service": tags.get("service", ""),
            "access": tags.get("access", ""),
            "tunnel": tags.get("tunnel", ""),
            "ref": tags.get("ref", ""),
            "osm_id": el.get("id"),
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }

def to_poly(el: dict):
    geom = el.get("geometry")
    if not geom or len(geom) < 3:
        return None
    tags = el.get("tags", {})
    coords = [[round(p["lon"], 6), round(p["lat"], 6)] for p in geom]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    kind = "building"
    if tags.get("leisure") in ("pitch", "stadium", "sports_centre"):
        kind = "pitch"
    return {
        "type": "Feature",
        "properties": {
            "kind": kind,
            "name": tags.get("name", ""),
            "building": tags.get("building", ""),
            "leisure": tags.get("leisure", ""),
            "sport": tags.get("sport", ""),
            "osm_id": el.get("id"),
        },
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }

def build_road_data() -> None:
    s, w, n, e = BBOX
    rq = f"[out:json][timeout:30];(way[\"highway\"]({s},{w},{n},{e}););out geom 200;"
    rj = fetch(rq)
    feats = [f for el in rj.get("elements", []) if (f := to_line(el))]
    OUT_ROADS.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROADS.write_text(json.dumps({"type": "FeatureCollection", "name": "KIET roads", "features": feats}))
    print(f"roads: {len(feats)} -> {OUT_ROADS}")
    bq = f"[out:json][timeout:30];(way[\"building\"]({s},{w},{n},{e});way[\"leisure\"~\"pitch|stadium|sports_centre\"]({s},{w},{n},{e}););out geom 300;"
    bj = fetch(bq)
    polys = [f for el in bj.get("elements", []) if (f := to_poly(el))]
    # merge boundary + labels
    bnd = json.loads(pathlib.Path("kiet_campus_map/boundary.geojson").read_text())
    for f in bnd["features"]:
        f["properties"]["kind"] = "boundary"
        polys.append(f)
    lbl = json.loads(pathlib.Path("kiet_campus_map/visible_features.geojson").read_text())
    for f in lbl["features"]:
        f["properties"]["kind"] = "label"
        polys.append(f)
    OUT_CAMPUS.write_text(json.dumps({"type": "FeatureCollection", "name": "KIET campus context", "features": polys}))
    print(f"campus: {len(polys)} -> {OUT_CAMPUS}")

if __name__ == "__main__":
    build_road_data()
