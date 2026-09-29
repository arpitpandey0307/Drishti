"""Horton + SCS-CN infiltration (EPA SWMM formulations, see source.md)."""
import numpy as np

def horton_capacity(f0, fc, k, t_h):
    return fc + (f0 - fc) * np.exp(-k * t_h)

class Infiltration:
    def __init__(self, method, params, cell_class):
        self.method = method
        self.cls = cell_class  # int array 0=road,1=open,2=building
        self.params = params
        self.t_h = np.zeros_like(cell_class, float)
        if method == "scs_cn":
            cn = np.array(params["scs_cn"])
            lut = {0: cn[0] if isinstance(cn, (list, tuple)) else params["scs_cn"]["road"],
                   1: params["scs_cn"]["open"], 2: params["scs_cn"]["building"]}
            # simpler: expect dict
            d = params["scs_cn"]
            self.cn = np.where(cell_class == 0, d["road"], np.where(cell_class == 1, d["open"], d["building"])).astype(float)
            self.Smax = 25400.0 / self.cn - 254.0  # mm
            self.Pcum = np.zeros_like(self.Smax)
            self.S = self.Smax.copy()

    def step(self, dt_s, rain_mmh):
        dt_h = dt_s / 3600.0
        self.t_h += dt_h
        if self.method == "horton":
            h = self.params["horton"]
            f0 = np.where(self.cls == 0, h["road"]["f0_mmh"], np.where(self.cls == 1, h["open"]["f0_mmh"], 0.0))
            fc = np.where(self.cls == 0, h["road"]["fc_mmh"], np.where(self.cls == 1, h["open"]["fc_mmh"], 0.0))
            k = np.where(self.cls == 0, h["road"]["k_per_h"], 2.5)
            cap = horton_capacity(f0, fc, k, self.t_h)
            return np.minimum(cap, rain_mmh)
        else:  # incremental SCS-CN per SWMM/Akan-Houghtalen
            P_before = self.Pcum.copy()
            self.Pcum = self.Pcum + rain_mmh * dt_h
            S1 = np.maximum(self.S, 1e-6)
            F1 = self.Pcum - self.Pcum ** 2 / (self.Pcum + S1 + 1e-9)
            F0 = P_before - P_before ** 2 / (P_before + S1 + 1e-9)
            f = np.clip((F1 - F0) / max(dt_h, 1e-9), 0, rain_mmh)
            return f
