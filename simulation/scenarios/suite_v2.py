"""Stratified v1.0 scenario sampler for flood-ML training data.

Design (see docs/dataset_report.md for the sizing rationale):
- Rainfall TOTAL classes by quota (light/moderate/heavy/extreme + trace/no-flood),
  grounded in local CSV stats (daily max 114.59 mm, p99 ~37 mm/day -> event 3-150 mm).
- Latin-Hypercube sampling (scipy.stats.qmc, numpy fallback) over the continuous
  knobs: duration_h, storm-cell sigma, moving-cell speed. Categorical knobs
  (temporal/spatial profiles) are round-robin balanced.
- Drainage uncertainty: network_variant (6 synthetic variants) x drain_eff scale
  (pipe capacity + inlet capacity multiplier) x inlet capacity jitter.
- Blockage: balanced quotas over levels x modes (never dominates).
- Terrain/surface uncertainty: tiny DEM delta (sigma 0.05 m), manning scale,
  depression-storage scale, impervious-open jitter. Original verified terrain
  is NEVER modified -- deltas are stored per-scenario and applied at run time.
- Recession tail: ~40% of scenarios get a dry tail (0.5-2 h) so the dataset
  contains drain-down dynamics ("flooding that later drains").
- Targeted edge-case classes (~15%): high-rain/free-drainage, moderate-rain +
  severe-blockage, storm-on-low-point, rapid-surcharge.
- OOD sampler: deliberately out-of-range combos (heavier/longer rain, faster
  storms, tighter cells, unseen blockage levels, restricted drainage).

All randomness derives deterministically from (master_seed, split, index), so
scenario IDs and specs are reproducible and resumable.
"""
from __future__ import annotations
import numpy as np

DATASET_VERSION = "1.0"
SIMULATOR_VERSION = "1.0"

# (class_name, total_mm_lo, total_mm_hi, quota) -- quotas sum to 1 within main pool
RAIN_CLASSES = [
    ("trace",    3.0,  12.0, 0.08),   # likely no-flood
    ("light",   12.0,  30.0, 0.12),
    ("moderate", 30.0,  60.0, 0.30),
    ("heavy",    60.0, 100.0, 0.30),
    ("extreme", 100.0, 150.0, 0.20),
]

TEMPORALS = ["uniform", "peaked", "front_loaded", "back_loaded", "multi_peak"]
SPATIALS = ["uniform", "gaussian_cell", "moving_cell", "gradient", "multi_cell"]
BLOCKAGE_MODES = ["pipe_uniform", "inlet_subset", "outfall_restricted"]
# (level, quota) -- balanced so blockage never dominates
BLOCKAGE_QUOTA = [(0.0, 0.30), (0.10, 0.20), (0.25, 0.15), (0.50, 0.15), (0.75, 0.10), (0.90, 0.10)]

N_NETWORK_VARIANTS = 6


def _lhs(n, d, seed):
    """Latin Hypercube samples in [0,1)^(n,d). scipy.qmc preferred, else stratified."""
    try:
        from scipy.stats import qmc
        sampler = qmc.LatinHypercube(d=d, seed=seed)
        return sampler.random(n=n)
    except Exception:
        rng = np.random.default_rng(seed)
        out = np.zeros((n, d))
        for j in range(d):
            perm = rng.permutation(n)
            out[:, j] = (perm + rng.random(n)) / n
        return out


def _assign_rain_class(n, rng):
    quotas = np.array([q for _, _, _, q in RAIN_CLASSES])
    counts = (quotas * n).astype(int)
    # fix rounding remainder on the largest class
    counts[np.argmax(quotas)] += n - counts.sum()
    classes = []
    for (name, lo, hi, _), c in zip(RAIN_CLASSES, counts):
        for _ in range(c):
            classes.append((name, float(rng.uniform(lo, hi))))
    rng.shuffle(classes)
    return classes


def _assign_blockage(n, rng):
    levels = [lv for lv, _ in BLOCKAGE_QUOTA]
    probs = np.array([q for _, q in BLOCKAGE_QUOTA])
    probs /= probs.sum()
    return [float(rng.choice(levels, p=probs)) for _ in range(n)]


def make_prod_suite(n, master_seed, network_variants=N_NETWORK_VARIANTS):
    """Stratified production pool (split assignment happens in assign_splits)."""
    rng = np.random.default_rng(master_seed)
    lhs = _lhs(n, 3, master_seed + 1)  # duration, sigma, speed
    rain_classes = _assign_rain_class(n, rng)
    blockages = _assign_blockage(n, rng)
    specs = []
    for k in range(n):
        rcls, total = rain_classes[k]
        dur = float(0.5 + lhs[k, 0] * 5.5)          # 0.5 - 6 h
        if rcls == "trace":
            dur = float(min(dur, rng.uniform(0.5, 1.5)))
        sigma = float(40.0 + lhs[k, 1] * 110.0)     # 40 - 150 m
        speed = float(2.0 + lhs[k, 2] * 8.0)        # 2 - 10 m/s
        blk = blockages[k]
        mode = BLOCKAGE_MODES[k % len(BLOCKAGE_MODES)]
        edge = None
        r = rng.random()
        if k % 20 >= 17:  # ~15% targeted edge cases, deterministic positions
            edge = ["free_drain", "blocked_moderate", "lowpoint_bullseye",
                    "rapid_surcharge"][k % 4]
            if edge == "free_drain":
                total, blk, mode = float(rng.uniform(90, 150)), 0.0, "pipe_uniform"
            elif edge == "blocked_moderate":
                total, blk = float(rng.uniform(25, 60)), float(rng.choice([0.75, 0.90]))
            elif edge == "lowpoint_bullseye":
                total = float(rng.uniform(30, 90))
            elif edge == "rapid_surcharge":
                total, blk, mode = float(rng.uniform(60, 120)), \
                    float(rng.choice([0.5, 0.75])), "outfall_restricted"
        specs.append({
            "scenario_idx": k,
            "seed": int(master_seed + 100003 * k),
            "split": "prod",
            "rain_class": rcls if edge is None else f"{rcls}+edge:{edge}",
            "edge_case": edge,
            "temporal": TEMPORALS[(k * 7 + master_seed) % len(TEMPORALS)] if edge not in (
                "rapid_surcharge",) else str(rng.choice(["peaked", "front_loaded"])),
            "spatial": SPATIALS[(k * 11 + master_seed // 7) % len(SPATIALS)] if edge not in (
                "lowpoint_bullseye",) else "gaussian_cell",
            "duration_h": round(dur, 3),
            "total_mm": round(total, 2),
            "storm_sigma_m": round(sigma, 1),
            "storm_speed_mps": round(speed, 2) if edge != "rapid_surcharge" else round(float(rng.uniform(2, 6)), 2),
            "storm_dir_deg": round(float(rng.uniform(0, 360)), 1),
            "bullseye_lowpoint": bool(edge == "lowpoint_bullseye"),
            "network_variant": int(k % network_variants),
            "drain_eff": round(float(rng.uniform(0.7, 1.3)) if edge != "free_drain"
                               else float(rng.uniform(1.2, 1.35)), 3),
            "blockage_level": blk,
            "blockage_mode": mode,
            # surface/terrain uncertainty (small, documented)
            "terrain_jitter_m": 0.05,
            "terrain_seed": int(master_seed + 200011 * k),
            "manning_scale": round(float(rng.uniform(0.9, 1.1)), 3),
            "dep_scale": round(float(rng.uniform(0.5, 1.5)), 3),
            "imperv_open": round(float(rng.uniform(0.25, 0.45)), 3),
            "recession_h": round(float(rng.choice([0.0, 0.0, 0.0, 0.5, 1.0, 1.5, 2.0])), 2),
            "dataset_version": DATASET_VERSION,
        })
    return specs


def make_ood_suite(n, master_seed, network_variants=N_NETWORK_VARIANTS):
    """Out-of-distribution: every scenario carries >=2 out-of-range factors."""
    rng = np.random.default_rng(master_seed)
    specs = []
    for k in range(n):
        specs.append({
            "scenario_idx": k,
            "seed": int(master_seed + 300017 * k),
            "split": "ood",
            "rain_class": "ood",
            "edge_case": None,
            "temporal": TEMPORALS[(k * 5 + 1) % len(TEMPORALS)],
            "spatial": ["moving_cell", "multi_cell", "gaussian_cell"][k % 3],
            "duration_h": round(float(rng.uniform(6.0, 8.0)), 3),       # beyond train max 6 h
            "total_mm": round(float(rng.uniform(150.0, 200.0)), 2),     # beyond train max 150 mm
            "storm_sigma_m": round(float(rng.uniform(25.0, 40.0)), 1),  # tighter than train
            "storm_speed_mps": round(float(rng.uniform(10.0, 15.0)), 2),  # faster than train
            "storm_dir_deg": round(float(rng.uniform(0, 360)), 1),
            "bullseye_lowpoint": bool(k % 3 == 0),
            "network_variant": int((k * 2 + 1) % network_variants),
            "drain_eff": round(float(rng.uniform(0.5, 0.65)), 3),       # below train range
            "blockage_level": float(rng.choice([0.6, 0.85])),           # unseen levels
            "blockage_mode": BLOCKAGE_MODES[k % len(BLOCKAGE_MODES)],
            "terrain_jitter_m": 0.05,
            "terrain_seed": int(master_seed + 400031 * k),
            "manning_scale": round(float(rng.uniform(0.9, 1.1)), 3),
            "dep_scale": round(float(rng.uniform(0.5, 1.5)), 3),
            "imperv_open": round(float(rng.uniform(0.25, 0.45)), 3),
            "recession_h": round(float(rng.choice([0.0, 1.0, 2.0])), 2),
            "dataset_version": DATASET_VERSION,
        })
    return specs


def assign_splits(specs, seed, train_frac=0.70, val_frac=0.15):
    """Scenario-level 70/15/15 split, stratified by (rain_class_base, blocked_any).

    Deterministic: sorts each stratum by seed, deals round-robin. Never splits
    frames -- a whole scenario lands in exactly one split.
    """
    rng = np.random.default_rng(seed)
    order = np.arange(len(specs))
    rng.shuffle(order)
    # strata key
    from collections import defaultdict
    strata = defaultdict(list)
    for k in order:
        sp = specs[k]
        base = sp["rain_class"].split("+")[0]
        key = (base, sp["blockage_level"] > 0)
        strata[key].append(k)
    train, val, test = [], [], []
    for key in sorted(strata):
        idx = sorted(strata[key], key=lambda k: specs[k]["seed"])
        nk = len(idx)
        ntr = int(round(nk * train_frac))
        nv = int(round(nk * val_frac))
        ntr = min(ntr, nk)
        nv = min(nv, nk - ntr)
        nte = nk - ntr - nv
        train += idx[:ntr]
        val += idx[ntr:ntr + nv]
        test += idx[ntr + nv:]
    # fix global rounding drift: move between buckets deterministically if needed
    want_tr, want_v = int(round(len(specs) * train_frac)), int(round(len(specs) * val_frac))
    pool = {"train": sorted(train), "val": sorted(val), "test": sorted(test)}
    while len(pool["train"]) > want_tr and len(pool["test"]) < len(specs) - want_tr - want_v:
        pool["test"].append(pool["train"].pop())
    return pool


def make_topup_suite(n_dry=24, n_freedrain=12, seed=99991,
                     split_quota=(25, 5, 6), network_variants=N_NETWORK_VARIANTS):
    """Targeted no-flood/minor-flood top-up (analysis-driven, see dataset stats).

    Dry drizzle + free-drainage moderate rain: tiny totals, zero blockage,
    high drain_eff, long recession tails. IDs start at scenario_idx 10000 so
    they never collide with the main pool. ml_split preassigned per quota.
    """
    rng = np.random.default_rng(seed)
    specs = []
    for k in range(n_dry + n_freedrain):
        dry = k < n_dry
        specs.append({
            "scenario_idx": 10000 + k,
            "seed": int(seed + 500009 * k),
            "split": "topup",
            "rain_class": "trace+topup:dry" if dry else "light+topup:free_drain",
            "edge_case": "topup_dry" if dry else "topup_free_drain",
            "temporal": "uniform",
            "spatial": str(rng.choice(["uniform", "gradient"])),
            "duration_h": round(float(rng.uniform(0.5, 1.0)), 3),
            "total_mm": round(float(rng.uniform(1.0, 8.0)) if dry
                              else float(rng.uniform(15.0, 40.0)), 2),
            "storm_sigma_m": round(float(rng.uniform(80.0, 150.0)), 1),
            "storm_speed_mps": 0.0,
            "storm_dir_deg": 0.0,
            "bullseye_lowpoint": False,
            "network_variant": int(k % network_variants),
            "drain_eff": round(float(rng.uniform(1.25, 1.40)) if dry
                               else float(rng.uniform(1.30, 1.45)), 3),
            "blockage_level": 0.0,
            "blockage_mode": "pipe_uniform",
            "terrain_jitter_m": 0.05,
            "terrain_seed": int(seed + 600013 * k),
            "manning_scale": round(float(rng.uniform(0.9, 1.1)), 3),
            "dep_scale": round(float(rng.uniform(0.5, 1.5)), 3),
            "imperv_open": round(float(rng.uniform(0.25, 0.45)), 3),
            "recession_h": round(float(rng.choice([1.0, 1.5, 2.0])), 2),
            "dataset_version": DATASET_VERSION,
        })
    order = np.arange(len(specs))
    rng.shuffle(order)
    quota = (["train"] * split_quota[0] + ["val"] * split_quota[1]
             + ["test"] * split_quota[2])
    assert len(quota) == len(specs), "topup quota must match suite size"
    for pos, k in enumerate(order):
        specs[k]["ml_split"] = quota[pos]
    return specs


def make_longdry_suite(n=48, seed=77791, split_quota=(34, 7, 7),
                       network_variants=N_NETWORK_VARIANTS):
    """Long, low-rainfall scenarios for full 0-3h lead windows.

    Window-level analysis showed short scenarios (T<42 steps) cannot support
    +180 min targets and only 0.2% of train windows are no-flood. These
    3.5-6 h drizzle/light scenarios (T=42-84) yield full-lead windows that are
    mostly no-flood/minor. IDs at 20000+; ml_split per quota.
    """
    rng = np.random.default_rng(seed)
    specs = []
    for k in range(n):
        specs.append({
            "scenario_idx": 20000 + k,
            "seed": int(seed + 700001 * k),
            "split": "topup2",
            "rain_class": "trace+topup:longdry" if k % 2 == 0 else "light+topup:longdry",
            "edge_case": "topup_longdry",
            "temporal": str(rng.choice(["uniform", "front_loaded", "back_loaded"])),
            "spatial": str(rng.choice(["uniform", "gradient", "gaussian_cell"])),
            "duration_h": round(float(rng.uniform(3.5, 6.0)), 3),
            "total_mm": round(float(rng.uniform(3.0, 12.0)) if k % 2 == 0
                              else float(rng.uniform(12.0, 25.0)), 2),
            "storm_sigma_m": round(float(rng.uniform(80.0, 150.0)), 1),
            "storm_speed_mps": 0.0,
            "storm_dir_deg": 0.0,
            "bullseye_lowpoint": False,
            "network_variant": int(k % network_variants),
            "drain_eff": round(float(rng.uniform(1.2, 1.4)), 3),
            "blockage_level": 0.0,
            "blockage_mode": "pipe_uniform",
            "terrain_jitter_m": 0.05,
            "terrain_seed": int(seed + 800011 * k),
            "manning_scale": round(float(rng.uniform(0.9, 1.1)), 3),
            "dep_scale": round(float(rng.uniform(0.5, 1.5)), 3),
            "imperv_open": round(float(rng.uniform(0.25, 0.45)), 3),
            "recession_h": round(float(rng.choice([0.5, 1.0])), 2),
            "dataset_version": DATASET_VERSION,
        })
    order = np.arange(len(specs))
    rng.shuffle(order)
    quota = (["train"] * split_quota[0] + ["val"] * split_quota[1]
             + ["test"] * split_quota[2])
    assert len(quota) == len(specs)
    for pos, k in enumerate(order):
        specs[k]["ml_split"] = quota[pos]
    return specs
