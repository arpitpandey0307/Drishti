"""Rainfall nowcast engine (SRS Module C): STEPS-style stochastic ensemble.

  radar frames (gauge-bias corrected)
    -> dBR transform -> optical flow (motion.py)
    -> Lagrangian alignment of the last 3 frames
    -> FFT band-pass cascade (n levels) with per-level AR(2) evolution (scale-dependent
       predictability: small scales decorrelate first)
    -> per-member stochastic noise (non-parametric spectral filter of the latest field)
       + per-member motion perturbation
    -> probability matching to the observed rain distribution
    -> semi-Lagrangian extrapolation
    -> blending with NWP guidance (or climatology) for 60-180 min (FR-C03)
Member 0 is the unperturbed control (S-PROG-like smoothed mean advection).

Follows Bowler, Pierce & Seed (2006) and Seed et al. (2013) / pysteps, re-implemented
because pysteps has no Python 3.14 wheel.
"""
from __future__ import annotations

import csv

import numpy as np

from .motion import advect, dense_motion, to_log, trajectories


# ----------------------------------------------------------------- gauge correction
def mean_field_bias(radar_at_gauges, gauge_mm, step_min, cfg):
    """Mean-field bias B = sum(gauge) / sum(radar) over paired VALID reports.

    radar_at_gauges, gauge_mm : lists of equal length (rates mm/h, 5-min accumulations mm).
    Returns (B, n_pairs, applied)."""
    gb = cfg["nowcast"]["gauge_bias"]
    r = np.asarray(radar_at_gauges, float) * step_min / 60.0
    g = np.asarray(gauge_mm, float)
    ok = np.isfinite(r) & np.isfinite(g) & ((r > 0.05) | (g > 0.05))
    n = int(ok.sum())
    # light rain is dominated by tipping-bucket quantisation (0.2 mm): require real totals
    if n < gb["min_pairs"] or min(r[ok].sum(), g[ok].sum()) < float(gb.get("min_total_mm", 2.0)):
        return 1.0, n, False
    B = float(np.clip(g[ok].sum() / max(r[ok].sum(), 1e-9), *gb["clip"]))
    return B, n, True


def gauge_field(points, grid, step_min=5.0, power=2.0, radius_km=25.0):
    """IDW interpolation of gauge 5-min accumulations -> rain-rate field (mm/h). Pixels
    farther than `radius_km` from every gauge get NaN (unknown, not dry)."""
    if not points:
        return np.full(grid.shape, np.nan, np.float32)
    x = np.array([p["x_km"] for p in points]); y = np.array([p["y_km"] for p in points])
    v = np.array([p["rain_mm"] for p in points]) * 60.0 / step_min
    d = np.sqrt((grid.X[..., None] - x) ** 2 + (grid.Y[..., None] - y) ** 2)
    w = 1.0 / np.maximum(d, 0.5) ** power
    f = (w * v).sum(-1) / w.sum(-1)
    return np.where(d.min(-1) <= radius_km, f, np.nan).astype(np.float32)


# ----------------------------------------------------------------- climatology
class Climatology:
    """Monsoon wet-day rainfall climatology from the local daily CSV (derived).

    Used as the long-lead fallback when no NWP guidance is available: a wet-day total spread
    over `effective_duration_h` gives a climatological hourly rate distribution."""

    def __init__(self, cfg, root="."):
        c = cfg["climatology"]
        vals = []
        with open(f"{root}/{c['daily_csv']}", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    m, v = int(r["date"][5:7]), float(r["rainfall_mm"])
                except (ValueError, KeyError):
                    continue
                if m in c["months"] and v >= c["wet_day_mm"]:
                    vals.append(v)
        self.daily = np.sort(np.array(vals)) if vals else np.array([10.0])
        self.dur = float(c["effective_duration_h"])
        self.source = c["daily_csv"]

    def rate_quantile(self, q):
        return float(np.quantile(self.daily, q)) / self.dur

    def describe(self):
        return {"source": self.source, "wet_days": int(self.daily.size), "provenance": "derived",
                "rate_p50_mmh": round(self.rate_quantile(0.5), 2), "rate_p90_mmh": round(self.rate_quantile(0.9), 2)}


# ----------------------------------------------------------------- cascade
def cascade_filters(shape, n_levels):
    ny, nx = shape
    ky = np.fft.fftfreq(ny) * ny; kx = np.fft.fftfreq(nx) * nx
    K = np.sqrt(ky[:, None] ** 2 + kx[None, :] ** 2)
    kmax = max(ny, nx) / 2.0
    centres = np.geomspace(1.0, kmax, n_levels)
    logk = np.log(np.maximum(K, 0.5))
    width = (np.log(kmax) / max(n_levels - 1, 1))
    W = np.array([np.exp(-0.5 * ((logk - np.log(c)) / width) ** 2) for c in centres])
    W[0][K < 1.0] = 1.0            # mean / largest scales in the first level
    return W / W.sum(0, keepdims=True)


def decompose(field, W):
    F = np.fft.fft2(field)
    return np.real(np.fft.ifft2(W * F[None]))


def _ar2(g1, g2):
    g1 = float(np.clip(g1, 0.01, 0.999)); g2 = float(np.clip(g2, -0.99, 0.999))
    phi2 = (g2 - g1 ** 2) / (1 - g1 ** 2)
    phi2 = float(np.clip(phi2, -0.9, 0.9))
    phi1 = g1 * (1 - phi2)
    var = (1 + phi2) * ((1 - phi2) ** 2 - phi1 ** 2) / (1 - phi2)
    if var <= 1e-6:            # non-stationary estimate -> fall back to AR(1)
        phi1, phi2, var = g1, 0.0, 1 - g1 ** 2
    return phi1, phi2, float(np.sqrt(max(var, 1e-6)))


def _noise_filter(field_db, floor):
    """Amplitude spectrum of the (tapered) latest field, for non-parametric noise."""
    ny, nx = field_db.shape
    taper = np.outer(np.hanning(ny), np.hanning(nx))
    a = np.abs(np.fft.fft2((field_db - field_db.mean()) * taper))
    a[0, 0] = 0.0
    return a / max(np.sqrt((a ** 2).mean()), 1e-12)


def _prob_match(field, target_sorted):
    """Replace values of `field` by the target distribution, keeping the field's ranks."""
    order = np.argsort(field, axis=None)
    out = np.empty(field.size)
    out[order] = target_sorted
    return out.reshape(field.shape)


# ----------------------------------------------------------------- nowcaster
class StepsNowcaster:
    def __init__(self, cfg, grid):
        self.cfg, self.grid = cfg, grid
        self.nc = cfg["nowcast"]
        self.step = float(cfg["step_min"])
        self.W = cascade_filters(grid.shape, int(self.nc["n_cascade_levels"]))

    def blend_weight(self, lead_min, degraded=False):
        pts = sorted((float(k), float(v)) for k, v in self.nc["blend_weight"].items())
        w = float(np.interp(lead_min, [p[0] for p in pts], [p[1] for p in pts]))
        if degraded:
            w *= float(self.nc["degraded"]["weight_factor"])
        return w

    def run(self, frames, n_steps, members=None, seed=0, motion=None, nwp=None, clim=None,
            degraded=False):
        """frames: >= 3 rain-rate fields (mm/h) oldest first, spaced by `step_min`, already
        bias corrected. motion: optional (2, ny, nx) px/step override (e.g. last good radar
        motion in gauge-only mode). nwp: (n_steps, ny, nx) mm/h guidance or None.
        Returns dict with members (M, n_steps, ny, nx) mm/h and diagnostics."""
        M = int(members or self.nc["members"])
        thr = float(self.nc["rain_threshold_mmh"])
        rng = np.random.default_rng(seed)
        L = [to_log(f, thr) for f in frames[-3:]]
        floor = L[0][1]
        dB = [l[0] for l in L]
        V = dense_motion(dB, smooth_px=float(self.nc["motion_smooth_px"])) if motion is None else motion
        # Lagrangian alignment of t-2, t-1 onto t
        D = trajectories(V, 2)
        a2 = advect(dB[0], D[1], fill=floor)
        a1 = advect(dB[1], D[0], fill=floor)
        a0 = dB[2]
        wet_now = a0 > floor + 1e-6
        lead_min = self.step * np.arange(1, n_steps + 1)
        noise_fac = float(self.nc["degraded"]["noise_factor"]) if degraded else 1.0
        # long-lead guidance: NWP if available, else climatology
        if nwp is not None:
            guide, guide_src = np.asarray(nwp, float), "nwp"
        else:
            guide, guide_src = None, "climatology"
        diag = {"motion_mean_px_per_step": [float(V[0].mean()), float(V[1].mean())],
                "motion_speed_kmh": float(np.hypot(V[0].mean(), V[1].mean()) * self.grid.dx * 60 / self.step),
                "wet_fraction_now": float(wet_now.mean()), "guidance": guide_src, "degraded": bool(degraded),
                "blend_weights": {int(l): round(self.blend_weight(l, degraded), 3) for l in (15, 30, 60, 120, 180)
                                  if l <= lead_min[-1]}}
        out = np.zeros((M, n_steps) + self.grid.shape, np.float32)
        if not wet_now.any() and guide is None and clim is None:
            diag["note"] = "no rain observed and no guidance: zero nowcast"
            return {"members": out, "lead_min": lead_min, "motion": V, "diag": diag}

        # cascade statistics + AR(2) parameters per level
        C0, C1, C2 = decompose(a0, self.W), decompose(a1, self.W), decompose(a2, self.W)
        mu, sd = C0.mean((1, 2)), C0.std((1, 2)) + 1e-9
        n0 = (C0 - mu[:, None, None]) / sd[:, None, None]
        n1 = (C1 - C1.mean((1, 2))[:, None, None]) / (C1.std((1, 2)) + 1e-9)[:, None, None]
        n2 = (C2 - C2.mean((1, 2))[:, None, None]) / (C2.std((1, 2)) + 1e-9)[:, None, None]
        g1 = [float((n0[k] * n1[k]).mean()) for k in range(len(mu))]
        g2 = [float((n0[k] * n2[k]).mean()) for k in range(len(mu))]
        ar = [_ar2(a, b) for a, b in zip(g1, g2)]
        diag["ar_lag1_per_level"] = [round(a, 3) for a in g1]
        target = np.sort(a0, axis=None)
        nf = _noise_filter(a0, floor)
        pert_px = float(self.nc["motion_perturb_mps"]) * 60 * self.step / 1000.0 / self.grid.dx

        for m in range(M):
            control = m == 0
            Vm = V if control else V + rng.normal(0, pert_px, 2)[:, None, None]
            Dm = trajectories(Vm, n_steps)
            c_prev, c_cur = n1.copy(), n0.copy()
            if guide is None and clim is not None:
                q = (m + 0.5) / M
                clim_rate = clim.rate_quantile(q) * max(float((dB[2] > floor + 1e-6).mean()), 0.05)
            gpert = None
            if guide is not None:
                z = np.real(np.fft.ifft2(nf * np.fft.fft2(rng.normal(size=self.grid.shape))))
                z = z / (z.std() + 1e-9) * float(self.nc["nwp_spread"])
                gpert = np.exp(z - float(self.nc["nwp_spread"]) ** 2 / 2)
            for k in range(n_steps):
                if control:
                    eps = np.zeros_like(n0)
                else:
                    wn = np.real(np.fft.ifft2(nf * np.fft.fft2(rng.normal(size=self.grid.shape))))
                    eps = decompose(wn, self.W)
                    eps = eps / (eps.std((1, 2), keepdims=True) + 1e-9)
                c_new = np.stack([ar[l][0] * c_cur[l] + ar[l][1] * c_prev[l] + ar[l][2] * noise_fac * eps[l]
                                  for l in range(len(mu))])
                c_prev, c_cur = c_cur, c_new
                f = (c_new * sd[:, None, None] + mu[:, None, None]).sum(0)
                f = _prob_match(f, target)
                f = advect(f, Dm[k], fill=floor)
                R = np.where(f > floor + 1e-6, 10 ** (f / 10.0), 0.0)
                R[R < thr] = 0.0
                w = self.blend_weight(lead_min[k], degraded)
                if w < 1.0:
                    if guide is not None:
                        G = guide[k] * gpert
                    elif clim is not None:
                        G = np.full(self.grid.shape, clim_rate)
                    else:
                        G = R
                    R = w * R + (1 - w) * G
                out[m, k] = R
        diag["members"] = M
        return {"members": out, "lead_min": lead_min, "motion": V, "diag": diag}


def quantile_fields(members, qs=(0.1, 0.5, 0.9)):
    return {f"p{int(q * 100)}": np.quantile(members, q, axis=0).astype(np.float32) for q in qs}
