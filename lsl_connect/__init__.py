"""
lsl_connect — 采集、LSL 广播、控制面板核心包。
第 4 课起在此包内添加 board、acquisition_worker 等模块。
"""

__version__ = "0.1.0"



from lsl_connect.board import BoardConfig,CytonBoard

__all__ = ["BoardConfig","CytonBoard","__version__"]
from lsl_connect.preprocessing import (
    PreprocessConfig,
    SCALE_EEG,
    preprocess_eeg_batch,
    apply_eeg_filters,
)
from lsl_connect.lsl_streams import (
    LslStreamConfig,
    create_eeg_outlet,
    create_accel_outlet,
    create_outlets,
    push_eeg_chunk,
    push_accel_chunk,
)