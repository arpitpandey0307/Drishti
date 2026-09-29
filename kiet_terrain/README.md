# KIET real terrain/elevation package

## Result

The campus extent used for clipping is the **32-vertex OpenStreetMap way 835252667** for `KIET GROUP OF INSTITUTIONS`, retrieved from the OSM API. It is the primary geographic boundary for this terrain package; the earlier hand-drawn screenshot boundary remains a separate visual reference.

**Exact boundary extent from the OSM geometry:**

- Minimum latitude: `28.7509201`
- Maximum latitude: `28.7542239`
- Minimum longitude: `77.4959414`
- Maximum longitude: `77.5010837`
- OSM-polygon centroid: `28.752790943197606, 77.49883075446867`

The clipped raster's pixel-aligned bounds are `77.49569444444445, 28.75069444444444` to `77.50125000000001, 28.754305555555554`, because the raster grid is aligned to the source DEM cells.

## Real DEM source

The DEM is **Copernicus DEM GLO-30 Public, 2021 release**, downloaded from the public AWS Open Data COG tile covering `N28 E077`. The source tile is:

`https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/Copernicus_DSM_COG_10_N28_00_E077_00_DEM/Copernicus_DSM_COG_10_N28_00_E077_00_DEM.tif`

The source is a **Digital Surface Model (DSM)**, not a bare-earth Digital Terrain Model. Its nominal grid spacing is 1 arc-second, approximately 30 m at this latitude. The horizontal CRS is `EPSG:4326`. Copernicus documentation reports absolute vertical accuracy `<4 m LE90`, relative vertical accuracy `<2 m` for slopes up to 20% and `<4 m` above 20%, and absolute horizontal accuracy `<6 m CE90`. The data uses the Copernicus product's EGM2008-related vertical reference as documented by the product handbook.

The raw source values were clipped without resampling. The clipped valid source-cell values range from approximately **214.6786 m to 231.3076 m**, with a mean of approximately **219.2223 m** over the OSM campus polygon. These are DSM elevations and can include roofs/vegetation.

Copernicus GLO-30 is the best freely downloadable global public baseline found for this Indian campus. The Copernicus 10 m EEA product is European coverage and does not cover Uttar Pradesh. A 30 m DEM is not sufficient for engineering-grade campus drainage or flood-depth prediction; use a licensed local LiDAR, photogrammetric survey, RTK survey, or total-station survey for that purpose.

## Files

- `campus_osm.geojson`: OSM campus boundary used for clipping.
- `osm_kiet_full.json`: reproducible OSM API response used to build the boundary.
- `data/terrain/raw/Copernicus_DSM_COG_10_N28_00_E077_00_DEM.tif`: raw Copernicus source tile.
- `data/terrain/clipped/kiet_copernicus_glo30_clipped.tif`: clipped real DEM; source values preserved, CRS `EPSG:4326`.
- `data/terrain/terrain_metadata.json`: machine-readable provenance and accuracy metadata.
- `data/terrain/derived/elevation_m.tif`: elevation layer derived from the clipped DEM.
- `data/terrain/derived/slope_degrees.tif`: slope in degrees derived from the DEM.
- `data/terrain/derived/aspect_degrees.tif`: aspect in degrees derived from the DEM.
- `data/terrain/derived/local_relief_m.tif`: 3×3-cell local relief, derived from the DEM.
- `data/terrain/derived/contours.geojson`: contour vectors derived from the clipped DEM.
- `data/terrain/derived/low_points.geojson`: cells in the lowest 10th percentile of valid DEM elevations; visualization candidates, not verified drainage outlets.
- `data/terrain/derived/terrain_grid.json`: lightweight sampled grid for browser queries.
- `data/terrain/derived/elevation_overlay.png`: visualization-only elevation overlay.
- `data/terrain/derived/slope_overlay.png`: visualization-only slope overlay.
- `build_kiet_terrain.py`: reproducible download, clipping, and derivation script.
- `render_terrain_assets.py`: reproducible browser visualization/contour asset script.

## Leaflet integration

Leaflet does not natively render GeoTIFF elevation rasters. For a first integration, add the derived contour/low-point vectors and the PNG overlays using the raster bounds in `data/terrain/derived/overlay_metadata.json`. For click queries, load `terrain_grid.json`, find the nearest sampled cell to the clicked coordinate, and display its source-cell elevation. Do not label interpolated values as measured values.

Example layer setup:

```js
const terrainBounds = [[28.75069444444444, 77.49569444444445],
                       [28.754305555555554, 77.50125000000001]];
const elevation = L.imageOverlay('/data/terrain/derived/elevation_overlay.png', terrainBounds,
  {opacity: 0.55, interactive: false});
const slope = L.imageOverlay('/data/terrain/derived/slope_overlay.png', terrainBounds,
  {opacity: 0.55, interactive: false});
const contours = L.geoJSON(await fetch('/data/terrain/derived/contours.geojson').then(r => r.json()),
  {style: {color: '#7b2cbf', weight: 1}});
const lowPoints = L.geoJSON(await fetch('/data/terrain/derived/low_points.geojson').then(r => r.json()),
  {pointToLayer: (_, latlng) => L.circleMarker(latlng, {radius: 3, color: '#0057b8'})});
L.control.layers({OpenStreetMap: osm}, {
  'Terrain / elevation': elevation,
  'Terrain / slope': slope,
  'Terrain / contours': contours,
  'Terrain / low points': lowPoints
}).addTo(map);
```

For production, serve the COG through a tile/terrain service or use a browser GeoTIFF library. Do not upscale the 30 m raster and claim 1 m terrain.

## Attribution

`© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.`

OSM data is © OpenStreetMap contributors and is available under the Open Database License (ODbL). Provide OSM attribution in the Leaflet map.
