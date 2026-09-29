# KIET Campus Road-Focused 2D Map — Design Spec
Date: 2026-09-04
Status: Approved by user (Interactive HTML + Internal+surroundings + Blocks+grounds)

## 1. Goal
Build an interactive 2D road-focused map of KIET Group of Institutions (28.75257, 77.49851) from real OSM geometry + the existing `kiet_campus_map/` reconstruction package. Roads are the visual hero; buildings/grounds are context.

## 2. Context / Inputs
- Existing: `kiet_campus_map/boundary.geojson` (red-outline polygon, approx lat/lng), `visible_features.geojson` (12 labels with image_pixel + lat/lng), `manifest.json`, QA overlay PNG.
- OSM verification: Overpass bbox 28.7480,77.4920,28.7585,77.5050 returns 199 `highway=*` ways (trunk NH-34, tertiary, residential 142, service 20 incl. `access=private` campus roads, footway 26) and 44 building/amenity/leisure ways (Auditorium, Saraswati dormitory, staff quarters, cricket/soccer/volleyball/basketball pitches, college polygon way 835252667).
- Coordinate system: WGS84 lat/lng throughout. No reprojection. Pixel geometry from screenshot is reference only.

## 3. Architecture
Single-folder offline-capable bundle, no build step:
```
kiet_road_map.html      # Leaflet map, layer toggles, legend, popups
data/roads.geojson      # filtered OSM highways (LineString, props: name, highway, service, access, ref)
data/campus.geojson     # buildings + pitches + boundary overlay + label points
docs/superpowers/specs/2026-09-04-kiet-road-map-design.md  # this file
```
`kiet_road_map.html` loads Leaflet 1.9.x via CDN with fallback: if tiles/CDN blocked, renders vectors on plain light background via L.CRS.Earth canvas. OSM tile layer optional (default ON with attribution).

## 4. Components
- **RoadLayer (hero):** style by hierarchy:
  - trunk (NH-34 Meerut Rd): #e67e22, 6px, casing #7e5109
  - tertiary/unclassified: #f1c40f, 4px, casing #7d6608
  - residential: #bdc3c7, 3px
  - service (campus private): #ffffff, 4px, casing #2c3e50 7px — pops on both light/dark
  - footway/steps: dashed #7fb3d5, 2px, dashArray 6 4
  - tunnel/building_passage: reduced opacity 0.6 + dashed casing
- **ContextLayer:** buildings (#d5d8dc fill, #2c3e50 stroke), pitches green (#82e0aa), college polygon faint, KIET red-boundary glow (cyan #00f0ff casing + red core to match QA overlay).
- **LabelLayer:** 12 points from `visible_features.geojson` + OSM names (Auditorium, Saraswati, etc.), permanent tooltips at z>=16, popups with category + source + confidence.
- **UI:** layer control (Main roads / Internal service / Footpaths / Buildings+Grounds / Boundary / Labels), legend bottom-right, fitBounds to boundary on load, scale control, OSM + screenshot-source attribution.

## 5. Data Flow
1. Fetch Overpass (highways + buildings/leisure/amenity) for bbox above.
2. Convert OSM `geometry` (lat/lon arrays) to GeoJSON LineString/Polygon, keep tags: name, highway, building, leisure, sport, access, service, tunnel, ref.
3. Merge: boundary polygon from `boundary.geojson` tagged `source=user screenshot red outline`; label points from `visible_features.geojson`.
4. Save to `data/*.geojson`. HTML fetches locally via fetch() — works via file:// + http server.
5. No backend, no routing graph yet (future: build routable graph from service+footway for Drishti nav).

## 6. Error Handling
- CDN/tiles blocked → catch tileerror, show plain #f8f9fa background + notice; vectors still render.
- fetch(file://) CORS → inline fallback: embed small campus core directly + try fetch, catch and use embedded.
- OSM fetch fails at build time → reuse last bundled GeoJSON, log warning in console.
- Approximate lat/lng disclaimer in corner + README: not for surveying/emergency use.

## 7. Testing / Acceptance
- Open `kiet_road_map.html` (double-click + `python3 -m http.server`): no console errors.
- Roads visible at z15-18, internal service white-with-casing distinguishable, footways dashed.
- Toggles hide/show each class; popups show name; legend matches styles; fitBounds shows full boundary + NH-34.
- Mobile 390px width: controls collapsible, legend compact.
- Files < 1MB total (simplify OSM geom to 6 decimals).

## 8. Non-Goals (YAGNI)
No routing/search/backend, no hand-traced schematic, no satellite tile scraping, no surveying-grade georeferencing. OSM © OpenStreetMap contributors attribution required.

## 9. Future (out of scope)
Routable graph (service+footway), gate/entry markers, block A-H indoor mapping, Drishti navigation integration.
