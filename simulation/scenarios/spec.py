"""Scenario specs + blockage sampler."""
import numpy as np

BLOCKAGE_LEVELS = [0.0, 0.10, 0.25, 0.50, 0.75, 0.90]

def make_suite(n, seed, rainfall_cfg, network_variants=3):
    rng = np.random.default_rng(seed)
    specs = []
    for k in range(n):
        dur = float(rng.uniform(rainfall_cfg["duration_h"]["min"], rainfall_cfg["duration_h"]["max"]))
        specs.append({
            "id": k, "seed": int(seed + k * 101),
            "temporal": str(rng.choice(rainfall_cfg["temporal_profiles"])),
            "spatial": str(rng.choice(rainfall_cfg["spatial_patterns"])),
            "duration_h": dur,
            "total_mm": float(rng.uniform(rainfall_cfg["total_mm"]["min"], rainfall_cfg["total_mm"]["max"])),
            "network_variant": int(k % network_variants),
            "blockage_level": float(rng.choice(BLOCKAGE_LEVELS)),
            "blockage_mode": str(rng.choice(["pipe_uniform", "inlet_subset", "outfall_restricted"])),
        })
    return specs
