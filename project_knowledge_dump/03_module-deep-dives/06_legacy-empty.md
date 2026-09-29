# 03.06 — Legacy / empty / dead namespaces

- `flood/` — NO SOURCE. Only `__pycache__/` 3 orphan bytecode: `hydraulics.cpython-312.pyc` 31 KB, `rainfall` 18 KB, `routing` 18 KB (Sep05 19:14–39) + `__init__` 194 B. [INFERRED] former `flood/{hydraulics,rainfall,routing}.py` deleted after refactor into `simulation/{hydraulics,rainfall}/` + `api/route.py`. Do not import.
- `drainage/` — EMPTY (only `.`/`..`). Placeholder; real code `simulation/drainage/network.py` + `simulation/hydraulics/pipes.py`, config `config/drainage.yaml`.
- `synthetic/seed11/`, `synthetic/quarantine/` — both empty (24 B `.`+`..`). Superseded by `outputs/datasets/v1/kiet_flood_quarantine.h5` 7.0 MB.
- `terrain/processed/`, `terrain/products/` — empty; awaiting DEM build outputs.
- `visualization/{viewer,layers,animation,controls}/__init__.py` — 0-byte stubs; only `data_adapter/` live.
- Root zips (gitignored, local-only): `kiet_campus_map_reconstruction.zip` 3.0 MB + `kiet_real_terrain_package.zip` 41.6 MB — extracted folders tracked instead.
- Previews root: `preview_3d_browser.png` 119 KB, `preview_3d_terrain.png` 361 KB, `preview_campus_zoom.png` 748 KB, `preview_flood_viewer_surcharge.png` 438 KB, `preview_road_map.png` 280 KB, `preview_terrain_map.png` 692 KB.
