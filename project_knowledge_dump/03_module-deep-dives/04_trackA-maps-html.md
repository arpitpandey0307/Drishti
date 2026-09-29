# 03.04 — Track A HTML apps + landing + deploy

## index.html:1-29 (landing, dark #0e1626)

h1 Drishti + sub KIET campus roads/buildings/terrain (`:18-19`). 6 cards (`:20-25`): 1) `kiet_3d_standalone.html` 3D offline; 2) `kiet_terrain_map.html` 2D terrain+road; 3) `kiet_road_map.html` 2D road; 4) `flood_planner.html` planner; 5) HF Space live model (external); 6) `flood_viewer.html?bank=demo&env=csv` sim env. Footer 30 m DSM ±4 m (`:26`). History: §11 root-404 cure → §§19–23 added cards 4–6.

## kiet_road_map.html:1-70 (4.9 KB, Leaflet 1.9.4, earliest)

Centre [28.75257,77.49851] z16 (`:16`); OSM + Esri satellite (`:19-22`); LayerGroups main/internal/foot/context/boundary/labels/accL (`:23`); `renderAccurate :24-31` circleMarkers (#0e6655/#f9e79f) tooltip real(sanctioned); `styleRoad :32-40` trunk #7e5109 w8 / tertiary #7d6608 w6 / residential grey w3 / service #2c3e50 w7 / foot dashed #7fb3d5; `styleRoadTop :41-48` orange/yellow/light/white; `renderRoads :50-63` dual-pass casing+top, popup name/highway/ref; `renderCampus :64-66` stub empty; fetch roads+campus+accurate, fitBounds khasra pad 0.15 (`:67`). Notice Rev6 + OSM approx 3–5 m (`:12`).

## kiet_terrain_map.html:1-111 (7.1 KB)

Same road stack (`:15-58`) + terrain group (`:23`). `renderTerrain :67-88`: bounds B=[[28.75069444,77.49569444],[28.75430555,77.50125]] (`:69`); hillshade 0.55 on + slope 0.5 off; smooth 2 m contours purple #7b2cbf on; low pockets blue on; click-query nearest 30 m within ~0.0003° (~25 m) popup ~X m ±4 m (`:76-87`); combined layers + legend (`:89-100`); fetch +contours+low+grid (`:102`).

## kiet_3d_terrain.html:1-203 (13 KB, Three.js 0.160 importmap :21) vs kiet_3d_standalone.html (279 KB)

Payload `data/terrain_3d.json` 160×104 mesh 16,640 nodes + mask; 45 roads draped; 31 buildings (12 m default, 18 m Saraswati/hostels, footprint-scaled kiosk fix); 25 contours; 12 labels + 10 low spheres; exaggeration 1–6×; sun+orbit+click query. Standalone embeds payload via `build_standalone_3d.py` (file:// CORS fix, md5-identical, `report.md:127-137`). Fixes: tower heights (`:139-147`), stick lines via valid-mask clip (`:149-156`).

## flood_planner.html (16.5 KB, NEW end-user product, report §22)

Leaflet OSM+campus+roads; baked `planner/storms/` stacks as heat overlay NOW→+180 slider; tap → water-now/at-horizon/peak/onset + CLEAR(<0.05)/WATCH(<0.15)/WARNING(<0.30)/DANGER badge (`:88,90`); nearest road label; origin/destination → normal (grey dashed) vs flood-aware (green, 10× penalty, ≥0.30 hard-avoid) Dijkstra+A* (`:149-166`); `?storm=&h=&selftest=`; synthetic labels. Verified zero console errors; selftest 64 cm/DANGER + 5.30 km dual routes. Endpoints = largest road-graph component.

## flood_viewer.html (38 KB, zero-dep canvas 2D, report §§14–15,23–24)

10 v0 + 2 v1 scenarios; play/pause/reset/speed/scrub (Space+arrows); 6 toggles terrain/rain/water/velocity/drainage/surcharge; click inspector cells (elev/rain/depth/vel/flooded/ttf) nodes (level/in/out/cap/surcharge/prov) pipes (len/D/flow/cap/util/blk/status); live metrics + causal chain; legend 0/1/5/10/20/50+ cm; synthetic banner. QC restyle (Manrope/Playfair/DM Mono, glass 18 px blur, directory+inspector+transport). `?bank=demo` prod switch (3 fetch sites). Headfull proof: play k0→4, cell [64,80], CSVs 17 rows ALL PASSED (report §24).

## planner/ vs viewer/ vs Space (why 3 apps — [INFERRED])

Planner = end-user decisions (tap + routes, baked model, works offline-ish on Vercel). Viewer = engineer truth (full physics, inspector, surcharge, needs http.server + H5 bundles). Space = live ML proof (browser ONNX, storm/lead/route, HF static). Different data (baked bins vs viz bundles vs w*.bin), different users, different hosts — kept separate deliberately.

## vercel.json / render.yaml / .gitignore / .vercelignore

`vercel.json` static cleanUrls false; `render.yaml` static publish `.` (empty buildCommand dropped); `.vercelignore` + `.gitignore:16-36` keep 40 MB tif, *.h5/*.pt/*.onnx(.data), space bins, kiet_terrain/data, legacy dirs, caches out; `!outputs/viz-demo` exception ships 5.3 MB demo bank.
