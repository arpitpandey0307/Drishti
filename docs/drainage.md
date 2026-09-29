# Drainage — synthetic network G=(V,E)

**Every node/edge: `verified=false`, `source=synthetic/inferred`, confidence 0.3–0.7.
NEVER present as real KIET infrastructure.**

## Generation (`simulation/drainage/network.py`)

1. Candidate score = flow accumulation + low-point bonus + road proximity (12 m),
   masked to in-domain non-building cells.
2. Greedy max-score picking with 15 m exclusion → ~50 inlets (target 60, spacing-limited).
3. 2 outfalls = lowest-ground nodes.
4. Downstream DAG: each node links to a node strictly closer to an outfall
   (drop-weighted); fallback = direct trunk edge (D=1.0 m). Guarantees a drainage path —
   no trapped cycles (verified by mass closure + graph checks).
5. Diameters sampled from [0.25–0.8] m, n ∈ [0.011, 0.017], slopes clamped [0.002, 0.05].

## Uncertainty (so ML never trusts one fictional network)

- `network_variants: 3` distinct topologies/seeds per split.
- Per-scenario blockage level ∈ {0, 10, 25, 50, 75, 90}% × 3 modes
  (uniform pipe, inlet subset, outfall restricted).
- Diameter/roughness/inlet-capacity/position jitter sampled per variant.

## Replacing with real data

Drop a real network JSON with the same schema (nodes: id/kind/i/j/lat/lon/rim/invert;
edges: u/v/length/diameter/slope/n) and set `verified=true, source=municipal-survey`.
No simulator rewrite needed. Exported example: `outputs/geojson/synthetic_drainage_v0.geojson`.
