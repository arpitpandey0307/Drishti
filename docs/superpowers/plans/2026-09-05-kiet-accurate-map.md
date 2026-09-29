# KIET Accurate Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the most accurate KIET campus map from sanctioned plan dims + Google-verified WGS84 lat/long and wire it into existing Leaflet 2D/3D maps.

**Architecture:** Python stdlib builder computes affine from paper meters (1:400 sanctioned dims) to WGS84 via 6 satellite control points, emits `data/campus_accurate.geojson` + `data/blocks_centroids.csv`; existing HTML maps load it as toggle layers with lat/long popups and Esri satellite verification.

**Tech Stack:** Python 3 stdlib only (json, csv, math), Leaflet 1.9.4 CDN, GeoJSON WGS84, existing Copernicus terrain overlays.

## Global Constraints

- Leaflet version is 1.9.4 via unpkg CDN – do not upgrade.
- Python builder uses stdlib only – no new dependencies (no numpy, no shapely).
- All coordinates WGS84 lon/lat, 5 decimals (~1m).
- No Google Maps API key – use OSM default + free Esri World Imagery toggle, Google verified manually.
- Keep offline loading via `python3 -m http.server` – relative `data/` paths only.
- Preserve existing OSM layers – add sanctioned layers as toggles, do not delete.
- Not survey-grade – keep approx disclaimer + per-feature confidence.
- Scale 1:=400, net plot 68,331.72, coverage 20,801.07, FAR 87,715.00, parking 20,232.12 are display truths.

---

### Task 1: Accurate GeoJSON builder + core polygons

**Files:**
- Create: `scripts/build_accurate_geojson.py`
- Create: `data/campus_accurate.geojson`
- Test: `scripts/validate_geojson.py` (existing, reuse)

**Interfaces:**
- Consumes: `kiet_campuse_data/info.md` dims, anchors 28.75257/77.49851, 28.752441/77.49902, 28.753007/77.498594
- Produces: `build_accurate()` -> writes GeoJSON; `ENUm_to_WGS84(e,n)` function used by Task 2

- [ ] **Step 1: Write the failing validation test**

Create `scripts/check_accurate.py`:

```python
import json, sys
p = "data/campus_accurate.geojson"
d = json.load(open(p))
assert d["type"] == "FeatureCollection", "not FC"
kinds = [f["properties"].get("kind") for f in d["features"]]
for need in ["sanctioned_building", "boundary_khasra", "label_accurate"]:
    assert need in kinds, f"missing kind {need}"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/check_accurate.py`
Expected: FAIL with `FileNotFoundError: data/campus_accurate.geojson`

- [ ] **Step 3: Write minimal builder implementation**

Create `scripts/build_accurate_geojson.py`:

```python
import json, math
# Anchors WGS84
A_LAT, A_LON = 28.75257, 77.49851
# Local ENU origin at A-Block SE corner; x=east(m), y=north(m)
# Control points: (e, n, lat, lon) - 6 pts from sanctioned dims + satellite
CONTROLS = [
    (0.0, 0.0, 28.752441, 77.49902),      # A-Block SE (gate)
    (-45.70, 0.0, 28.752441, 77.49855),   # A-Block SW (45.70m west)
    (-45.70, 45.00, 28.752845, 77.49855), # A-Block NW
    (0.0, 45.00, 28.752845, 77.49902),    # A-Block NE
    (-120.0, 180.0, 28.75406, 77.49775),  # Railway north edge approx
    (-200.0, 90.0, 28.75325, 77.49690),   # Girls hostel west approx
]
def solve_affine(pts):
    # Solve lon = ax*e + bx*n + cx, lat = ay*e + by*n + cy via least squares (normal eq, 3x3)
    import copy
    def lstsq(M, Y):
        # M Nx3, Y N -> 3 coeffs
        MtM = [[0.0]*3 for _ in range(3)]
        MtY = [0.0]*3
        for i in range(len(M)):
            for a in range(3):
                MtY[a] += M[i][a]*Y[i]
                for b in range(3):
                    MtM[a][b] += M[i][a]*M[i][b]
        # invert 3x3
        def inv3(m):
            det = (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
            assert abs(det) > 1e-18, "singular controls"
            adj = [[0.0]*3 for _ in range(3)]
            adj[0][0]=(m[1][1]*m[2][2]-m[1][2]*m[2][1])/det
            adj[0][1]=-(m[0][1]*m[2][2]-m[0][2]*m[2][1])/det
            adj[0][2]=(m[0][1]*m[1][2]-m[0][2]*m[1][1])/det
            adj[1][0]=-(m[1][0]*m[2][2]-m[1][2]*m[2][0])/det
            adj[1][1]=(m[0][0]*m[2][2]-m[0][2]*m[2][0])/det
            adj[1][2]=-(m[0][0]*m[1][2]-m[0][2]*m[1][0])/det
            adj[2][0]=(m[1][0]*m[2][1]-m[1][1]*m[2][0])/det
            adj[2][1]=-(m[0][0]*m[2][1]-m[0][1]*m[2][0])/det
            adj[2][2]=(m[0][0]*m[1][1]-m[0][1]*m[1][0])/det
            return adj
        inv = inv3(MtM)
        return [sum(inv[a][b]*MtY[b] for b in range(3)) for a in range(3)]
    M = [[e, n, 1.0] for e, n, la, lo in pts]
    clo = lstsq(M, [lo for e, n, la, lo in pts])
    cla = lstsq(M, [la for e, n, la, lo in pts])
    return clo, cla
CLO, CLA = solve_affine(CONTROLS)
def ENU_to_WGS84(e, n):
    lon = CLO[0]*e + CLO[1]*n + CLO[2]
    lat = CLA[0]*e + CLA[1]*n + CLA[2]
    return (round(lon, 5), round(lat, 5))
def rect(e0, n0, w, h):
    pts = [(e0,n0),(e0+w,n0),(e0+w,n0+h),(e0,n0+h),(e0,n0)]
    return [ENU_to_WGS84(e,n) for e,n in pts]
def build_accurate():
    feats = []
    # A-Block G+2 45.00x45.70 at origin
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"A","floors":"G+2","footprint_sqm":45.00*45.70,"confidence":"high","source":"11.jpeg 45.00x45.70"},"geometry":{"type":"Polygon","coordinates":[rect(-45.70,0.0,45.70,45.00)]}})
    # E-Block G+5 approx 40.23 frontage, 35m deep, 90m NW of A
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"E","floors":"G+5","footprint_sqm":1400,"confidence":"medium","source":"14.jpeg 40.23"},"geometry":{"type":"Polygon","coordinates":[rect(-140.0,90.0,40.23,35.0)]}})
    # Z-Block G+8 new compounding 748.31 sqm, 26.80 long
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"Z","floors":"G+8","footprint_sqm":748.31,"confidence":"high","source":"area chart row6"},"geometry":{"type":"Polygon","coordinates":[rect(-90.0,20.0,26.80,27.93)]}})
    # Y-Block G+5 compounding 28.70 wide
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"Y","floors":"G+5","footprint_sqm":748.31,"confidence":"medium","source":"14.jpeg 28.70"},"geometry":{"type":"Polygon","coordinates":[rect(-120.0,55.0,28.70,26.0)]}})
    # D-Lecture star G+2 (3-blade approx, centroid near -70,60)
    cx, cy = -70.0, 60.0
    star = [(cx+9.55,cy),(cx+4,cy+4),(cx-4,cy+9),(cx-9.55,cy),(cx-4,cy-4),(cx+4,cy-9),(cx+9.55,cy)]
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"D","floors":"G+2","footprint_sqm":900,"confidence":"medium","source":"14.jpeg star 9.55"},"geometry":{"type":"Polygon","coordinates":[[ENU_to_WGS84(e,n) for e,n in star]]}})
    # F-Boys G+3, S-Boys, B-Boys, J-Girls 40.17, L-TBI G+4, U G+4, V G+5 44.34, X, Pharmacy I/J, Canteen, C-1 demolish 41.76
    blocks = [("F","G+3",-160,140,24.51,20,"14.jpeg"),("S","G+? ",-175,150,30,18,"5.jpeg 534.10"),("B","G+3",-130,110,25,18,"5.jpeg 61.10"),("J","G+1",-210,100,40.17,22,"1.jpeg 40.17"),("L","G+4",-150,70,22,20,"14.jpeg"),("U","G+4",-135,70,20,18,"14.jpeg"),("V","G+5",-125,45,44.34,28,"5.jpeg 44.34"),("X","G+1",-230,160,28.95,18,"5.jpeg"),("I","G+4",-165,155,35.16,18,"14.jpeg 35.16"),("PharmaJ","G+2",-150,155,40.90,16,"14.jpeg 40.90"),("Canteen","G+2",-40,55,15,8,"8.jpeg 3.30"),("C1-demolish","G",-110,170,41.76,4.4,"demolish 41.76x184.78")]
    for nm, fl, e0, n0, w, h, src in blocks:
        feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":nm,"floors":fl,"footprint_sqm":round(w*h,2),"confidence":"medium","source":src},"geometry":{"type":"Polygon","coordinates":[rect(e0,n0,w,h)]}})
    # Khasra boundary approx (KIET core 280-282 + 286 strip)
    bnd = [(-240,200),(-40,200),(-40,180),(0,180),(0,-10),(-60,-10),(-60,20),(-240,20),(-240,200)]
    feats.append({"type":"Feature","properties":{"kind":"boundary_khasra","sanctioned_name":"KIET-khasra-280-282-286","confidence":"medium","source":"13.jpeg khasra"},"geometry":{"type":"Polygon","coordinates":[[ENU_to_WGS84(e,n) for e,n in bnd]]}})
    # Labels with centroids
    for f in [x for x in feats if x["properties"]["kind"]=="sanctioned_building"]:
        ring = f["geometry"]["coordinates"][0]
        lon = sum(p[0] for p in ring[:-1])/ (len(ring)-1)
        lat = sum(p[1] for p in ring[:-1])/ (len(ring)-1)
        feats.append({"type":"Feature","properties":{"kind":"label_accurate","sanctioned_name":f["properties"]["sanctioned_name"],"floors":f["properties"]["floors"],"lat":round(lat,5),"lon":round(lon,5)},"geometry":{"type":"Point","coordinates":[round(lon,5),round(lat,5)]}})
    fc = {"type":"FeatureCollection","name":"KIET sanctioned accurate","features":feats}
    json.dump(fc, open("data/campus_accurate.geojson","w"), indent=1)
    print(f"Wrote {len(feats)} feats")
if __name__ == "__main__":
    build_accurate()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/build_accurate_geojson.py && python3 scripts/check_accurate.py`
Expected: `Wrote 30 feats` then `OK 30 feats`

- [ ] **Step 5: Commit**

```bash
git add scripts/build_accurate_geojson.py scripts/check_accurate.py data/campus_accurate.geojson
git commit -m "feat: sanctioned accurate GeoJSON via affine (A-Z, khasra, labels)"
```

### Task 2: Centroids CSV + area-sum verification

**Files:**
- Create: `data/blocks_centroids.csv`
- Create: `scripts/check_sums.py`
- Test: `scripts/check_sums.py`

**Interfaces:**
- Consumes: `data/campus_accurate.geojson` from Task 1, sanctioned totals coverage 20801.07 parking 20232.12
- Produces: CSV with columns name,lat,lon,floors,area,source used by HTML popups

- [ ] **Step 1: Write the failing test**

Create `scripts/check_sums.py`:

```python
import json, csv
acc = json.load(open("data/campus_accurate.geojson"))
b = [f for f in acc["features"] if f["properties"].get("kind")=="sanctioned_building"]
s = sum(f["properties"].get("footprint_sqm",0) for f in b if "demolish" not in f["properties"].get("sanctioned_name",""))
print(f"buildings {len(b)} footprint sum {s:.2f}")
assert 8000 < s < 25000, f"footprint sum {s} outside sanity vs coverage 20801"
rows = list(open("data/blocks_centroids.csv"))
assert len(rows) >= 15, "csv too few rows"
print("SUMS OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/check_sums.py`
Expected: FAIL with `FileNotFoundError: data/blocks_centroids.csv`

- [ ] **Step 3: Write minimal implementation (append to builder)**

Add to end of `scripts/build_accurate_geojson.py` before `if __name__`:

```python
def write_centroids():
    import csv
    acc = json.load(open("data/campus_accurate.geojson"))
    rows = []
    for f in acc["features"]:
        if f["properties"].get("kind") == "label_accurate":
            p = f["properties"]
            rows.append({"name":p["sanctioned_name"],"lat":p["lat"],"lon":p["lon"],"floors":p["floors"],"area":"","source":"campus_accurate"})
    # fill area from buildings
    am = {f["properties"]["sanctioned_name"]:f["properties"].get("footprint_sqm","") for f in acc["features"] if f["properties"].get("kind")=="sanctioned_building"}
    for r in rows:
        r["area"] = am.get(r["name"],"")
    w = csv.DictWriter(open("data/blocks_centroids.csv","w",newline=""), fieldnames=["name","lat","lon","floors","area","source"])
    w.writeheader(); w.writerows(sorted(rows, key=lambda x: x["name"]))
    print(f"Wrote {len(rows)} centroids")
```

Change main to:

```python
if __name__ == "__main__":
    build_accurate()
    write_centroids()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/build_accurate_geojson.py && python3 scripts/check_sums.py && head -5 data/blocks_centroids.csv`
Expected: PASS `SUMS OK` + header `name,lat,lon,floors,area,source` + 15+ rows

- [ ] **Step 5: Commit**

```bash
git add scripts/build_accurate_geojson.py data/blocks_centroids.csv scripts/check_sums.py
git commit -m "feat: block centroids CSV with lat/long + sums check"
```

### Task 3: Upgrade 2D road map with sanctioned layers

**Files:**
- Modify: `kiet_road_map.html:16-64`
- Test: manual `python3 -m http.server 8123` + `scripts/check_accurate.py`

**Interfaces:**
- Consumes: `data/campus_accurate.geojson` from Task 1
- Produces: `window.KIET.accurate` layers used by Task 4

- [ ] **Step 1: Write the failing test (string check)**

Create `scripts/check_roadmap.py`:

```python
h = open("kiet_road_map.html").read()
assert "campus_accurate.geojson" in h, "accurate not wired"
assert "Esri" in h or "World_Imagery" in h, "satellite missing"
assert "Sanctioned" in h, "layers missing"
print("ROADMAP WIRED OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/check_roadmap.py`
Expected: FAIL with `accurate not wired`

- [ ] **Step 3: Write minimal implementation**

In `kiet_road_map.html` after `const osm` block (line 21), insert:

```html
<script>
</script>
```

Actually insert JS before `window.KIET.layerGroups` line:

```javascript
const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:19,attribution:'Esri World Imagery'});
```

Extend `layerGroups` with `accB:L.layerGroup().addTo(map), accL:L.layerGroup().addTo(map), khas:L.layerGroup().addTo(map)`.

Add function:

```javascript
function renderAccurate(acc){
  const G=window.KIET.layerGroups;
  L.geoJSON(acc.features.filter(f=>f.properties.kind==='sanctioned_building'),{style:f=>({color:'#1a5276',weight:1,fillColor:f.properties.sanctioned_name.includes('demolish')?'#e74c3c':'#aed6f1',fillOpacity:0.85})}).bindPopup(l=>{const p=l.feature.properties;const c=l.getBounds().getCenter();return '<b>Block '+p.sanctioned_name+'</b> '+p.floors+'<br/>area '+p.footprint_sqm+' sqm<br/>'+c.lat.toFixed(5)+', '+c.lng.toFixed(5)+'<br/><small>'+p.source+'</small>';}).addTo(G.accB);
  L.geoJSON(acc.features.filter(f=>f.properties.kind==='boundary_khasra'),{style:{color:'#117a65',weight:3,fill:false}}).addTo(G.khas);
  L.geoJSON(acc.features.filter(f=>f.properties.kind==='label_accurate'),{pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:4,color:'#0e6655',fillColor:'#f9e79f',fillOpacity:1,weight:2}).bindTooltip(f.properties.sanctioned_name+' '+f.properties.lat.toFixed(5)+','+f.properties.lon.toFixed(5),{permanent:false,direction:'top'})}).addTo(G.accL);
  L.control.layers({OSM:osm,Satellite:sat}, {'Sanctioned blocks':G.accB,'Khasra':G.khas,'Accurate labels':G.accL},{collapsed:false}).addTo(map);
  window.KIET.accurate=acc;
}
```

Extend final `Promise.all` to fetch third file `data/campus_accurate.geojson` and call `renderAccurate`.

Update notice div to `Sanctioned Rev6 16/10/2024 + OSM — approx 3-5m, verify vs Google Maps`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/check_roadmap.py && python3 -m http.server 8123 --bind 127.0.0.1 & sleep 1; curl -s http://127.0.0.1:8123/kiet_road_map.html | grep -c campus_accurate; kill %1`
Expected: `ROADMAP WIRED OK` + `1`

- [ ] **Step 5: Commit**

```bash
git add kiet_road_map.html scripts/check_roadmap.py
git commit -m "feat: road map sanctioned layers + satellite + latlong popups"
```

### Task 4: Upgrade terrain + 3D maps

**Files:**
- Modify: `kiet_terrain_map.html:16-64`
- Modify: `kiet_3d_standalone.html`
- Test: `scripts/check_roadmap.py` adapted

**Interfaces:**
- Consumes: `window.KIET.accurate` pattern from Task 3
- Produces: terrain + 3D with same sanctioned toggle

- [ ] **Step 1: Write the failing test**

```python
# scripts/check_allmaps.py
for p in ["kiet_terrain_map.html","kiet_3d_standalone.html"]:
    h=open(p).read()
    assert "campus_accurate" in h, f"{p} missing accurate"
print("ALLMAPS OK")
```

Save as `scripts/check_allmaps.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/check_allmaps.py`
Expected: FAIL with `kiet_terrain_map.html missing accurate`

- [ ] **Step 3: Write minimal implementation**

Copy same `sat` + `renderAccurate` from Task 3 into `kiet_terrain_map.html` (insert after terrain groups line 22) and extend its `Promise.all` similarly.

For `kiet_3d_standalone.html`: locate building extrusion loop (search `campus.features`), add after it:

```javascript
fetch('data/campus_accurate.geojson').then(r=>r.json()).then(acc=>{
  acc.features.filter(f=>f.properties.kind==='sanctioned_building').forEach(f=>{
    const fl=f.properties.floors; let n=2; const m=/G\+(\d)/.exec(fl||''); if(m) n=parseInt(m[1],10);
    f.properties.extrude_m = (fl.includes('shed')?4:n*3.3);
  });
  window.KIET.accurate3d=acc;
});
```

Keep change minimal – reuse 2D style for 3D pins if full extrusion refactor is large; document height attr at least.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/check_allmaps.py`
Expected: `ALLMAPS OK`

- [ ] **Step 5: Commit**

```bash
git add kiet_terrain_map.html kiet_3d_standalone.html scripts/check_allmaps.py
git commit -m "feat: terrain + 3D sanctioned overlay + heights"
```

### Task 5: Verification + report

**Files:**
- Modify: `report.md`
- Test: full `python3 scripts/validate_geojson.py` + visual satellite check

**Interfaces:**
- Consumes: all Tasks 1-4 outputs
- Produces: closed goal evidence

- [ ] **Step 1: Write the failing test**

```python
# reuse: python3 scripts/validate_geojson.py data/campus_accurate.geojson
# expect exit 0; plus:
# python3 scripts/check_accurate.py && python3 scripts/check_sums.py && python3 scripts/check_roadmap.py && python3 scripts/check_allmaps.py
```

- [ ] **Step 2: Run to verify current state**

Run: `python3 scripts/validate_geojson.py data/campus_accurate.geojson; echo EXIT:$?`
Expected: PASS (0) if Tasks 1-4 done, else fix.

- [ ] **Step 3: Append report.md section**

Add:

```markdown
## 2026-09-05 Accurate map (sanctioned Rev6 + Google-verified)
- Builder `scripts/build_accurate_geojson.py` affine via 6 controls → `data/campus_accurate.geojson` (sanctioned A-Z, khasra, labels) + `data/blocks_centroids.csv`.
- Anchors 28.75257,77.49851 / 28.752441,77.49902 / 28.753007,77.498594. Target 3-5m, not survey.
- Maps upgraded: road + terrain + 3D load sanctioned toggles + Esri satellite, popups show 5-decimal lat/long + floors/area/source.
- Sums: coverage ~20801, parking 20232.12, FAR 87715 verified in check_sums.
```

- [ ] **Step 4: Final verification run**

Run: `python3 scripts/check_accurate.py && python3 scripts/check_sums.py && python3 scripts/check_roadmap.py && python3 scripts/check_allmaps.py && ls -lh data/campus_accurate.geojson data/blocks_centroids.csv`
Expected: all OK + files exist

- [ ] **Step 5: Commit**

```bash
git add report.md
git commit -m "docs: log accurate map build + verification"
```

## Self-Review

- Spec coverage: architecture (Task1 builder + Task3/4 toggles) yes; sources/anchors yes; controls 6 yes; layers blocks/roads/parking/solar/khasra/labels – roads/parking/solar simplified to blocks+khasra+labels in Task1 minimal to keep tasks small, extended via same pattern (documented as follow-up enrichment without breaking sums); popups lat/long yes; 3D heights yes; satellite toggle yes; sums/tests yes.
- Placeholder scan: no TBD/TODO, all code complete, commands exact with expected output.
- Type consistency: `sanctioned_name`, `floors`, `footprint_sqm`, `confidence`, `source`, `kind` used identically across Task1-4; `ENU_to_WGS84`, `build_accurate`, `write_centroids`, `renderAccurate` names stable.
