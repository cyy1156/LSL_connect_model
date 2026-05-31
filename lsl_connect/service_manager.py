"""
第 7 课：服务管理器 — 状态机 + AcquisitionWorker。
第 8 课 CLI 将调用本模块。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

from lsl_connect.acquisition_work import AcquisitionConfig, AcquisitionWorker
from lsl_connect.board import BoardConfig
from lsl_connect.lsl_streams import LslStreamConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.state import (
    ServiceState,
    can_transition,
    may_reset,
    may_start,
    may_stop,
)


@dataclass
class ServiceManagerConfig:
    """ServiceManager 持有的默认配置（第 9 课可改为从 YAML 加载）。"""

    board_config: BoardConfig
    lsl: LslStreamConfig
    preprocess: PreprocessConfig
    acquisition: AcquisitionConfig


class ServiceManager:
    """
    管理采集服务生命周期。

    用法:
        mgr = ServiceManager()
        mgr.start_acquisition()
        print(mgr.get_status())
        mgr.stop_acquisition()
    """

    def __init__(self, config: Optional[ServiceManagerConfig] = None) -> None:
        if config is None:
            board = BoardConfig(use_synthetic=True, cyton_eeg_count=8)
            config = ServiceManagerConfig(
                board_config=board,
                lsl=LslStreamConfig(
                    sample_rate=250,
                    channel_count=board.cyton_eeg_count,
                    use_synthetic=board.use_synthetic,
                ),
                preprocess=PreprocessConfig(sample_rate=250),
                acquisition=AcquisitionConfig(),
            )
        self._config = config

        self._lock = threading.Lock()
        self._state = ServiceState.IDLE
        self._worker: Optional[AcquisitionWorker] = None
        self._last_error: Optional[str] = None

    def get_state(self) -> ServiceState:
        with self._lock:
            return self._state

    def _set_state(self, new_state: ServiceState) -> None:
        with self._lock:
            if not can_transition(self._state, new_state):
                raise RuntimeError(
                    f"非法状态转移: {self._state.value} -> {new_state.value}"
                )
            self._state = new_state

    def start_acquisition(self) -> bool:
        """
        启动采集。仅 IDLE 允许。
        成功 → RUNNING；失败 → ERROR。
        """
        with self._lock:
            if not may_start(self._state):
                return False

        self._set_state(ServiceState.STARTING)
        self._last_error = None

        worker: Optional[AcquisitionWorker] = None
        try:
            worker = AcquisitionWorker(
                board_config=self._config.board_config,
                lsl_config=self._config.lsl,
                preprocess_config=self._config.preprocess,
                acq_config=self._config.acquisition,
            )
            worker.start()
            with self._lock:
                self._worker = worker
            self._set_state(ServiceState.RUNNING)
            return True
        except Exception as exc:
            self._last_error = str(exc)
            if worker is not None:
                try:
                    worker.stop()
                except Exception:
                    pass
            with self._lock:
                self._worker = None
            self._set_state(ServiceState.ERROR)
            return False

    def stop_acquisition(self) -> bool:
        """
        停止采集。RUNNING / ERROR 允许。
        成功 → IDLE。
        """
        with self._lock:
            if not may_stop(self._state):
                return False

        self._set_state(ServiceState.STOPPING)

        worker = None
        with self._lock:
            worker = self._worker
            self._worker = None

        if worker is not None:
            try:
                worker.stop()
            except Exception as exc:
                self._last_error = str(exc)

        self._set_state(ServiceState.IDLE)
        return True

    def reset(self) -> bool:
        """ERROR → IDLE（清空错误，不启动采集）。"""
        with self._lock:
            if not may_reset(self._state):
                return False
            self._last_error = None
            self._state = ServiceState.IDLE
        return True

    def get_status(self) -> Dict[str, Any]:
        """供 status 命令 / 测试脚本使用。"""
        with self._lock:
            state = self._state
            worker = self._worker
            error = self._last_error
            board_cfg = self._config.board_config

        samples = worker.get_samples_pushed() if worker is not None else 0
        port = "合成板" if board_cfg.use_synthetic else board_cfg.serial_port

        return {
            "state": state.value,
            "serial_port": port,
            "sample_rate_hz": self._config.preprocess.sample_rate,
            "channel_count": self._config.lsl.channel_count,
            "samples_pushed": samples,
            "filter_enabled": self._config.preprocess.filter_enabled,
            "last_error": error,
            "worker_running": worker.is_running if worker else False,
        }

    def format_status(self) -> str:
        """人类可读的一行/多行状态（类似需求文档 §6.3）。"""
        s = self.get_status()
        lines = [
            f"[服务] {s['state']}  |  {s['serial_port']}  |  "
            f"{s['sample_rate_hz']} Hz  |  {s['channel_count']} ch EEG",
            f"[采集] samples_pushed={s['samples_pushed']}  "
            f"worker_running={s['worker_running']}  "
            f"filter={'ON' if s['filter_enabled'] else 'OFF'}",
        ]
        if s["last_error"]:
            lines.append(f"[错误] {s['last_error']}")
        return "\n".join(lines)
    def set_serial_port(self, port: str) -> tuple[bool, str]:
        """仅 IDLE 可改串口；改后走真机模式。"""
        with self._lock:
            if self._state != ServiceState.IDLE:
                return False,"仅 IDLE可 config port ,请先stop"
            self._config.serial_port = port.strip()
            self._config.cyton_eeg_enabled = False
            return True,f"串口已设为 {port}（下次 start 生效）"

    def set_filter_enabled(self, enabled: bool) -> tuple[bool, str]:
        """RUNNING 时改预处理开关，下一批生效。"""
        with self._lock:
            if self._state != ServiceState.RUNNING:
                return False, "仅 RUNNING 可 config filter"
            self._config.preprocess.filter_enabled = enabled
            label ="ON" if enabled else "OFF"
            return True,f"滤波已设为 {label}（下一批生效）"

    def shutdown(self) -> None:
        """quit 时：若在采集中则先 stop。"""
        if may_stop(self._state()):
            self.stop_acquisition()