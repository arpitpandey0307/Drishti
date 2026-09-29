# KIET Road Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build offline-capable interactive road-focused 2D map `kiet_road_map.html` + local GeoJSON for KIET campus.

**Architecture:** Python build script fetches OSM Overpass bbox and converts to local GeoJSON; single Leaflet HTML page renders roads by hierarchy with context layers, no backend.

**Tech Stack:** Python 3 stdlib (urllib, json) for build; Leaflet 1.9.4 via CDN for map; GeoJSON WGS84; OSM tiles optional.

## Global Constraints

- Coordinate system WGS84 lat/lng throughout, 6-decimal precision.
- OSM attribution `© OpenStreetMap contributors` visible always.
- Disclaimer `Approx. OSM + screenshot reconstruction — not for surveying/emergency` in corner.
- Total bundle < 1MB (excluding existing zip).
- Works via `python3 -m http.server` and degrades gracefully on `file://` + blocked CDN.
- Do not scrape Google tiles; OSM + user screenshot geometry only.

---

### Task 1: Build OSM data bundle

**Files:**
- Create: `/home/devdevil/development/drishti/scripts/build_road_data.py`
- Create: `/home/devdevil/development/drishti/data/roads.geojson`
- Create: `/home/devdevil/development/drishti/data/campus.geojson`
- Test: `/home/devdevil/development/drishti/scripts/validate_geojson.py`

**Interfaces:**
- Consumes: Overpass API `https://overpass-api.de/api/interpreter`, existing `/home/devdevil/development/drishti/kiet_campus_map/boundary.geojson`, `/home/devdevil/development/drishti/kiet_campus_map/visible_features.geojson`
- Produces: `build_road_data() -> writes data/roads.geojson (FeatureCollection LineString, props: name, highway, service, access, tunnel, ref)` and `data/campus.geojson (FeatureCollection Polygon+Point, props: kind, name, category, source)`; later tasks fetch these via `fetch('data/roads.geojson')`

- [ ] **Step 1: Write the failing validation script**

```python
# scripts/validate_geojson.py
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
```

- [ ] **Step 2: Run validation to verify it fails**

Run: `python3 scripts/validate_geojson.py`
Expected: FAIL with `missing data/roads.geojson` (files don't exist yet)

- [ ] **Step 3: Write minimal build script**

```python
# scripts/build_road_data.py
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

def to_line(el: dict) -> dict | None:
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

def to_poly(el: dict) -> dict | None:
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
```

- [ ] **Step 4: Run build then validation to verify it passes**

Run: `python3 scripts/build_road_data.py && python3 scripts/validate_geojson.py`
Expected: PASS with `OK data/roads.geojson: 150+ features`, `OK road classes: {... 'service' ...}`

- [ ] **Step 5: Commit**

```bash
git init 2>/dev/null || true; git add scripts/build_road_data.py scripts/validate_geojson.py data/roads.geojson data/campus.geojson docs/superpowers/specs/2026-09-04-kiet-road-map-design.md; git commit -m "feat: add KIET OSM road + campus GeoJSON bundle" || echo "commit skipped - no git user"
```

### Task 2: Map shell + base layers

**Files:**
- Create: `/home/devdevil/development/drishti/kiet_road_map.html`
- Test: manual open + `python3 -c "assert open('kiet_road_map.html').read().count('leaflet')>=2"`

**Interfaces:**
- Consumes: `data/roads.geojson`, `data/campus.geojson` via fetch()
- Produces: global `window.KIET = {map, layerGroups: {main, internal, foot, context, boundary, labels}}` for Task 3-4 to extend

- [ ] **Step 1: Write failing shell check**

```python
# inline check file: scripts/check_shell.py
import pathlib
h = pathlib.Path("kiet_road_map.html").read_text()
assert "leaflet@1.9.4" in h, "leaflet CDN missing"
assert "L.map('map')" in h or 'L.map("map")' in h, "map init missing"
assert "data/roads.geojson" in h, "roads fetch missing"
assert "© OpenStreetMap contributors" in h, "attribution missing"
print("OK shell")
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python3 scripts/check_shell.py`
Expected: FAIL with `kiet_road_map.html does not exist` or `leaflet CDN missing`

- [ ] **Step 3: Write minimal HTML shell**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>KIET Campus Road Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{height:100%;margin:0}#map{background:#f8f9fa}.notice{position:absolute;z-index:999;left:8px;bottom:28px;background:#fff;padding:4px 8px;font:12px system-ui;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.2)}</style>
</head>
<body>
<div id="map"></div>
<div class="notice">Approx. OSM + screenshot reconstruction — not for surveying/emergency</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
window.KIET = {};
const map = L.map('map').setView([28.75257, 77.49851], 16);
window.KIET.map = map;
L.control.scale().addTo(map);
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'});
osm.on('tileerror', ()=>{ map.getContainer().style.background='#f8f9fa'; });
osm.addTo(map);
window.KIET.layerGroups = {main:L.layerGroup().addTo(map),internal:L.layerGroup().addTo(map),foot:L.layerGroup().addTo(map),context:L.layerGroup().addTo(map),boundary:L.layerGroup().addTo(map),labels:L.layerGroup().addTo(map)};
Promise.all([fetch('data/roads.geojson').then(r=>r.json()),fetch('data/campus.geojson').then(r=>r.json())]).then(([roads,campus])=>{
  window.KIET.raw={roads,campus};
  const b = L.geoJSON(campus.features.filter(f=>f.properties.kind==='boundary'));
  if(b.getLayers().length) map.fitBounds(b.getBounds().pad(0.15));
});
</script>
</body>
</html>
```

- [ ] **Step 4: Run check to verify it passes**

Run: `python3 scripts/check_shell.py && python3 -m http.server 8000 & sleep 1; curl -s http://localhost:8000/kiet_road_map.html | grep -c leaflet; kill %1`
Expected: PASS `OK shell` + curl count >=2

- [ ] **Step 5: Commit**

```bash
git add kiet_road_map.html scripts/check_shell.py; git commit -m "feat: add KIET road map shell with Leaflet base" || echo "commit skipped"
```

### Task 3: Road hierarchy styling + toggles + legend

**Files:**
- Modify: `/home/devdevil/development/drishti/kiet_road_map.html`
- Test: `/home/devdevil/development/drishti/scripts/check_roads_style.py`

**Interfaces:**
- Consumes: `window.KIET.raw.roads`, `window.KIET.layerGroups`
- Produces: `window.KIET.styleRoad(feature) -> Leaflet path options`; legend `div.info.legend` with 5 entries

- [ ] **Step 1: Write failing style check**

```python
# scripts/check_roads_style.py
import pathlib
h = pathlib.Path("kiet_road_map.html").read_text()
for token in ["styleRoad", "NH-34", "service", "footway", "dashArray", "L.control.layers", "legend"]:
    assert token in h, f"missing {token}"
print("OK road styling")
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python3 scripts/check_roads_style.py`
Expected: FAIL with `missing styleRoad`

- [ ] **Step 3: Write minimal styling implementation (insert before Promise.all line, replace fetch block)**

```javascript
// road styling — insert into kiet_road_map.html <script> before Promise.all
function styleRoad(f){
  const p=f.properties||{};
  if(p.highway==='trunk') return {color:'#7e5109',weight:8,opacity:1};
  if(p.highway==='tertiary'||p.highway==='unclassified') return {color:'#7d6608',weight:6,opacity:1};
  if(p.highway==='residential') return {color:'#7f8c8d',weight:3,opacity:1};
  if(p.highway==='service') return {color:'#2c3e50',weight:7,opacity:1};
  return {color:'#7fb3d5',weight:2,opacity:1,dashArray:'6 4'};
}
function styleRoadTop(f){
  const p=f.properties||{};
  if(p.highway==='trunk') return {color:'#e67e22',weight:5};
  if(p.highway==='tertiary'||p.highway==='unclassified') return {color:'#f1c40f',weight:3};
  if(p.highway==='residential') return {color:'#bdc3c7',weight:2};
  if(p.highway==='service') return {color:'#ffffff',weight:4};
  return {color:'#7fb3d5',weight:2,dashArray:'6 4'};
}
window.KIET.styleRoad=styleRoad;
function renderRoads(roads){
  const G=window.KIET.layerGroups;
  roads.features.forEach(f=>{
    const hw=(f.properties||{}).highway||'';
    const grp = (hw==='trunk'||hw==='tertiary'||hw==='unclassified') ? G.main : (hw==='service'||hw==='residential') ? G.internal : G.foot;
    const_nm = (f.properties||{}).name || hw;
    L.geoJSON(f,{style:styleRoad}).addTo(grp);
    L.geoJSON(f,{style:styleRoadTop}).bindPopup(`<b>${const_nm}</b><br/>highway=${hw} ref=${(f.properties||{}).ref||''}`).addTo(grp);
  });
  L.control.layers(null,{ 'Main (NH-34/tertiary)':G.main,'Internal (service/residential)':G.internal,'Footpaths':G.foot },{collapsed:false}).addTo(window.KIET.map);
  const leg=L.control({position:'bottomright'});
  leg.onAdd=()=>{const d=L.DomUtil.create('div','info legend');d.style.cssText='background:#fff;padding:8px;border-radius:6px;font:12px system-ui';d.innerHTML='<b>Roads — NH-34</b><br/><span style="color:#e67e22">━━</span> Trunk NH-34<br/><span style="color:#f1c40f">━━</span> Tertiary<br/><span style="color:#fff;background:#2c3e50">━━</span> Campus service<br/><span style="color:#7fb3d5">┄┄</span> Footway';return d;};
  leg.addTo(window.KIET.map);
}
```

Wire into fetch: after `window.KIET.raw={roads,campus};` add `renderRoads(roads);`

- [ ] **Step 4: Run check to verify it passes**

Run: `python3 scripts/check_roads_style.py`
Expected: PASS `OK road styling`

- [ ] **Step 5: Commit**

```bash
git add kiet_road_map.html scripts/check_roads_style.py; git commit -m "feat: add road hierarchy styling, toggles, legend" || echo "commit skipped"
```

### Task 4: Context layers — buildings, pitches, boundary, labels

**Files:**
- Modify: `/home/devdevil/development/drishti/kiet_road_map.html`
- Test: `/home/devdevil/development/drishti/scripts/check_context.py`

**Interfaces:**
- Consumes: `window.KIET.raw.campus`, `window.KIET.layerGroups`
- Produces: rendered polygons + tooltips; no new globals (reuses layerGroups)

- [ ] **Step 1: Write failing context check**

```python
# scripts/check_context.py
import pathlib
h = pathlib.Path("kiet_road_map.html").read_text()
for token in ["renderCampus", "kind==='building'", "kind==='pitch'", "kind==='boundary'", "kind==='label'", "bindTooltip"]:
    assert token in h, f"missing {token}"
print("OK context")
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python3 scripts/check_context.py`
Expected: FAIL with `missing renderCampus`

- [ ] **Step 3: Write minimal context implementation (append after renderRoads def)**

```javascript
function renderCampus(campus){
  const G=window.KIET.layerGroups, map=window.KIET.map;
  const pick=k=>campus.features.filter(f=>(f.properties||{}).kind===k);
  L.geoJSON(pick('building'),{style:{color:'#2c3e50',weight:1,fillColor:'#d5d8dc',fillOpacity:0.9}}).bindPopup(l=>`<b>${l.feature.properties.name||'Building'}</b>`).addTo(G.context);
  L.geoJSON(pick('pitch'),{style:{color:'#1e8449',weight:1,fillColor:'#82e0aa',fillOpacity:0.8}}).bindPopup(l=>`<b>${l.feature.properties.name||'Ground'}</b><br/>${l.feature.properties.sport||''}`).addTo(G.context);
  L.geoJSON(pick('boundary'),{style:{color:'#00f0ff',weight:6,opacity:0.9,fill:false}}).addTo(G.boundary);
  L.geoJSON(pick('boundary'),{style:{color:'#e74c3c',weight:2,opacity:0.9,fill:false}}).addTo(G.boundary);
  L.geoJSON(pick('label'),{pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:5,color:'#2c3e50',fillColor:'#f1c40f',fillOpacity:1,weight:2}).bindTooltip(f.properties.name||'',{permanent:map.getZoom()>=16,direction:'top'}).bindPopup(`<b>${f.properties.name||''}</b><br/>${f.properties.category||''}<br/><small>${f.properties.confidence||''}</small>`)}).addTo(G.labels);
  L.control.layers(null,{'Buildings+Grounds':G.context,'Boundary':G.boundary,'Labels':G.labels},{collapsed:false}).addTo(map);
  map.on('zoomend',()=>{G.labels.eachLayer(l=>{const m=l.getLayers?l.getLayers()[0]:l; if(m&&m.getTooltip) {const t=m.getTooltip(); if(t) m.unbindTooltip().bindTooltip(m.getPopup?'' :' ',{permanent:map.getZoom()>=16});}});});
}
```

Wire into fetch: after `renderRoads(roads);` add `renderCampus(campus);`

- [ ] **Step 4: Run check to verify it passes**

Run: `python3 scripts/check_context.py`
Expected: PASS `OK context`

- [ ] **Step 5: Commit**

```bash
git add kiet_road_map.html scripts/check_context.py; git commit -m "feat: add buildings, pitches, boundary, labels" || echo "commit skipped"
```

### Task 5: Validation, offline fallback, docs

**Files:**
- Modify: `/home/devdevil/development/drishti/kiet_road_map.html`
- Create: `/home/devdevil/development/drishti/README_ROADMAP.md`
- Test: `python3 scripts/validate_geojson.py && python3 scripts/check_shell.py && python3 scripts/check_roads_style.py && python3 scripts/check_context.py`

**Interfaces:**
- Consumes: all previous tasks
- Produces: final acceptance — all checks green, bundle size verified

- [ ] **Step 1: Write failing final check**

```bash
ls -lh data/*.geojson kiet_road_map.html
python3 - << 'PY'
import json, pathlib
r=json.loads(pathlib.Path("data/roads.geojson").read_text())
c=json.loads(pathlib.Path("data/campus.geojson").read_text())
assert len(r["features"])>=50, "too few roads"
assert any(f["properties"].get("kind")=="boundary" for f in c["features"]), "boundary missing"
assert any(f["properties"].get("kind")=="label" for f in c["features"]), "labels missing"
total=sum(pathlib.Path(p).stat().st_size for p in ["data/roads.geojson","data/campus.geojson","kiet_road_map.html"])
assert total < 1024*1024, f"bundle too big {total}"
print(f"OK final: roads={len(r['features'])} campus={len(c['features'])} bytes={total}")
PY
```

- [ ] **Step 2: Run to verify it fails (before fallback + README)**

Run: `cat README_ROADMAP.md`
Expected: FAIL `No such file`

- [ ] **Step 3: Add fetch fallback + README**

In `kiet_road_map.html`, wrap fetch with catch showing plain-background notice:
```javascript
// replace Promise.all(...).then with:
Promise.all([fetch('data/roads.geojson').then(r=>{if(!r.ok)throw 0;return r.json()}),fetch('data/campus.geojson').then(r=>{if(!r.ok)throw 0;return r.json()})]).then(([roads,campus])=>{window.KIET.raw={roads,campus};renderRoads(roads);renderCampus(campus);const b=L.geoJSON(campus.features.filter(f=>f.properties.kind==='boundary'));if(b.getLayers().length)map.fitBounds(b.getBounds().pad(0.15));}).catch(()=>{alert('Could not load data/*.geojson — run via python3 -m http.server');});
```

`README_ROADMAP.md`:
```markdown
# KIET Road Map
Open via `python3 -m http.server 8000` then http://localhost:8000/kiet_road_map.html
Data: `data/roads.geojson` (OSM highways), `data/campus.geojson` (buildings/pitches + screenshot boundary + 12 labels)
Rebuild: `python3 scripts/build_road_data.py`
Sources: © OpenStreetMap contributors; boundary from user screenshot red outline (approx lat/lng).
```

- [ ] **Step 4: Run all checks to verify they pass**

Run: `python3 scripts/validate_geojson.py && python3 scripts/check_shell.py && python3 scripts/check_roads_style.py && python3 scripts/check_context.py`
Expected: PASS all four `OK ...`

- [ ] **Step 5: Commit**

```bash
git add kiet_road_map.html README_ROADMAP.md docs/superpowers/plans/2026-09-04-kiet-road-map.md; git commit -m "feat: finalize KIET road map with fallback + docs" || echo "commit skipped"
```
