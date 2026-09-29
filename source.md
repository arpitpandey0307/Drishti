# source.md — Every external source actually used

> Rule: no invented citations. Everything below was opened/read during this build
> and directly informed an equation, parameter, dataset, or design choice.
> Synthetic/assumed values are listed separately at the bottom, never as citations.

## 1. EPA SWMM (hydrology + hydraulics conceptual model)

- Title: Storm Water Management Model User's Manual Version 5.1
- Author/Organization: Lewis A. Rossman / U.S. EPA Office of Research and Development (NRMRL)
- URL: https://www.epa.gov/sites/default/files/2019-02/documents/epaswmm5_1_manual_master_8-2-15.pdf
- What it was used for: overall simulator architecture — subcatchment rainfall-runoff → inlet capture → 1D pipe/channel routing with nodes/links, storage, surcharge, outfalls; event vs continuous simulation framing; object model (junctions, conduits, outfalls, gullies as sink nodes).
- Concepts adopted: node-link drainage graph; inlet inflow → node storage → conduit routing; surcharge/overflow as excess head above rim; blockage as capacity reduction. No SWMM code was copied.

- Title: Storm Water Management Model Reference Manual Volume I – Hydrology
- Author/Organization: Lewis A. Rossman & Wayne C. Huber / U.S. EPA (EPA/600/R-15/162A, Jan 2016)
- URL: https://cfpub.epa.gov/si/si_public_record_report.cfm?Lab=NRMRL&dirEntryId=309346
- What it was used for: infiltration options and depression-storage handling.
- Equations/concepts adopted: Horton exponential decay `f(t) = fc + (f0-fc)*e^(-k*t)`; Green-Ampt sharp-wetting-front form; SCS-CN incremental form `Q = P²/(P+Smax)`, `Smax = 1000/CN − 10` (inches), modified incremental application per Akan & Houghtalen (2003) as implemented in SWMM; depression storage separated from infiltration (grass ~2.5 mm).

- Title: Storm Water Management Model Reference Manual Volume II – Hydraulics
- Author/Organization: Lewis A. Rossman / U.S. EPA (EPA/600/R-17/111, 2017)
- URL: https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=337162
- What it was used for: pipe hydraulics formulation and dynamic-wave vs kinematic-wave framing for conduits.
- Equations/concepts adopted: Manning-based conduit friction slope; node continuity with storage; pressurized/surcharge flow when hydraulic grade exceeds rim.

## 2. Surface flow — diffusive-wave shallow-water approximation

- Title: A simple raster-based model for flood inundation simulation (LISFLOOD-FP)
- Author/Organization: P.D. Bates & A.P.J. De Roo / Journal of Hydrology 236 (2000), pp. 54–77
- URL: http://www.catalytics.asia/wp-content/themes/catalytics/flood/Bates%20and%20De%20Roo%202000%20lisfloodI.pdf
- What it was used for: core surface solver design — simplest physically-plausible raster flood model: 1D channel + 2D floodplain diffusion wave on a storage-cell grid, explicit inter-cell fluxes, wetting/drying limiter.
- Equations/concepts adopted: floodplain flow as 2D diffusion wave; inter-cell discharge via Manning + water-surface slope; explicit update `dh/dt = (Qin − Qout)/A + R − I − Qd`; flow-limiter scaling so a cell cannot drain more than its volume in one step (CFL-style stability control).

- Title: LISFLOOD-FP User Manual v5.9.6 (Bristol)
- Author/Organization: University of Bristol, School of Geographical Sciences
- URL: https://www.bristol.ac.uk/media-library/sites/geography/migrated/documents/lisflood-manual-v5.9.6.pdf
- What it was used for: solver options taxonomy (kinematic / diffusive / inertial / full SWE), subgrid channel concept, output fields (depth, WSE, velocity per cell per step).
- Concepts adopted: diffusive floodplain solver as default for slowly-varying pluvial events; inertial/full-SWE noted as out of scope.

- Title: An urban pluvial flood simulation model based on diffusive wave approximation of shallow water equations
- Author/Organization: Hydrology Research (IWA Publishing), 2017
- URL: https://iwaponline.com/hr/article/50/1/138/38826/An-urban-pluvial-flood-simulation-model-based-on
- What it was used for: justification of diffusive-wave + Manning for urban pluvial floods; building/rainfall treatment ideas.
- Equations adopted: Manning friction `Sf = n²V²/R^(4/3)` (SI, k=1); equilibrium of gravity vs friction (inertia neglected); 2D extension with `|∇zs|` in denominator.

- Title: Diffusion Wave Approximation to the Shallow Water Equations (HEC-RAS 1D/2D Technical Reference)
- Author/Organization: U.S. Army Corps of Engineers, HEC-RAS documentation
- URL: https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/6.2/theoretical-basis-for-one-dimensional-and-two-dimensional-hydrodynamic-calculations/2d-unsteady-flow-hydrodynamics/hydraulic-equations/diffusion-wave-approximation-to-the-shallow-water-equations
- What it was used for: canonical diffusive-wave momentum form.
- Equations adopted: `V = −R^(2/3)/(n·|∇zs|^½)·∇zs`; mass balance `∂h/∂t = ∇·(β∇zs) + q` with `β = R^(2/3)·h/(n·|∇zs|^½)`.

- Title: Testing a simple 2D hydraulic model in an urban flood experiment
- Author/Organization: Francesco Dottori & Ezio Todini / Hydrological Processes (Wiley, 2012, doi:10.1002/hyp.9370)
- URL: https://doi.org/10.1002/hyp.9370
- What it was used for: validation that a simple 2D diffusive model reproduces bulk urban flood depths/extents while missing local inertial shocks; porosity/roughness proxy for buildings.
- Concepts adopted: represent buildings as blocked cells + raised roughness as an acceptable coarse-grid proxy (used in our land-cover scheme).

## 3. Infiltration

- Title: Evaluating three commonly used infiltration methods for permeable surfaces in urban areas using SWMM and STORM
- Author/Organization: Hydrology Research (IWA Publishing)
- URL: https://iwaponline.com/hr/article/52/1/160/79270/Evaluating-three-commonly-used-infiltration
- What it was used for: choosing Horton as default event model, Green-Ampt/SCS-CN as options; parameter sensitivity guidance.
- Concepts adopted: Horton most sensitive to minimum (saturated) rate; Green-Ampt to Ks; field measurement of saturated rate matters most; Holtan noted but not implemented (needs soil-moisture accounting + ET).

- Title: Infiltration in InfoSWMM and InfoSWMM SA for Horton, Green-Ampt and Curve Number options
- Author/Organization: swmm5.org (Autodesk/CHI community docs, 2017)
- URL: https://swmm5.org/2017/11/06/infiltration-in-infoswmm-and-infoswmm-sa-for-horton-green-ampt-and-curve-number-options/
- What it was used for: SCS-CN incremental implementation details reused in our `infiltration.py`.
- Equations adopted: per-step `F1 = P − P²/(P+S1)`, `f = (F1−F)/dt`; inter-event reset `T = 4.5/√Ks`; dry-weather recovery `S += k·(Smax−S)·dt`.

## 4. Manning roughness n

- Title: Open-Channel Hydraulics
- Author/Organization: Ven Te Chow (1959), via TxDOT/Un-Spider/HEC-RAS reproductions
- URL (table reproduction actually read): https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-11--time-of-concentration/manning-s-roughness-coefficient-values.html
- What it was used for: Manning n values per land cover.
- Values adopted: concrete 0.011–0.015; earth channels 0.022–0.033; short grass 0.025–0.035; dense brush up to 0.16; mapped to campus classes — roads 0.013–0.016, buildings blocked, open/grass 0.03–0.05, drains (concrete pipe) 0.013.

- Title: Guide for Selecting Manning's Roughness Coefficients for Natural Channels and Flood Plains
- Author/Organization: U.S. Geological Survey, Water-Supply Paper 2339
- URL: https://pubs.usgs.gov/wsp/2339/report.pdf
- What it was used for: Cowan (1956) additive procedure background; confirmed ranges; not directly coded.

- Title: Design Charts for Open-Channel Flow (HDS-3)
- Author/Organization: U.S. FHWA
- URL: https://www.fhwa.dot.gov/engineering/hydraulics/pubs/hds3.pdf
- What it was used for: Manning equation in SI `V = (1/n)·R^(2/3)·S^(1/2)`, `Q = A·V`; circular-pipe part-full relations; uniform-flow assumptions and limits.
- Equations adopted: full-flow pipe capacity `Qcap = (1/n)·A·R^(2/3)·√S` with `A = πD²/4`, `R = D/4`.

## 5. Terrain / GIS data sources (KIET domain)

- Title: Copernicus DEM Product Handbook / Global and European DEM collection description
- Author/Organization: DLR / Airbus Defence and Space, via Copernicus Data Space Ecosystem (TanDEM-X 2011–2015; GLO-30 1″ ≈ 30 m; vertical accuracy < 4 m LE90; DSM including buildings/vegetation)
- URL: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- What it was used for: provenance of `data/terrain_grid.json` (13×20, 100 valid cells, 214.68–231.31 m) and known limits (30 m DSM ±4 m; DSM≠DTM; cannot resolve roads/drains).
- Adopted: honest-accuracy labels carried into configs and plots; DEM upsampling explicitly marked synthetic.

- Title: OpenStreetMap (roads, buildings, campus boundary way 835252667)
- Author/Organization: © OpenStreetMap contributors
- URL: https://www.openstreetmap.org (data vendored as `data/roads.geojson`, `data/campus.geojson`, `kiet_terrain/campus_osm.geojson`)
- What it was used for: road centerlines (199 features), building footprints, campus boundary polygon.
- Adopted: roads → low-roughness impervious corridors + inlet placement; buildings → blocked cells; boundary → domain mask.

- Title: KIET sanctioned compounding plan Rev 6 (GDA approval 2024)
- Author/Organization: Krishna Charitable Society / Er. Atul Goel / Ghaziabad Development Authority (photographed drawing set, transcribed in `kiet_campuse_data/info.md`; machine-readable subset `data/campus_accurate.geojson`)
- What it was used for: authoritative building list (17 blocks), plot area 68,331.72 m², ground coverage 20,801.07 m², FAR 87,715 m² — used for impervious-fraction sanity checks only.
- Adopted: nothing structural; flagged UNVERIFIED where georeferencing is affine-approximate (3–5 m target).

## 6. Rainfall data sources (local, in-repo)

- Files: `random_info/daily_rainfall_2016_2026.csv` (3652 daily rows, 2016–2026, max 114.59 mm/day, p99 ≈ 37.2 mm/day, 24 days > 50 mm); `random_info/Ghaziabad_Rainfall_2021_2025.csv`, `random_info/GPM_IMERG_Ghaziabad_Rainfall_2021_2025.csv`, `random_info/ERA5_Land_Ghaziabad_Rainfall_2021_2025.csv` (1827 rows each).
- Author/Organization: unknown provenance (files as found; GPM IMERG = NASA, ERA5-Land = ECMWF/Copernicus — inferred from filenames, NOT verified).
- What it was used for: scenario intensity/duration ranges — event totals 10–150 mm, durations 1–6 h, peak 5-min intensities up to ~90 mm/h; never presented as calibrated design storms.
- Adopted: `config/rainfall.yaml` ranges + dataset `rainfall_total_mm` spot-checks against p99/max above.

## 7. Software / formats

- Python + numpy + scipy (bilinear `zoom`, flow routing math) — https://numpy.org, https://scipy.org
- h5py (HDF5 dataset container) — https://www.h5py.org
- PyYAML (config files) — https://pyyaml.org
- matplotlib (validation/viz PNGs) — https://matplotlib.org
- HEC-RAS infiltration-methods reference (SCS-CN/Horton/Green-Ampt parameter context) — https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/latest/developing-a-terrain-model-and-geospatial-layers/infiltration-methods

## 9. Dataset v1.0 design + generation environment (Phase 3, 2026-09-06)

- Title: scipy.stats.qmc.LatinHypercube (SciPy v1.18.0 Manual)
- URL: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html
- What it was used for: stratified sampling of the continuous scenario knobs
  (duration_h, storm-cell sigma, moving-cell speed) in `simulation/scenarios/suite_v2.py`.
- Concepts adopted: LHS places exactly one point per univariate stratum
  [j/n,(j+1)/n); variance lower than plain MC. Numpy-stratified fallback when
  scipy is unavailable.
- References noted from that page (not separately opened): McKay et al., "A Comparison
  of Three Methods for Selecting Values of Input Variables in the Analysis of Output
  from a Computer Code", Technometrics, 1979 (LHS origin); Stein 1987; Owen 1992/1997.

- Tooling: Google Colab CPU runtime as PRIMARY generation environment
  (benchmarked 2026-09-06: 2 vCPU, ~13 GB RAM, 94 GB free disk, 0.57 s per 5-min
  output step, ~2.3x the local PC); local PC kept for dev/debugging/QC.
  Session management via `google-colab-cli` (`colab new/exec/upload/download`
  commands; CLI README read 2026-09-06). Colab notebook: `docs/colab_generation.ipynb`.
- Rainfall class quotas (trace/light/moderate/heavy/extreme + OOD 150-200 mm)
  grounded in the local CSV stats of section 6 (daily max 114.59 mm, p99 ~37 mm/day);
  event totals 3-150 mm train, durations 0.5-6 h train / 6-8 h OOD.

## 10. Synthetic Assumptions ADDED in Phase 3 (NOT real data)

1. Fine simulation grid (default 5 m, 100×80) bilinearly upsampled from 30 m DSM — sub-30 m relief is INTERPOLATED, not measured (`verified=false`).
2. Entire underground drainage network (nodes, pipes, diameters 0.3–1.2 m, slopes, inverts, inlet capacities) is SYNTHETIC, terrain+road-inferred (`source=synthetic/inferred`, `verified=false`, per-feature `confidence` 0.3–0.7).
3. No real inlet/drain survey exists; inlet spacing ~25–40 m along roads near low points is a planning-rule guess.
4. Infiltration params (Horton f0/fc/k per land class), depression storage, Manning n per class are literature-typical values, NOT calibrated to KIET soils.
5. Building cells treated as blocked (no flow, no ponding) — rooftop storage/drainage ignored.
6. Outfall water levels assumed free discharge; no downstream river backwater model.
7. Rainfall scenarios are plausible-synthetic (Indian monsoon ranges), not IMD design storms; no IDF curve was fitted.
8. Pipe sedimentation/blockage fractions (0–90%) are scenario knobs, not inspection data.
9. Coordinate work in UTM 43N (EPSG:32643) via local equirectangular projection; sub-metre projection error accepted at campus scale.
10. All flood depths are MODEL OUTPUT on synthetic terrain+drainage — never to be labelled as observed KIET flooding.
11. Phase-3 per-scenario uncertainty knobs are scenario samplers, NOT measurements:
    drain_eff 0.7-1.3 (0.5-0.65 OOD) pipe+inlet capacity multiplier; DEM jitter
    N(0, 0.05 m); manning scale 0.9-1.1; depression-storage scale 0.5-1.5;
    imperv_open 0.25-0.45; recession tails 0-2 h; 6 synthetic network variants;
    OOD rainfall 150-200 mm / 6-8 h / storm speeds 10-15 m/s / blockage 0.6-0.85.
