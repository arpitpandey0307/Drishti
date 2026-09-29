"""Motion estimation (optical flow) and semi-Lagrangian extrapolation for radar nowcasting.

Dense pyramidal Lucas-Kanade on log-transformed rain fields (as pysteps' `lucaskanade` +
`semilagrangian`, re-implemented in NumPy/SciPy because pysteps has no Python 3.14 wheel).
Motion is in pixels per step, as (vy, vx) with +vy pointing to increasing row index (south).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, zoom


def to_log(R, thr=0.1):
    """Rain rate -> dBR (zero rain mapped to a floor just below the threshold)."""
    R = np.nan_to_num(np.asarray(R, float), nan=0.0)
    floor = 10 * np.log10(thr) - 5.0
    return np.where(R >= thr, 10 * np.log10(np.maximum(R, thr)), floor), floor


def warp(field, V, cval=None):
    """Sample field at x - V (backward warp by displacement V = (vy, vx) arrays)."""
    ny, nx = field.shape
    ii, jj = np.mgrid[0:ny, 0:nx].astype(float)
    return map_coordinates(field, [ii - V[0], jj - V[1]], order=1, mode="nearest" if cval is None else "constant",
                           cval=0.0 if cval is None else cval)


def _lk(I0, I1, sigma):
    Iy, Ix = np.gradient(0.5 * (I0 + I1))
    It = I1 - I0
    g = lambda a: gaussian_filter(a, sigma)
    Sxx, Syy, Sxy = g(Ix * Ix), g(Iy * Iy), g(Ix * Iy)
    Sxt, Syt = g(Ix * It), g(Iy * It)
    det = Sxx * Syy - Sxy ** 2
    ok = det > 1e-6 * np.maximum((Sxx + Syy) ** 2, 1e-12)
    d = np.where(ok, det, 1.0)
    vx = np.where(ok, -(Syy * Sxt - Sxy * Syt) / d, 0.0)
    vy = np.where(ok, -(Sxx * Syt - Sxy * Sxt) / d, 0.0)
    w = np.where(ok, np.sqrt(np.maximum(det, 0)), 0.0)
    return vy, vx, w


def dense_motion(frames, levels=3, sigma=4.0, smooth_px=6.0, iters=3):
    """Motion field (2, ny, nx) in px/step from >= 2 consecutive log-rain frames (oldest first).

    Pairwise pyramidal LK, averaged over pairs, confidence-weighted, then gap-filled with the
    confidence-weighted mean and smoothed so rain-free areas carry the large-scale flow."""
    frames = [np.asarray(f, float) for f in frames]
    ny, nx = frames[0].shape
    acc = np.zeros((2, ny, nx)); wacc = np.zeros((ny, nx))
    for I0, I1 in zip(frames[:-1], frames[1:]):
        V = np.zeros((2, ny, nx))
        for lev in range(levels - 1, -1, -1):
            s = 2 ** lev
            if s > 1:
                a, b = zoom(I0, 1 / s, order=1), zoom(I1, 1 / s, order=1)
                Vs = np.stack([zoom(V[k], (a.shape[0] / ny, a.shape[1] / nx), order=1) / s for k in (0, 1)])
            else:
                a, b, Vs = I0, I1, V.copy()
            for _ in range(iters):
                b_w = warp(b, -Vs)                       # align I1 back onto I0 with current estimate
                vy, vx, w = _lk(a, b_w, sigma)
                Vs = Vs + np.stack([vy, vx])
            V = np.stack([zoom(Vs[k], (ny / Vs.shape[1], nx / Vs.shape[2]), order=1) * s for k in (0, 1)])
            V = V[:, :ny, :nx]
        _, _, w = _lk(I0, warp(I1, -V), sigma)
        acc += V * w; wacc += w
    wsum = wacc.sum()
    mean = acc.reshape(2, -1).sum(1) / max(wsum, 1e-12)
    # normalised convolution: local confidence-weighted mean, falling back to global mean
    sm = max(smooth_px, 1.0)
    num = np.stack([gaussian_filter(acc[k], sm) for k in (0, 1)])
    den = gaussian_filter(wacc, sm)
    alpha = den / (den + 0.05 * wacc.max() + 1e-12)
    V = alpha * num / np.maximum(den, 1e-12) + (1 - alpha) * mean[:, None, None]
    return V


def trajectories(V, n_steps):
    """Backward displacement fields D_k (k = 1..n) for semi-Lagrangian advection:
    field(t + k)(x) = field(t)(x - D_k(x)); D follows the (spatially varying) motion."""
    ny, nx = V.shape[1:]
    ii, jj = np.mgrid[0:ny, 0:nx].astype(float)
    D = np.zeros_like(V)
    out = []
    for _ in range(n_steps):
        # midpoint rule: velocity at the half-step departure point
        pi, pj = ii - D[0] - 0.5 * V[0], jj - D[1] - 0.5 * V[1]
        v = np.stack([map_coordinates(V[k], [pi, pj], order=1, mode="nearest") for k in (0, 1)])
        D = D + v
        out.append(D.copy())
    return out


def advect(field, D, fill=0.0):
    """field(x - D) with values outside the grid set to `fill` (no rain enters from outside)."""
    return warp(field, D, cval=fill)
