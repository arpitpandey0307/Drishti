# KIET 3D Mesh Visual — Design (2026-09-05)

## Goal
Convert `kiet_3d_standalone.html` + `kiet_3d_terrain.html` from solid 3D to mesh visual, defaulting to mesh+solid overlay.

## Decisions (user-approved)
- Style: wireframe overlay (faint solid for depth + bright wireframe grid)
- Scope: terrain + buildings + base, both 3D files

## Architecture
Reuse same BufferGeometry / ExtrudeGeometry. Dual-layer:
- `terrainSolid`: MeshStandardMaterial vertexColors, transparent, opacity 0.35 (both) / 1.0 (solid-only)
- `terrainWire`: MeshBasicMaterial color #22d3ee, wireframe:true, opacity 0.85, y-offset +0.15 to avoid z-fight
- `base`: keep BoxGeometry solid (transparent 0.9) + EdgesGeometry LineSegments cyan
- `buildings`: solid MeshStandardMaterial transparent 0.45 + per-building EdgesGeometry LineSegments (#7dd3fc)
- `acc` (sanctioned, standalone only): same pattern, keep green/red colors, transparent 0.35 + edges
- Roads/contours/low-points unchanged (already lines), render on top.

## Controls
Panel adds `Style: [Mesh+Solid | Mesh only | Solid only]` dropdown (`#style`), default `both`.
`curStyle` + `applyStyle()` toggles `meshParts.solid[]` / `meshParts.wire[]` visibility + opacity.
Async acc buildings push to same lists + re-apply current style.

## Data flow / errors
No data change. Raycast still hits `window._terrain` solid. Wireframe has no lighting impact.

## Testing
Open both HTML via `python3 -m http.server`, orbit, switch Style modes, click terrain for elevation, toggle layers.
