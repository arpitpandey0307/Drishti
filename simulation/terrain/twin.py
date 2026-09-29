"""Terrain intelligence engine (SRS Module D): the gridded digital twin of the pilot area.

Builds a regular metric grid (row 0 = north) around the configured centre and derives:
DEM, slope, D8 flow direction + accumulation, depressions (priority-flood fill), land cover
(roads / buildings / open), Manning roughness, imperviousness and the model domain mask.

Grid convention (shared with the web viewers):
    X[i, j] = (j - (nx-1)/2) * dx      metres east of centre
    Y[i, j] = ((ny-1)/2 - i) * dx      metres north of centre
"""
from __future__ import annotations

import heapq
import json
import os

import numpy as np

M_PER_DEG_LAT = 111320.0
# D8 neighbour offsets (di, dj) and their distances in cells
D8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
D8_DIST = np.array([1, 2 ** 0.5, 1, 2 ** 0.5, 1, 2 ** 0.5, 1, 2 ** 0.5])


# ---------------------------------------------------------------- geometry helpers
def _points_in_polygon(px, py, ring):
    """Vectorised even-odd ray casting. px/py: flat arrays, ring: (N,2) array."""
    inside = np.zeros(px.shape, bool)
    x, y = ring[:, 0], ring[:, 1]
    xj, yj = np.roll(x, 1), np.roll(y, 1)
    for k in range(len(ring)):
        cond = (y[k] > py) != (yj[k] > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj[k] - x[k]) * (py - y[k]) / (yj[k] - y[k]) + x[k]
        inside ^= cond & (px < xint)
    return inside


def _dist_to_segments(px, py, segs):
    """Min distance from points to a set of segments (S,4 array x0,y0,x1,y1)."""
    best = np.full(px.shape, np.inf)
    for x0, y0, x1, y1 in segs:
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = np.zeros_like(px) if L2 == 0 else np.clip(((px - x0) * dx + (py - y0) * dy) / L2, 0, 1)
        d = np.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
        np.minimum(best, d, out=best)
    return best


def _fill_nans(grid):
    """Fill NaN cells by inverse-distance weighting from valid cells."""
    g = grid.copy()
    ok = np.isfinite(g)
    if ok.all():
        return g
    ii, jj = np.indices(g.shape)
    vi, vj, vv = ii[ok], jj[ok], g[ok]
    for i, j in zip(*np.where(~ok)):
        d2 = (vi - i) ** 2 + (vj - j) ** 2
        w = 1.0 / (d2 ** 1.5)
        g[i, j] = float((w * vv).sum() / w.sum())
    return g


def priority_flood(dem, domain):
    """Barnes et al. (2014) priority-flood depression filling. Cells outside `domain`
    are ignored; domain-edge cells are the seeds (water leaves over the edge)."""
    ny, nx = dem.shape
    filled = np.where(domain, dem, np.nan).astype(float)
    done = ~domain.copy()
    pq = []
    for i in range(ny):
        for j in range(nx):
            if not domain[i, j]:
                continue
            edge = i in (0, ny - 1) or j in (0, nx - 1) or any(
                not domain[i + di, j + dj] for di, dj in D8
                if 0 <= i + di < ny and 0 <= j + dj < nx)
            if edge:
                heapq.heappush(pq, (filled[i, j], i, j))
                done[i, j] = True
    while pq:
        z, i, j = heapq.heappop(pq)
        for di, dj in D8:
            a, b = i + di, j + dj
            if 0 <= a < ny and 0 <= b < nx and not done[a, b]:
                done[a, b] = True
                filled[a, b] = max(filled[a, b], z)
                heapq.heappush(pq, (filled[a, b], a, b))
    return np.where(domain, filled, dem)


def d8_flow(dem_filled, domain, dx):
    """D8 steepest-descent direction (index into D8, -1 = outlet/flat) and accumulation
    (number of upstream cells incl. itself). Flats on the filled surface are resolved with
    a tiny gradient towards lower raw neighbours so every cell drains."""
    ny, nx = dem_filled.shape
    fdir = np.full((ny, nx), -1, int)
    # epsilon gradient: add distance-to-edge ordering so flats drain outward
    z = dem_filled.copy()
    for i in range(ny):
        for j in range(nx):
            if not domain[i, j]:
                continue
            best, bk = 0.0, -1
            for k, (di, dj) in enumerate(D8):
                a, b = i + di, j + dj
                if not (0 <= a < ny and 0 <= b < nx) or not domain[a, b]:
                    continue
                s = (z[i, j] - z[a, b]) / (D8_DIST[k] * dx)
                if s > best:
                    best, bk = s, k
            fdir[i, j] = bk
    # flats: point towards any equal-height neighbour that already has a direction (BFS)
    changed = True
    while changed:
        changed = False
        for i, j in zip(*np.where((fdir == -1) & domain)):
            for k, (di, dj) in enumerate(D8):
                a, b = i + di, j + dj
                if (0 <= a < ny and 0 <= b < nx and domain[a, b] and fdir[a, b] != -1
                        and abs(z[a, b] - z[i, j]) < 1e-9):
                    fdir[i, j] = k
                    changed = True
                    break
    # accumulation: process cells from highest to lowest
    acc = np.where(domain, 1.0, 0.0)
    order = np.argsort(-np.where(domain, z, -np.inf), axis=None)
    for flat in order:
        i, j = divmod(int(flat), nx)
        if not domain[i, j] or fdir[i, j] < 0:
            continue
        di, dj = D8[fdir[i, j]]
        acc[i + di, j + dj] += acc[i, j]
    return fdir, acc


# ---------------------------------------------------------------- twin
class Twin:
    """Gridded terrain + land-cover twin. Construct from `config/terrain.yaml`."""

    def __init__(self, cfg, root="."):
        d = cfg["domain"]
        self.cfg = cfg
        self.nx, self.ny, self.dx = int(d["nx"]), int(d["ny"]), float(d["dx_m"])
        self.lat0, self.lon0 = float(d["centre_lat"]), float(d["centre_lon"])
        self.m_per_deg_lon = M_PER_DEG_LAT * np.cos(np.deg2rad(self.lat0))
        jj, ii = np.meshgrid(np.arange(self.nx), np.arange(self.ny))
        self.X = (jj - (self.nx - 1) / 2.0) * self.dx
        self.Y = ((self.ny - 1) / 2.0 - ii) * self.dx
        self.lat = self.lat0 + self.Y / M_PER_DEG_LAT
        self.lon = self.lon0 + self.X / self.m_per_deg_lon
        p = lambda rel: os.path.join(root, rel)

        self._build_dem(p(cfg["dem_source"]["file"]), seed=int(cfg.get("micro_relief_seed", 26085)),
                        relief_m=float(cfg.get("micro_relief_m", 0.15)))
        self._build_landcover(cfg, p)
        self._build_hydrology_grids(cfg)
        self.meta = {
            "crs_calc": d.get("crs_calc"), "crs_store": d.get("crs_store"),
            "vertical_datum": cfg["dem_source"].get("vertical_datum", "EGM2008"),
            "resolution_m": self.dx, "native_resolution_m": cfg["dem_source"]["native_res_m"],
            "vertical_accuracy_m": cfg["dem_source"]["accuracy_m"],
            "dem_kind": cfg["dem_source"]["kind"],
            "data_tier": cfg["dem_source"].get("tier", 1),
            "data_tier_label": cfg["dem_source"].get(
                "tier_label", "Tier 1 - public/coarse (30 m DSM, upsampled)"),
            "provenance": "derived",
            "bounds_latlon": [[float(self.lat.min()), float(self.lon.min())],
                              [float(self.lat.max()), float(self.lon.max())]],
        }

    # -- coordinates
    def ll_to_xy(self, lat, lon):
        return ((np.asarray(lon) - self.lon0) * self.m_per_deg_lon,
                (np.asarray(lat) - self.lat0) * M_PER_DEG_LAT)

    def xy_to_ij(self, x, y):
        j = np.rint(np.asarray(x) / self.dx + (self.nx - 1) / 2.0).astype(int)
        i = np.rint((self.ny - 1) / 2.0 - np.asarray(y) / self.dx).astype(int)
        return i, j

    # -- DEM
    def _build_dem(self, path, seed, relief_m):
        g = json.load(open(path))
        rows = g["rows"]
        lats = np.array([r[0]["lat"] for r in rows])
        lons = np.array([c["lon"] for c in rows[0]])
        z = np.array([[np.nan if c["elevation_m"] is None else c["elevation_m"] for c in r]
                      for r in rows], float)
        self.dem_source_valid_cells = int(np.isfinite(z).sum())
        z = _fill_nans(z)
        # bilinear interpolation of the coarse grid at every fine cell (clamped at edges)
        fi = np.interp(self.lat, lats[::-1], np.arange(len(lats))[::-1])  # lats descend
        fj = np.interp(self.lon, lons, np.arange(len(lons)))
        i0 = np.clip(np.floor(fi).astype(int), 0, len(lats) - 2)
        j0 = np.clip(np.floor(fj).astype(int), 0, len(lons) - 2)
        ti, tj = fi - i0, fj - j0
        dem = (z[i0, j0] * (1 - ti) * (1 - tj) + z[i0 + 1, j0] * ti * (1 - tj)
               + z[i0, j0 + 1] * (1 - ti) * tj + z[i0 + 1, j0 + 1] * ti * tj)
        rng = np.random.default_rng(seed)
        noise = rng.normal(0, 1, dem.shape)
        # smooth the noise (3x3 box, twice) so micro-relief is spatially coherent
        for _ in range(2):
            pad = np.pad(noise, 1, mode="edge")
            noise = sum(pad[1 + a:1 + a + self.ny, 1 + b:1 + b + self.nx]
                        for a in (-1, 0, 1) for b in (-1, 0, 1)) / 9.0
        noise = noise / (noise.std() + 1e-9) * relief_m
        self.dem = dem + noise

    # -- land cover
    def _build_landcover(self, cfg, p):
        lc = cfg["landcover"]
        px, py = self.X.ravel(), self.Y.ravel()
        ring = lambda coords: np.array([self.ll_to_xy(la, lo) for lo, la in coords])

        # domain = campus boundary polygon (closed model domain)
        bnd = json.load(open(p(lc["boundary_source"])))["features"][0]["geometry"]
        dom = np.zeros(px.shape, bool)
        polys = bnd["coordinates"] if bnd["type"] == "MultiPolygon" else [bnd["coordinates"]]
        for poly in polys:
            dom |= _points_in_polygon(px, py, ring(poly[0]))
        self.in_domain = dom.reshape(self.ny, self.nx)

        bsrc = p(lc["building_source"])
        if not os.path.exists(bsrc):
            bsrc = p("data/campus.geojson")
        bld = np.zeros(px.shape, bool)
        for f in json.load(open(bsrc))["features"]:
            g = f["geometry"]
            if g["type"] == "Polygon" and "building" in str(f["properties"].get("kind", "building")):
                bld |= _points_in_polygon(px, py, ring(g["coordinates"][0]))
        self.is_building = bld.reshape(self.ny, self.nx) & self.in_domain

        segs = []
        for f in json.load(open(p(lc["road_source"])))["features"]:
            g = f["geometry"]
            if f["properties"].get("highway") in ("footway", "steps", "path"):
                continue
            lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
            for line in lines:
                xy = ring(line)
                segs += [(*xy[k], *xy[k + 1]) for k in range(len(xy) - 1)]
        road_d = _dist_to_segments(px, py, segs).reshape(self.ny, self.nx)
        self.is_road = (road_d <= float(lc["road_halfwidth_m"])) & self.in_domain & ~self.is_building
        self.is_open = self.in_domain & ~self.is_building & ~self.is_road
        # 0 = road, 1 = open, 2 = building / outside
        self.cell_class = np.where(self.is_road, 0, np.where(self.is_open, 1, 2))

    # -- hydrology grids
    def _build_hydrology_grids(self, cfg):
        h = cfg["hydrology_defaults"]
        self.manning = np.where(self.is_road, h["manning_road"],
                                np.where(self.is_building, h["manning_building"], h["manning_open"]))
        self.imperv = np.where(self.is_road | self.is_building, 1.0, h["imperv_open"])
        gy, gx = np.gradient(self.dem, self.dx)
        self.slope = np.hypot(gx, gy)                        # m/m
        self.slope_deg = np.degrees(np.arctan(self.slope))
        self.wet = self.in_domain & ~self.is_building        # cells that carry surface water
        self.dem_filled = priority_flood(self.dem, self.wet)
        self.depression_depth = np.where(self.wet, self.dem_filled - self.dem, 0.0)
        self.flowdir, acc = d8_flow(self.dem_filled, self.wet, self.dx)
        self.accum = np.where(self.in_domain, np.maximum(acc, 1.0), 0.0)
        thr = float(cfg.get("low_point_min_depth_m", 0.02))
        top = np.quantile(self.accum[self.wet], 0.9) if self.wet.any() else np.inf
        self.low_points = self.wet & ((self.depression_depth > thr) | (self.accum >= top))

    def summary(self):
        return {
            "shape": [self.ny, self.nx], "dx_m": self.dx,
            "in_domain_cells": int(self.in_domain.sum()), "road_cells": int(self.is_road.sum()),
            "building_cells": int(self.is_building.sum()), "low_point_cells": int(self.low_points.sum()),
            "dem_range_m": [float(self.dem[self.in_domain].min()), float(self.dem[self.in_domain].max())],
            "max_depression_m": float(self.depression_depth.max()),
            **self.meta,
        }
