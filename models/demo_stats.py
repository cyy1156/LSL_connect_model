"""
第 10 课：演示模型 — 打印窗口内全通道均值/标准差。
"""

from __future__ import annotations

from typing import Any,Dict

import numpy as np

from models.base import ModelPlugin

class DemoStatsModel(ModelPlugin):
    name="demo"
    window_size = 250
    hop_size = 125

    def load(self) ->None:
        pass

    def predict(self,data: np.ndarray) ->Dict[str,float]:
        return {
            #算数平均值
            "mean_uv": float(np.mean(data)),
           #方差
            "std_uv": float(np.std(data)),
            "n_ch": float(data.shape[0]),
            "n_samples": float(data.shape[1]),
        }
