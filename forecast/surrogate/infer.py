"""ONNX Runtime inference for the flood surrogate (one forward pass per ensemble member)."""
from __future__ import annotations

import json
import os

import numpy as np

from .features import build_inputs, static_stack, uncrop


class FloodSurrogate:
    def __init__(self, model_path, meta_path, twin, threads=None):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"{model_path} missing — train it with "
                                    "`python -m forecast.surrogate.dataset` then `python -m forecast.surrogate.train`")
        import onnxruntime as ort
        so = ort.SessionOptions()
        if threads:
            so.intra_op_num_threads = int(threads)
        self.sess = ort.InferenceSession(model_path, so, providers=["CPUExecutionProvider"])
        self.meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
        self.twin = twin
        self.static = static_stack(twin)
        self.lead_min = self.meta.get("inputs", {}).get("lead_min")

    def predict(self, rain_hist_mm, depth_hist, fut_rain_mm, blockage=0.0, batch=10):
        """-> (M, L, ny, nx) depth (m) on the full twin grid."""
        x = build_inputs(self.static, rain_hist_mm, depth_hist, fut_rain_mm, blockage)
        out = [self.sess.run(None, {"input": x[i:i + batch]})[0] for i in range(0, x.shape[0], batch)]
        return uncrop(np.maximum(np.concatenate(out), 0.0), self.twin.dem.shape)
