"""Diffusive-wave storage-cell surface solver (Bates & De Roo 2000 style).

h[t+1] = h + dt*(R - I)/3600 - dt*drain/3600 + dt*(Qin-Qout)/A
Inter-cell flux: q = (h_flow^(5/3)/n) * sqrt(S) * dx  (Manning, wide-channel R~h)
"""
import numpy as np

def step_surface(h, dem, manning, rain_mmh, infil_mmh, drain_ms, dx, dt, h_min=0.0, blocked=None):
    """drain_ms: drainage sink in m/s (positive = leaving surface).
    blocked: bool array (buildings + outside domain) acting as no-flow walls."""
    """drain_ms: drainage sink in m/s (positive = leaving surface)."""
    ny, nx = h.shape
    ws = dem + h
    qE = np.zeros_like(h); qS = np.zeros_like(h)
    S_CAP = 0.05  # DSM-noise guard: 30m DSM steps are not real channel slopes
    # east faces
    hf = np.maximum(ws[:, :-1], ws[:, 1:]) - np.maximum(dem[:, :-1], dem[:, 1:])
    hf = np.clip(hf, 0, None)
    S = np.minimum(np.abs(ws[:, :-1] - ws[:, 1:]) / dx, S_CAP)
    n = np.maximum((manning[:, :-1] + manning[:, 1:]) / 2, 1e-3)
    q = hf ** (5.0 / 3.0) / n * np.sqrt(np.maximum(S, 1e-8)) * dx
    sgn = np.sign(ws[:, :-1] - ws[:, 1:])
    q = q * sgn
    qE[:, :-1] = q
    # south faces
    hf = np.maximum(ws[:-1, :], ws[1:, :]) - np.maximum(dem[:-1, :], dem[1:, :])
    hf = np.clip(hf, 0, None)
    S = np.minimum(np.abs(ws[:-1, :] - ws[1:, :]) / dx, S_CAP)
    n = np.maximum((manning[:-1, :] + manning[1:, :]) / 2, 1e-3)
    q = hf ** (5.0 / 3.0) / n * np.sqrt(np.maximum(S, 1e-8)) * dx
    sgn = np.sign(ws[:-1, :] - ws[1:, :])
    qS[:-1, :] = q * sgn
    if blocked is not None:
        # buildings / outside-domain are walls: kill fluxes touching them
        bE = blocked[:, :-1] | blocked[:, 1:]
        qE[:, :-1] = np.where(bE, 0.0, qE[:, :-1])
        bS = blocked[:-1, :] | blocked[1:, :]
        qS[:-1, :] = np.where(bS, 0.0, qS[:-1, :])
    # --- explicit-diffusion stability limiter (Bates & De Roo 2000 style):
    # no face may move more than 1/4 of the upwind cell volume in one step.
    hE_up = np.where(qE[:, :-1] > 0, h[:, :-1], h[:, 1:])
    qmaxE = 0.125 * np.maximum(hE_up, 0) * dx * dx / max(dt, 1e-9)
    qE[:, :-1] = np.clip(qE[:, :-1], -qmaxE, qmaxE)
    hS_up = np.where(qS[:-1, :] > 0, h[:-1, :], h[1:, :])
    qmaxS = 0.125 * np.maximum(hS_up, 0) * dx * dx / max(dt, 1e-9)
    qS[:-1, :] = np.clip(qS[:-1, :], -qmaxS, qmaxS)
    # net inflow (m3/s per cell). Sign convention: qE>0 = flow left->right,
    # so the LEFT cell loses and the RIGHT cell gains (and same N->S for qS).
    Qin = np.zeros_like(h)
    Qin[:, :-1] -= qE[:, :-1]; Qin[:, 1:] += qE[:, :-1]
    Qin[:-1, :] -= qS[:-1, :]; Qin[1:, :] += qS[:-1, :]
    # NOTE: no cell-net rescaling here — scaling outflow without scaling the
    # neighbour's matching inflow creates mass and blows up. Per-face limits
    # above (1/8 vol each, max 1/2 vol total) guarantee stability conservatively.
    dh = dt * (rain_mmh - infil_mmh) / 3600.0 / 1000.0 - dt * drain_ms + dt * Qin / (dx * dx)
    h2 = np.maximum(h + dh, 0.0)
    h2 = np.where(h2 < h_min, 0.0, h2)
    vel = np.zeros_like(h)
    with np.errstate(divide="ignore", invalid="ignore"):
        vE = np.abs(qE) / np.maximum(hf.mean() if False else 1.0, 1e-9)
    # cheap velocity proxy for ML features
    vmag = np.abs(Qin) / np.maximum(np.maximum(h2, h) * dx, 1e-9)
    vel = np.clip(np.nan_to_num(vmag, nan=0.0, posinf=0.0, neginf=0.0), 0, 3.0)
    return h2, vel, Qin
