# 07 — Research Papers / References / Inspiration

Rule (`source.md:3-5`): everything opened/read, directly informed equation/param/dataset/design. No invented citations. Strongly-implied (no explicit cite) marked [IMPLIED].

## 1. EPA SWMM (architecture + infiltration) — source.md:7-25

- Rossman/EPA NRMRL **SWMM 5.1 User Manual** (`epa.gov/...epaswmm5_1_manual...pdf`): subcatchment→inlet→1D routing, nodes/links storage, surcharge, outfalls, event vs continuous. Adopted node-link graph, inlet→node→conduit, surcharge above rim, blockage capacity cut. No code copied.
- Rossman & Huber **SWMM Vol I Hydrology** EPA/600/R-15/162A (2016): Horton `f(t)=fc+(f0−fc)e^(−kt)` → `infiltration.py:4-5` + `simulate.py:83`; Green-Ampt; SCS-CN `Q=P²/(P+Smax)`, `Smax=1000/CN−10` in → metric `25400/CN−254` mm → `infiltration.py:20`; Akan & Houghtalen 2003 incremental → `infiltration.py:37-40`; depression separated (grass ~2.5 mm) → `hydraulics.yaml:19-20` open 2.5/road 1.0.
- Rossman **SWMM Vol II Hydraulics** EPA/600/R-17/111 (2017): Manning conduit friction → `pipe_capacity()`; node continuity+storage → `pipes.py:58`; dynamic vs kinematic framing.
- IWA **Evaluating three methods (SWMM/STORM)** + swmm5.org **InfoSWMM 2017**: Horton default / Green-Ampt / SCS-CN options; per-step `F1=P−P²/(P+S1)`, `f=(F1−F)/dt`; dry recovery (in `infiltration.py`, unwired). Green-Ampt/Holtan researched, deliberately not implemented (`knowledge.md:172-197`).

## 2. Surface diffusive wave — source.md:27-57

- **Bates & De Roo 2000**, J. Hydrology 236, 54–77, LISFLOOD-FP: 1D channel + 2D floodplain diffusion storage-cell, explicit fluxes, wetting/drying limiter → `runoff.py:1-64` (flux, limiter 1/8, `dh/dt=(Qin−Qout)/A+R−I−Qd`).
- **LISFLOOD-FP Manual v5.9.6** (Bristol): kinematic/diffusive/inertial/full-SWE taxonomy; diffusive default for slowly-varying pluvial; inertial/full out of scope (decision).
- IWA 2017 **urban pluvial diffusive**: Manning `Sf=n²V²/R^(4/3)` SI k=1, gravity≈friction, 2D `|∇zs|` denominator → `runoff.py:19,28`.
- **HEC-RAS DWE**: `V=−R^(2/3)/(n|∇zs|^½)∇zs`, `∂h/∂t=∇·(β∇zs)+q`, `β=R^(2/3)h/(n|∇zs|^½)` → `docs/simulation.md:20-25`, `knowledge.md:145-170`.
- **Dottori & Todini 2012**, Hydrol. Processes doi:10.1002/hyp.9370: simple 2D diffusive reproduces bulk depths/extents, misses inertial shocks; buildings blocked+raised roughness → `twin.py:146-152` (n 0.20), `runoff.py:33-38` walls.
- [IMPLIED] Chow 1959 open-channel (via TxDOT table, actually read): concrete 0.011–0.015, earth 0.022–0.033, grass 0.025–0.035, brush →0.16 → mapped roads 0.013–0.016, open 0.03–0.05, pipe 0.013 (`source.md:73-90`). USGS WSP 2339 Cowan 1956 background only. FHWA HDS-3 SI `V=(1/n)R^(2/3)S^(1/2)`, `Q=A·V`, circular part-full → `Qcap` (`source.md:73-90`).

## 3. Terrain/GIS/rainfall/software — source.md:92-124

- Copernicus DEM handbook via Data Space (DLR/Airbus TanDEM-X 2011–2015 GLO-30 1″ ~30 m <4 m LE90 DSM) → `terrain_grid.json` provenance + limits.
- OSM (roads/buildings/boundary way 835252667) → `data/roads.geojson` etc.
- KIET sanctioned Rev6 GDA 2024 (photos) → `campus_accurate.geojson` (sanity only, UNVERIFIED affine 3–5 m).
- In-repo CSVs (daily max 114.59 p99 ~37) → `rainfall.yaml` ranges; never calibrated.
- numpy+scipy (`zoom`, routing), h5py, PyYAML, matplotlib, HEC-RAS infiltration ref.

## 4. v1.0 sampling/compute — source.md:127-146

- `scipy.stats.qmc.LatinHypercube` docs (SciPy v1.18.0): one point per stratum, variance<MC, numpy fallback → `suite_v2.py:49-61`. Refs McKay et al. 1979 Technometrics, Stein 1987, Owen 1992/1997 (not separately opened).
- Colab CPU primary (benched 2vCPU ~13 GB 0.57 s/step ~2.3× local; T4 0.58 identical — NumPy can't use GPUs) → `docs/colab_generation.ipynb`; `google-colab-cli` README.
- Rainfall quotas + OOD grounded in §6 CSV stats.

## 5. [IMPLIED] by implementation (no explicit cite in repo)

- A* (Hart/Nilsson/Raphael 1968) — `api/route.py` heapq 8-conn + `space/index.html:51` JS mirror + planner Dijkstra+A* (`flood_planner.html:149`).
- D8 flow routing (O'Callaghan & Mark 1984) — `twin.py:158-188`.
- Horn 1981 slope + standard hillshade (az315/alt45) — report Exp2.
- Affine (6-param) georeferencing — `build_accurate_geojson.py:17-54`.
- U-Net (Ronneberger et al. 2015) — `baseline_unet.py` encoder-decoder + skip-pad.
- Adam (Kingma & Ba 2015), BCE+MSE multitask, Welford streaming stats, Latin Hypercube (above), SCS-CN (USDA-SCS 1972 via SWMM docs above).

## 6. Links

SWMM manuals (EPA URLs in `source.md`), LISFLOOD-FP paper/manual, HEC-RAS DWE docs, Copernicus Data Space, OSM/Overpass, Leaflet 1.9.4, Three.js 0.160, onnxruntime/ORT-web 1.22.0, HF static Spaces, Vercel/Render static, Esri World Imagery. Full URLs in `source.md`.
