"""
第 5 课：EEG / 加速度预处理（缩放 + 可选滤波）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from brainflow.data_filter import DataFilter, FilterTypes

# Cyton：ADC 计数 -> 微伏 (uV)
SCALE_EEG = 4_500_000 / 24 / (2**23 - 1)

# 加速度计原始值 -> m/s^2（按 BrainFlow / OpenBCI 常用换算）
SCALE_ACCEL = 0.002 / (2**4)


@dataclass
class PreprocessConfig:
    """预处理开关与滤波参数。"""

    sample_rate: int = 250
    filter_enabled: bool = True
    bandpass_low_hz: float = 0.5
    bandpass_high_hz: float = 45.0
    notch_low_hz: float = 49.0
    notch_high_hz: float = 51.0
    filter_order: int = 2


def counts_to_microvolts(eeg_counts: np.ndarray) -> np.ndarray:
    """将 EEG 原始计数转为微伏。输入/输出形状: (n_channels, n_samples)。"""
    return eeg_counts.astype(np.float64) * SCALE_EEG


def counts_to_accel_ms2(accel_counts: np.ndarray) -> np.ndarray:
    """将加速度计原始计数转为 m/s^2。形状: (3, n_samples)。"""
    return accel_counts.astype(np.float64) * SCALE_ACCEL


def apply_eeg_filters(
    eeg_uv: np.ndarray,
    config: PreprocessConfig | None = None,
) -> None:
    """
    原地滤波。eeg_uv 形状必须为 (n_channels, n_samples)。
    """
    if config is None:
        config = PreprocessConfig()
    if not config.filter_enabled:
        return

    n_ch, _ = eeg_uv.shape
    for ch in range(n_ch):
        DataFilter.perform_bandpass(
            eeg_uv[ch],
            config.sample_rate,
            config.bandpass_low_hz,
            config.bandpass_high_hz,
            config.filter_order,
            FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
            0,
        )
        DataFilter.perform_bandstop(
            eeg_uv[ch],
            config.sample_rate,
            config.notch_low_hz,
            config.notch_high_hz,
            config.filter_order,
            FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
            0,
        )


def preprocess_eeg_batch(
    eeg_counts: np.ndarray,
    config: PreprocessConfig | None = None,
) -> np.ndarray:
    """
    计数 -> 微伏 -> 可选滤波，返回 float32 数组 (n_channels, n_samples)。
    """
    if config is None:
        config = PreprocessConfig()
    eeg_uv = counts_to_microvolts(eeg_counts)
    apply_eeg_filters(eeg_uv, config)
    return eeg_uv.astype(np.float32)


def preprocess_accel_batch(accel_counts: np.ndarray) -> np.ndarray:
    """加速度计数 -> m/s^2，返回 float32 (3, n_samples)。"""
    return counts_to_accel_ms2(accel_counts).astype(np.float32)