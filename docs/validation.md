# Validation

Automated: `tests/test_simulator.py` (8 tests, all passing 2026-09-06) +
`simulation/validation/checks.py` gates inside every dataset run
(surface issues warn, graph errors abort, mass error stored per scenario).

## Physics (spec seed=1, peaked, uniform, 2 h, 80 mm)

| check | result |
|---|---|
| mass conservation | rel. err 3e-8 (machine precision) |
| rainfall→runoff monotonic (20 vs 120 mm) | pass |
| blockage 0→50%: drainage 12.2→8.2 mm, ponding 44.5→48.5 mm | pass |
| low-point mean max-depth 0.089 m vs 0.044 m elsewhere (~2×) | pass |
| surcharge nodes in 80 mm event | 20–23 |

## Numerical

- No NaN/Inf/negative-depth across 10 test scenarios + suite.
- Max depth ≤ 1.2 m; velocity capped 3 m/s.
- Explicit-diffusion guards: 1/8-volume face cap, S cap 0.05, wall boundaries.

## Graph

- No bad endpoints/lengths/diameters/slopes/capacities; no orphans; ≥1 outfall;
  DAG-to-outfall construction (no trapped cycles); 3/3 variants valid.

## Manual

- `outputs/figures/scenario_0003.png`, `scenario_0009.png`: SW-high→NE-low fall,
  storm cells, ponding in low pockets, networks following roads — inspected 2026-09-06.
- Test split: 10/10 scenarios mass_err = 0.000.

## Scale-up rule

val (100) → prod (1000) only after re-running this suite green.
