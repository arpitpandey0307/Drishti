"""Regional (radar-scale) grid centred on the campus, and sampling onto the campus twin grid.

Row 0 = north, like `simulation.terrain.twin.Twin`. Coordinates are km east / north of the
campus centre, so the twin's X/Y (metres from the same centre) map directly.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates


class RegionalGrid:
    def __init__(self, cfg):
        g = cfg["regional_grid"]
        self.nx, self.ny, self.dx = int(g["nx"]), int(g["ny"]), float(g["dx_km"])
        jj, ii = np.meshgrid(np.arange(self.nx), np.arange(self.ny))
        self.X = (jj - (self.nx - 1) / 2.0) * self.dx      # km east
        self.Y = ((self.ny - 1) / 2.0 - ii) * self.dx      # km north

    @property
    def shape(self):
        return (self.ny, self.nx)

    def xy_to_frac_ij(self, x_km, y_km):
        """Fractional pixel indices (i, j) of km coordinates."""
        return ((self.ny - 1) / 2.0 - np.asarray(y_km) / self.dx,
                np.asarray(x_km) / self.dx + (self.nx - 1) / 2.0)

    def nearest_ij(self, x_km, y_km):
        fi, fj = self.xy_to_frac_ij(x_km, y_km)
        return (np.clip(np.rint(fi).astype(int), 0, self.ny - 1),
                np.clip(np.rint(fj).astype(int), 0, self.nx - 1))

    def sample(self, field, x_km, y_km):
        """Bilinear sample of a regional field (..., ny, nx) at km coordinates."""
        fi, fj = self.xy_to_frac_ij(x_km, y_km)
        coords = np.stack([np.ravel(fi), np.ravel(fj)])
        field = np.asarray(field)
        flat = field.reshape((-1,) + field.shape[-2:])
        out = np.stack([map_coordinates(f, coords, order=1, mode="nearest") for f in flat])
        return out.reshape(field.shape[:-2] + np.shape(fi))

    def to_campus(self, field, twin):
        """Regional field (..., ny, nx) -> campus twin grid (..., twin.ny, twin.nx).

        Radar pixels are ~1 km, the campus is < 1 km across: the sampled field is smooth
        and cannot resolve sub-kilometre rain structure (stated in the provenance)."""
        return self.sample(field, twin.X / 1000.0, twin.Y / 1000.0)
