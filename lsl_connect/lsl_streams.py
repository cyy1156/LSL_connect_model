"""
第 5 课：LSL StreamInfo / Outlet 工厂与 chunk 推送。
流名称与需求文档 §7.4 一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple,Optional,Sequence

import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock

# 需求文档 §7.4
EEG_STREAM_NAME = "OpenBCI_EEG"
EEG_STREAM_TYPE = "EEG"
EEG_SOURCE_ID_CYTON = "openbci_cyton_8ch"
EEG_SOURCE_ID_SYNTHETIC = "openbci_synthetic_eeg"

ACCEL_STREAM_NAME = "OpenBCI_Accel"
ACCEL_STREAM_TYPE = "ACC"
ACCEL_SOURCE_ID = "openbci_cyton_accel"

DEFAULT_EEG_LABELS = ["Fp1", "Fp2", "C3", "C4", "P7", "P8", "O1", "O2"]

class BoardToLslTimestampMapper:
    """
        把 BrainFlow 板卡时间戳（秒）映射到 LSL 的 local_clock 时间轴。
        第一次见到的板卡时间会对齐到当时的 local_clock()，之后只加固定偏移。
    """
    def __init__(self) -> None:
        self._offset:Optional[float] = None

    def reset(self) -> None:
        """断开板卡后调用，下次连接重新对齐。"""
        self._offset = None

    def to_local_clock(self,board_timestamps: np.ndarray) -> List[float]:
        ts =np.asarray(board_timestamps,dtype=np.float64).reshape(-1)
        if ts.size == 0:
            return []

        if self._offset is None:

            self._offset = float(local_clock() -ts[-1])
        return (ts+self._offset).tolist()
    def to_lsl_uniform(
        self,
        board_timestamps: np.ndarray,
        sample_rate: int = 250,
    ) -> List[float]:
        """
        若一批内板卡时间几乎相同，则按 sample_rate 生成等间隔 LSL 时间；
        否则仍用板卡时间逐点映射。
        """
        ts = np.asarray(board_timestamps, dtype=np.float64).reshape(-1)
        n = ts.size
        if n == 0:
            return []

        dt = 1.0 / float(sample_rate)
        span = float(ts[-1] - ts[0])
        # 跨度小于“应有跨度”的一半 → 认为板卡戳退化，用等间隔
        expected = (n - 1) * dt if n > 1 else 0.0

        if n == 1 or span < expected * 0.5:
            lsl_end = self.to_local_clock(ts[-1:])[0]
            return [lsl_end - (n - 1 - i) * dt for i in range(n)]

        return self.to_local_clock(ts)
@dataclass
class LslStreamConfig:
  sample_rate: int = 250
  channel_count: int = 8
  use_synthetic: bool = False
  eeg_labels: List[str] | None = None


def create_eeg_outlet(config: LslStreamConfig | None = None) -> StreamOutlet:
    """创建 EEG LSL Outlet。"""
    if config is None:
        config = LslStreamConfig()

    source_id = (
        EEG_SOURCE_ID_SYNTHETIC if config.use_synthetic else EEG_SOURCE_ID_CYTON
    )
    info = StreamInfo(
        name=EEG_STREAM_NAME,
        type=EEG_STREAM_TYPE,
        channel_count=config.channel_count,
        nominal_srate=config.sample_rate,
        channel_format="float32",
        source_id=source_id,
    )

    channels_desc = info.desc().append_child("channels")
    labels = config.eeg_labels or DEFAULT_EEG_LABELS
    for i in range(config.channel_count):
        label = labels[i] if i < len(labels) else f"Ch{i + 1}"
        ch = channels_desc.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")

    return StreamOutlet(info)


def create_accel_outlet(sample_rate: int = 250) -> StreamOutlet:
    """创建加速度计 LSL Outlet（3 通道）。"""
    info = StreamInfo(
        name=ACCEL_STREAM_NAME,
        type=ACCEL_STREAM_TYPE,
        channel_count=3,
        nominal_srate=sample_rate,
        channel_format="float32",
        source_id=ACCEL_SOURCE_ID,
    )
    return StreamOutlet(info)


def create_outlets(
    config: LslStreamConfig | None = None,
) -> Tuple[StreamOutlet, StreamOutlet]:
    """同时创建 EEG + Accel Outlet。"""
    if config is None:
        config = LslStreamConfig()
    return create_eeg_outlet(config), create_accel_outlet(config.sample_rate)


def push_eeg_chunk(outlet: StreamOutlet, eeg_data: np.ndarray,timepstamps:Optional[Sequence[float]] =None) -> int:
    """
    推送 EEG chunk。eeg_data: (n_channels, n_samples)，单位 µV。
    返回本批样本数。
    eeg_data 是 (8 通道, 25 时间)。
    .T 变成 (25 行, 8 列)，才符合 pylsl「一行一个时刻」。
    push_chunk 调用 1 次 = 1 个 chunk = 25 个 sample 一起上网。
    """
    n_samples = eeg_data.shape[1]
    if timepstamps is None:
        ts_list =[local_clock() for _ in range(n_samples)]

    else:
        ts_list=list(timepstamps)
        if len(ts_list) != n_samples:
            raise ValueError(
                f"timestamps 长度 {len(ts_list)} 与样本数 {n_samples} 不一致"
            )
    chunk = np.ascontiguousarray(eeg_data.T, dtype=np.float32)
    outlet.push_chunk(chunk, ts_list)
    return n_samples


def push_accel_chunk(
    outlet: StreamOutlet,
    accel_data: np.ndarray,
    timestamps: Optional[Sequence[float]] = None,
) -> None:
    """推送加速度 chunk。accel_data: (3, n_samples)。"""
    n_samples = accel_data.shape[1]
    if timestamps is None:
        ts_list = [local_clock() for _ in range(n_samples)]
    else:
        ts_list = list(timestamps)
        if len(ts_list) != n_samples:
            raise ValueError(
                f"timestamps 长度 {len(ts_list)} 与样本数 {n_samples} 不一致"
            )

    chunk = np.ascontiguousarray(accel_data.T, dtype=np.float32)
    outlet.push_chunk(chunk, ts_list)