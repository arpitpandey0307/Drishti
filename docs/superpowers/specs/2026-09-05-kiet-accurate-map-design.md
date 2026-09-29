# KIET Accurate Map – Design (2026-09-05)

Goal: most accurate KIET campus map from sanctioned `kiet_campuse_data/` (16 photos → info.md) + Google Maps lat/long verification. Upgrade existing Leaflet maps, full polygons, no Google API key.

## 1. Architecture & sources

- Keep stack: `kiet_road_map.html` (2D roads), `kiet_terrain_map.html` (2D terrain), `kiet_3d_standalone.html` (3D), `index.html` landing. No framework change, Leaflet 1.9.4 CDN + offline GeoJSON.
- New data:
  - `data/campus_accurate.geojson` – WGS84, kinds: `sanctioned_building`, `road_sanctioned`, `parking`, `solar`, `boundary_khasra`, `label_accurate`. Each feature: `sanctioned_name` (A,B,C,C1,D,E,F,S,J,J1,L,U,V,X,Y,Z,Pharmacy,Canteen,Auditorium), `floors` (e.g. G+5), `footprint_sqm`, `far_share`, `solar_kw` where pink, `confidence` (high/med), `source` (e.g. 14.jpeg + dims).
  - `data/blocks_centroids.csv` – name, lat, lon (5 decimals), floors, area, source image.
- Anchors (WGS84):
  - OSM/Mapcarta 28.75257, 77.49851 (way 835252667, high confidence)
  - Google/FindLatLon 28.752441, 77.49902 (KIET gate area)
  - DigiPin 28.753007, 77.498594
  - Campusogram: NH-58 45M ROW centreline, Railway Lane north edge.
- Sanctioned truths (from `kiet_campuse_data/info.md`, Rev 6 16/10/2024, 1:400, Er. Atul Goel, Krishna Charitable Society):
  Net 68,331.72, coverage 20,801.07 (perm 23,916.10), FAR 87,715.00 (perm 1,36,663.44), parking 20,232.12 (req 20,190.00), demolition C-1 184.78, covered 9-11m setback 760.73, GDA fee 2,74,27,180.
- Control points for affine: NW Railway/9M setback triangle, NE C-workshop 41.76m edge + 337.48/142.70, E NH-58 frontage 115.79 x 120.83 + A-Block 45.00x45.70, C E-Block 40.23, S A-Block south 42.67/35.74, W J-Girls 40.17/38.12. Minimum 4, target 6.
- Basemap: OSM default + Esri World Imagery free satellite `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` for verification toggle. Google used manually via google.com/maps (no tiles/key).

## 2. Components & data flow

- `scripts/build_accurate_geojson.py` (stdlib only): paper meters from sanctioned dims → local ENU (east=x, north=y, origin at A-Block SE corner) → affine to WGS84 via least-squares on controls → emit polygons. No new deps.
- Blocks: rectangles from dims where given (A 45.00x45.70, C-1 41.76 long, E 40.23, Z 26.80 etc.), star D-Lecture as 3-blade polygon (approx from 14.jpeg), others proportioned from site-plan ratios, all closed CCW.
- Roads: centreline offsets from plan (6.00M grid, 7.50M spine, 3.00M service, NH-58 45M, Railway Lane), width attr.
- Parking A-R with areas (O 7820.55 largest south, M 2748.70, L 1915.03, A 1753.14 front), solar belts with KW (33,44-8,100,15,80,49,20,60,40,93-72).
- Khasra boundary: KIET hatch 280,281,282,284 + 277,278,279 partials + 286/286C strip, surrounding 260-296 as context (low confidence).
- Map upgrades: load `campus_accurate.geojson` as toggle layers (`Sanctioned blocks`, `Sanctioned roads`, `Parking/Solar`, `Khasra`) alongside OSM `campus.geojson`/`roads.geojson`; popups show name, floors, footprint, lat/long centroid, source image + dims; labels permanent tooltips with lat/long; 3D extrudes height = (G+n)*3.3m (shed 4m).
- Dev-only: perspective-corrected stitch of 14 (NE) + 6 (N) + 11 (E) + 13 (S) as `ImageOverlay` for alignment check, not shipped.

## 3. Accuracy, errors, testing, scope

- Target 3-5m absolute (photo distortion + 30m Copernicus DEM ±4m). Not survey-grade. Keep existing disclaimer + `confidence` per feature.
- Risks: photo perspective (mitigate via dims, not pixel tracing), creases/fingers occlusion (use sharpest of duplicates: 11E,14NE,6N,3T,1tables,13khasra), Key Plan north vs site north confusion (use site arrow 1/7), Hindi approval partial (display only verified fee/dates).
- Tests: GeoJSON valid, all rings closed, area sums match sanctioned ±1% (coverage, parking, FAR), visual vs Esri + google.com/maps satellite (hostels N, A-Block SE, star D central-E, sports NW), `fitBounds` to khasra, popups show 5-decimal lat/long, old maps still load offline.
- Out of scope: Google API tiles/geocoding, indoor plans, live GPS, rescan, terrain resurvey.

Approved: upgrade-existing + full-polygons + verify-no-key + rubber-sheet A.
