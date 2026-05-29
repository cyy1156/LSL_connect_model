"""
第 6 课：后台采集线程 — BrainFlow → 预处理 → LSL push。
供第 7 课 ServiceManager 调用 start / stop。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
from pylsl import StreamOutlet

from lsl_connect.board import BoardConfig, CytonBoard
from lsl_connect.lsl_streams import (
    BoardToLslTimestampMapper,
    LslStreamConfig,
    create_outlets,
    push_accel_chunk,
    push_eeg_chunk,
)
from lsl_connect.preprocessing import (
    PreprocessConfig,
    preprocess_accel_batch,
    preprocess_eeg_batch,
)


@dataclass
class AcquisitionConfig:
    """采集循环参数（对应 eeg_broadcaster 的 BUFFER_SIZE 等）。"""

    buffer_size: int = 25  # 单批最多处理样本数
    loop_sleep_sec: float = 0.005
    stats_every_n_batches: int = 20


class AcquisitionWorker:
    """
    在独立线程中运行采集循环。

    用法:
        worker = AcquisitionWorker()
        worker.start()
        print(worker.get_samples_pushed())
        worker.stop()
    """

    def __init__(
        self,
        board_config: Optional[BoardConfig] = None,
        lsl_config: Optional[LslStreamConfig] = None,
        preprocess_config: Optional[PreprocessConfig] = None,
        acq_config: Optional[AcquisitionConfig] = None,
    ) -> None:
        self._board_config = board_config or BoardConfig(use_synthetic=True)
        self._lsl_config = lsl_config or LslStreamConfig(
            sample_rate=250,
            channel_count=self._board_config.cyton_eeg_count,
            use_synthetic=self._board_config.use_synthetic,
        )

        self._preprocess_config = preprocess_config or PreprocessConfig()
        self._acq_config = acq_config or AcquisitionConfig()

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stats_lock = threading.Lock()
        self._samples_pushed = 0
        self._batch_count = 0

        self._board: Optional[CytonBoard] = None
        self._outlet_eeg: Optional[StreamOutlet] = None
        self._outlet_accel: Optional[StreamOutlet] = None
        self._eeg_channel: Optional[np.ndarray] = None
        self._accel_channel: Optional[np.ndarray] = None
        self._ts_channel: Optional[int] = None
        self._ts_mapper = BoardToLslTimestampMapper()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_samples_pushed(self) -> int:
        with self._stats_lock:
            return self._samples_pushed

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("采集线程已在运行")

        self._stop_event.clear()
        with self._stats_lock:
            self._samples_pushed = 0
            self._batch_count = 0

        self._board = CytonBoard(self._board_config)
        self._board.connect()
        eeg, accel, ts = self._board.get_channel_indices()
        self._eeg_channel = eeg
        self._accel_channel = accel
        self._ts_channel = int(ts)

        self._ts_mapper.reset()

        n_eeg = len(self._eeg_channel)
        self._lsl_config.channel_count = n_eeg
        self._lsl_config.use_synthetic = self._board_config.use_synthetic
        self._lsl_config.sample_rate = self._preprocess_config.sample_rate
        self._outlet_eeg, self._outlet_accel = create_outlets(self._lsl_config)

        self._thread = threading.Thread(
            target=self._run_loop,
            name="AcquisitionWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            if self._thread.is_alive():
                print("[警告] 采集线程未在超时内结束")
            self._thread = None

        if self._board is not None:
            self._board.disconnect()
            self._board = None

        self._ts_mapper.reset()
        self._outlet_eeg = None
        self._outlet_accel = None

    def _run_loop(self) -> None:
        assert self._board is not None
        assert self._outlet_eeg is not None
        assert self._outlet_accel is not None
        assert self._eeg_channel is not None
        assert self._accel_channel is not None
        assert self._ts_channel is not None

        cfg = self._acq_config
        fs = self._preprocess_config.sample_rate
        print("-" * 50)
        print("AcquisitionWorker 运行中... 调用 stop() 结束")
        print(
            f"拉数: fetch_new_batch | 单批上限: {cfg.buffer_size} | "
            f"滤波: {'ON' if self._preprocess_config.filter_enabled else 'OFF'}"
        )
        print("-" * 50)

        while not self._stop_event.is_set():
            data = self._board.fetch_new_batch(cfg.buffer_size)
            if data.shape[1] == 0:
                time.sleep(cfg.loop_sleep_sec)
                continue

            board_ts = data[self._ts_channel, :]
            lsl_ts = self._ts_mapper.to_lsl_uniform(board_ts, fs)

            eeg_counts = data[self._eeg_channel, :]
            eeg_uv = preprocess_eeg_batch(eeg_counts, self._preprocess_config)
            n = push_eeg_chunk(
                self._outlet_eeg,
                eeg_uv,
                timepstamps=lsl_ts,
            )

            with self._stats_lock:
                self._samples_pushed += n
                self._batch_count += 1
                batch_count = self._batch_count
                total = self._samples_pushed

            accel_ch = self._accel_channel
            if len(accel_ch) > 0 and int(accel_ch[0]) < data.shape[0]:
                accel_count = data[accel_ch, :]
                accel_ms2 = preprocess_accel_batch(accel_count)
                push_accel_chunk(
                    self._outlet_accel,
                    accel_ms2,
                    timestamps=lsl_ts,
                )

            if batch_count % cfg.stats_every_n_batches == 0:
                print(f"[统计] 已累计推送约 {total} 个 EEG 样本")

            time.sleep(cfg.loop_sleep_sec)
