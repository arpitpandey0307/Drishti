# Viewer — interactive flood simulation viewer

Browser app (`flood_viewer.html`, canvas 2D, no JS dependencies; Google Fonts
with system fallback) styled with the **Quiet Cartography Overlay Design System**
(`Quiet Cartography Overlay Design System.md`): full-bleed map as the primary
visual, warm ivory glass cards at the edges (scenario directory left, inspector
detail card right, transport bar bottom-center, live-stats lower-left, layer
controls lower-right), Manrope + Playfair Display italic + DM Mono, terracotta
accents, honest-precision footnotes. Map data colours are scientific and
unchanged by the styling.

## Run

```
python3 -m http.server 8123            # fetch() needs http, not file://
# open http://localhost:8123/flood_viewer.html
```

Press Play (or Space), scrub the timeline (or ←/→), click cells/nodes/pipes.

## CSV export (⤓t / ⤓s buttons in the transport bar)

- **⤓t** — `<scenario>_timeline.csv`: per-frame `t_min, rain_mean/max_mm,
  flooded_cells, flooded_m2, max_depth_m` (straight from the bundle meta, no fetch).
- **⤓s** — `<scenario>_<cell|node|pipe>_<id>.csv`: full event series for the
  current inspector selection (cell → rain/depth/velocity; node → level;
  pipe → flow). Fetches all frames with `k/T` progress on the button.
- Both carry a `#` header: scenario id + synthetic-drainage note + 1 mm display resolution.

## Data pipeline (all precomputed)

```
kiet_flood_{split}.h5 + kiet_networks_{split}.json
  → python3 -m visualization.data_adapter.export_viz --split test
  → outputs/viz/index.json + <scenario>/meta.json + frame_*.json
  → python3 -m visualization.data_adapter.validate_viz   # must print ALL CHECKS PASSED
```

Frames store int16/base64 grids (rain 0.1 mm, depth mm, velocity cm/s, node mm;
pipes int32 1e-5 m³/s). Display resolution 1 mm; borderline 49–51 mm cells may
differ from float H5 counts — validated as the only difference.

## What each visual element is driven by

| visual | source field |
|---|---|
| terrain/buildings/roads | DEM + landcover masks (static) |
| rain wash | `rain_dmm` per frame |
| water colour | `depth_mm` per frame, bands 0/1/5/10/20/50+ cm |
| pipe colour/width | `pipe_e5` ÷ effective capacity (blockage-adjusted) |
| flow chevrons | graph edges u→v (exact direction) |
| surcharge halo | node level ≥ rim − 2 mm (model caps at rim on overflow) |
| velocity arrows | `vel_cms` magnitude + downhill surface gradient |
| metrics/inspector | frame data + meta adjacency (no other inputs) |

## Validation (2026-09-06, scenario_0009)

`validate_viz.py`: DEM/max-depth/ttf exact; frames 0/30/60 rain/depth/node/pipe
exact within quantization; edge u→v match; derived surcharge set ==
model-reported set (21 ids); flooded counts match quantized grids.
Browser-tested: scrub, play/pause/reset, speed, all 6 layer toggles, scenario
switch, cell/node/pipe inspector (node #9: level 1.500 m = rim, surcharge YES;
pipe #39: 0.0104/0.4932 m³/s).

## Limits

- 2D only (deliberate — no fake 3D).
- Bundles ~6 MB/scenario, lazy-loaded (~150 KB/frame); fine on localhost.
- `outputs/` is gitignored; regenerate with the two commands above.
