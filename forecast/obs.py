"""Multi-source observation layer (SRS Module A): provider-agnostic rainfall adapters.

Every adapter implements `RainfallSource.fetch(t_min) -> Observation`. Grid sources return a
rain-rate field (mm/h) on the regional grid; point sources return gauge reports (5-min
accumulations, mm). An adapter never raises for an unavailable product — it returns an
Observation with status MISSING so the quality engine and degradation logic can react.

  SyntheticRadar     radar mosaic simulated from a StormEvent (bias, noise, outages)  synthetic
  SyntheticGauges    rain gauges simulated from a StormEvent (noise, injectable faults) synthetic
  RadarArchiveReplay archived radar / GPM-IMERG frames replayed from an .npz stack    observed*
  GaugeCSVSource     gauge CSV: time_min|time,station_id,x_km|lat,y_km|lon,rain_mm     observed*
  MosdacDWRSource    MOSDAC Doppler Weather Radar stub (needs credentials)            -
  SyntheticNWP       smoothed, time-shifted "NWP" guidance from the truth               synthetic
  (* provenance as declared by the archive / file)
"""
from __future__ import annotations

import csv
import zlib
import json
from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import gaussian_filter

M_PER_DEG_LAT = 111_320.0


@dataclass
class Observation:
    source: str
    kind: str                       # "radar" | "gauge"
    t_min: float                    # requested valid time
    obs_time_min: float | None      # actual observation time (None when missing)
    provenance: str                 # observed | derived | modelled | synthetic
    grid: np.ndarray | None = None  # radar: rain rate mm/h (ny, nx)
    points: list = field(default_factory=list)  # gauges: [{id, x_km, y_km, t_min, rain_mm}]
    status: str = "VALID"           # set by the adapter only for MISSING; Module B sets the rest
    reasons: list = field(default_factory=list)


class RainfallSource:
    name = "source"
    kind = "radar"
    provenance = "observed"

    def fetch(self, t_min) -> Observation:  # pragma: no cover - interface
        raise NotImplementedError

    def missing(self, t_min, reason):
        return Observation(self.name, self.kind, t_min, None, self.provenance, status="MISSING",
                           reasons=[reason])


class SyntheticRadar(RainfallSource):
    """Radar = truth x Z-R bias x correlated log-normal noise. `outages`: [(t_from, t_to)]
    minutes with no product. `faults`: {t_min: "nan" | "frozen" | "spike"} corrupt one frame."""
    kind, provenance = "radar", "synthetic"

    def __init__(self, event, grid, bias=0.75, noise_sigma=0.25, outages=(), faults=None,
                 latency_min=0.0, seed=1, name="synthetic_radar"):
        self.event, self.grid, self.bias, self.sigma = event, grid, bias, noise_sigma
        self.outages, self.faults, self.latency = list(outages), dict(faults or {}), latency_min
        self.seed, self.name = seed, name
        self._last = None

    def fetch(self, t_min):
        if any(a <= t_min < b for a, b in self.outages):
            return self.missing(t_min, "radar outage")
        t_obs = t_min - self.latency
        rng = np.random.default_rng((self.seed, int(round(t_obs * 10))))
        n = gaussian_filter(rng.normal(size=self.grid.shape), 2.0)
        n = n / (n.std() + 1e-9) * self.sigma
        g = self.event.rate(self.grid, t_obs) * self.bias * np.exp(n - self.sigma ** 2 / 2)
        g = np.where(g < 0.1, 0.0, g)
        f = self.faults.get(t_min)
        if f == "nan":
            g = g.copy(); g[: g.shape[0] * 2 // 3] = np.nan
        elif f == "frozen" and self._last is not None:
            g = self._last.copy()
        elif f == "spike":
            g = g * 40.0
        self._last = g
        return Observation(self.name, "radar", t_min, t_obs, self.provenance, grid=g.astype(np.float32))


DEFAULT_GAUGES = [  # id, km east, km north of campus centre (campus gauge first)
    ("G0-KIET", 0.0, 0.0), ("G1", 6.0, 4.0), ("G2", -7.0, 5.0), ("G3", 3.0, -8.0),
    ("G4", -5.0, -6.0), ("G5", 12.0, -2.0), ("G6", -12.0, 1.0), ("G7", 1.0, 11.0),
]


class SyntheticGauges(RainfallSource):
    """Tipping-bucket gauges: 5-min accumulation of the true rate, 0.2 mm resolution, noise.
    `faults`: {gauge_id: (kind, t_from)} with kind in offline | frozen | spike | negative |
    drift (clock offset in seconds given as a third element) | stuck_zero."""
    kind, provenance = "gauge", "synthetic"

    def __init__(self, event, stations=None, noise=0.1, faults=None, seed=2, name="synthetic_gauges"):
        self.event, self.st = event, list(stations or DEFAULT_GAUGES)
        self.noise, self.faults, self.seed, self.name = noise, dict(faults or {}), seed, name
        self._frozen = {}

    def fetch(self, t_min):
        pts = []
        for gid, x, y in self.st:
            f = self.faults.get(gid)
            kind, active = (f[0], t_min >= f[1]) if f else (None, False)
            if active and kind == "offline":
                continue
            ts = t_min + (f[2] / 60.0 if (active and kind == "drift" and len(f) > 2) else 0.0)
            rate = np.mean([self.event.rate_at(x, y, t_min - s) for s in (0.0, 1.25, 2.5, 3.75)])
            rng = np.random.default_rng((self.seed, zlib.crc32(gid.encode()) % 10_000, int(round(t_min * 10))))
            mm = max(rate * 5 / 60 * (1 + self.noise * rng.normal()), 0.0)
            mm = np.round(mm / 0.2) * 0.2
            if active and kind == "frozen":
                mm = self._frozen.setdefault(gid, max(mm, 1.4))
            elif active and kind == "spike" and abs(t_min - f[1]) < 1e-6:
                mm = 35.0
            elif active and kind == "negative":
                mm = -3.0
            elif active and kind == "stuck_zero":
                mm = 0.0
            pts.append({"id": gid, "x_km": x, "y_km": y, "t_min": ts, "rain_mm": float(mm)})
        return Observation(self.name, "gauge", t_min, t_min, self.provenance, points=pts)


class RadarArchiveReplay(RainfallSource):
    """Replay archived radar / IMERG frames from an .npz with `times_min` (T,), `rate_mmh`
    (T, ny, nx) and optional json `meta` (provenance, product). Returns the latest frame at or
    before t (its age is judged by the quality engine, so a 30-min IMERG cadence shows STALE)."""
    kind = "radar"

    def __init__(self, path, name="archive_replay"):
        z = np.load(path, allow_pickle=False)
        self.times = np.asarray(z["times_min"], float)
        self.frames = np.asarray(z["rate_mmh"], np.float32)
        meta = json.loads(str(z["meta"])) if "meta" in z else {}
        self.provenance = meta.get("provenance", "observed")
        self.name = meta.get("product", name)

    def fetch(self, t_min):
        k = np.searchsorted(self.times, t_min + 1e-6) - 1
        if k < 0:
            return self.missing(t_min, "no archived frame before t")
        return Observation(self.name, "radar", t_min, float(self.times[k]), self.provenance,
                           grid=self.frames[k])

    @staticmethod
    def save(path, source, times_min, product="replay", provenance=None):
        """Archive any radar source (e.g. a synthetic event, or converted IMERG) for replay."""
        frames, ts = [], []
        for t in times_min:
            o = source.fetch(t)
            if o.grid is not None:
                frames.append(o.grid); ts.append(o.obs_time_min)
        meta = {"product": product, "provenance": provenance or source.provenance}
        np.savez_compressed(path, times_min=np.array(ts), rate_mmh=np.array(frames, np.float32),
                            meta=json.dumps(meta))


class GaugeCSVSource(RainfallSource):
    """Sub-daily gauge CSV. Columns: `time_min` (or ISO `time` + origin), `station_id`, and
    either `x_km,y_km` or `lat,lon` (+ campus centre), and `rain_mm` (accumulation over the
    preceding 5 min). Missing station rows simply do not appear (-> MISSING / STALE in QC)."""
    kind = "gauge"

    def __init__(self, path, centre_latlon=None, origin=None, provenance="observed", name="gauge_csv"):
        import datetime as _dt
        self.name, self.provenance = name, provenance
        self.rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if "time_min" in r and r["time_min"] != "":
                    t = float(r["time_min"])
                else:
                    t = (_dt.datetime.fromisoformat(r["time"]) - _dt.datetime.fromisoformat(origin)
                         ).total_seconds() / 60.0
                if r.get("x_km", "") != "":
                    x, y = float(r["x_km"]), float(r["y_km"])
                else:
                    lat0, lon0 = centre_latlon
                    x = (float(r["lon"]) - lon0) * M_PER_DEG_LAT * np.cos(np.deg2rad(lat0)) / 1000
                    y = (float(r["lat"]) - lat0) * M_PER_DEG_LAT / 1000
                v = r.get("rain_mm", "")
                self.rows.append({"id": r["station_id"], "x_km": x, "y_km": y, "t_min": t,
                                  "rain_mm": float(v) if v not in ("", None) else np.nan})

    def fetch(self, t_min, step_min=5.0):
        pts = [dict(r) for r in self.rows if t_min - step_min < r["t_min"] <= t_min + 0.5]
        return Observation(self.name, "gauge", t_min, t_min, self.provenance, points=pts)


class MosdacDWRSource(RainfallSource):
    """MOSDAC (ISRO) Doppler Weather Radar adapter — stub for the Indian deployment pathway.
    A real implementation downloads the DWR reflectivity / rain-rate product for the station
    (e.g. Delhi DWR), reprojects it to the regional grid and converts Z -> R. Level-1 scope has
    no credentials, so it always reports MISSING (and the platform degrades honestly)."""
    kind, provenance, name = "radar", "observed", "mosdac_dwr"

    def __init__(self, station="DELHI", product="DWR_PRECIP", credentials=None):
        self.station, self.product, self.credentials = station, product, credentials

    def fetch(self, t_min):
        return self.missing(t_min, f"MOSDAC DWR adapter not configured ({self.station}/{self.product}: "
                                   "needs MOSDAC credentials)")


class NwpSource:
    name, provenance = "nwp", "modelled"

    def forecast(self, t0_min, leads_min, grid):  # -> (L, ny, nx) mm/h or None
        return None


class SyntheticNWP(NwpSource):
    """Stand-in NWP guidance: truth smoothed to NWP scale, with a timing error and a bias."""
    provenance = "synthetic"

    def __init__(self, event, smooth_km=8.0, time_shift_min=20.0, bias=1.2, name="synthetic_nwp"):
        self.event, self.smooth, self.shift, self.bias, self.name = event, smooth_km, time_shift_min, bias, name

    def forecast(self, t0_min, leads_min, grid):
        return np.array([gaussian_filter(self.event.rate(grid, t0_min + l + self.shift), self.smooth / grid.dx)
                         * self.bias for l in leads_min], np.float32)
