"""
第 10 课：模型插件基类。
predict 输入形状: (n_channels, n_samples)，单位 µV。
"""

from __future__ import annotations

from typing import Any

import numpy as np

class ModelPlugin:
    """所有模型插件的基类。"""

    name: str ="base"
    window_size: int =250
    hop_size :int =125 #重叠点数

    def load(self) ->None:
        """加载权重等；演示模型可空实现。"""

    def predict(self,data:np.ndarray) -> Any:
        """
                对一段 EEG 窗口做推理或统计。
                data: (n_channels, n_samples)
         """
        raise NotImplementedError