# KIET Campus Map Reconstruction

This package reconstructs the campus area marked in the supplied 1920×1080 Google Maps screenshot. It is intended as an editable starting point for a custom map, GIS layer, or game/map conversion pipeline.

## Files

| File | Purpose |
|---|---|
| `boundary_points.json` | Full simplified boundary vertices in source-image pixels, normalized coordinates, and approximate latitude/longitude. |
| `boundary_points.csv` | Same boundary vertices in tabular form. |
| `boundary.geojson` | Approximate campus boundary as a GeoJSON polygon. Import into QGIS, ArcGIS, MapLibre, or Leaflet. |
| `visible_features.geojson` | Twelve screenshot-visible labeled places with approximate point positions and categories. |
| `red_pixels.json` | Downsampled raw red-pixel samples plus the exact threshold rule used to detect the hand-drawn outline. |
| `boundary_mask.png` | Binary mask of detected red boundary pixels. |
| `boundary_overlay.png` | QA image showing the extracted contour in cyan over the supplied screenshot. |
| `manifest.json` | Machine-readable metadata, sources, named facility classes, and confidence notes. |

## Coordinate and accuracy notes

The pixel geometry is the most reliable part of this package: the supplied screenshot is 1920×1080, and all extracted points preserve their original image coordinates. The latitude/longitude values are **approximate**, anchored to the map URL center shown in the screenshot and a local scale estimate. They should not be used for surveying, emergency routing, construction, or navigation without a second georeferencing pass against current GIS data.

The screenshot contains browser chrome, Google UI, a scale bar, and an opaque panel over part of the red outline. Therefore, the raw-pixel layer and QA overlay are included so the boundary can be corrected manually if needed.

## Verified public facts used

KIET's official infrastructure page reports a built-up college area of 88,041 square metres; academic blocks A–H; 100+ ICT-enabled classrooms; a Central Library connected with eight departmental libraries; an auditorium seating more than 550; a campus temple; sports grounds and courts; hostels; a 24/7 medical centre; faculty apartments; and guest houses. Mapcarta, based on OpenStreetMap, identifies the campus at approximately **28.75257, 77.49851** on Muradnagar Meerut Road (NH 58), Ghaziabad 201206.

## Important provenance limitation

This is not a reproduction of Google's copyrighted satellite tiles or a claim that every building footprint was scraped from Google Maps. The deliverable combines: (1) geometry extracted from the user's supplied image, (2) text labels visible in that image, and (3) public, cited facility information. A true pixel-perfect, georeferenced basemap should be rebuilt from imagery or vector data for which you have the required license, or from an OSM-derived layer with its required attribution.

## Suggested import workflow

1. Load `boundary.geojson` and `visible_features.geojson` into QGIS or a web map.
2. Use the screenshot as a raster reference at its native 1920×1080 dimensions.
3. Align the raster using the supplied map center and at least three visible control points, then replace the approximate longitude/latitude transform.
4. Trace or source building footprints separately; the red outline is a campus-area boundary, not a complete building cadastral layer.
5. Keep the `source` and `confidence` properties attached to every generated feature.

## Sources

- [KIET official infrastructure page](https://www.kiet.edu/campus-life/infrastructure/)
- [Mapcarta / OpenStreetMap-derived KIET listing](https://mapcarta.com/W835252667)
- [OpenStreetMap way 835252667](https://www.openstreetmap.org/way/835252667)
- User-supplied screenshot: `Untitleddesign(10).png`
