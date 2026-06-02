"""
第 7 课：服务管理器 — 状态机 + AcquisitionWorker。
第 8 课 CLI 将调用本模块。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lsl_connect.acquisition_work import AcquisitionConfig, AcquisitionWorker
from lsl_connect.eeg_labels import labels_from_text, validate_eeg_channel_labels
from lsl_connect.board import BoardConfig
from lsl_connect.lsl_streams import DEFAULT_EEG_LABELS, LslStreamConfig
from lsl_connect.model_worker import ModelWorker, ModelWorkerConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.recorder_worker import RecorderWorker, RecorderWorkerConfig
from lsl_connect.recording_config import RecordingConfig, make_recording_path
from lsl_connect.recording_quality import (
    RecordingStopReport,
    compute_recording_quality,
    patch_meta_quality,
)
from lsl_connect.state import (
    ServiceState,
    can_transition,
    may_reset,
    may_start,
    may_stop,
)
from models import create_plugin, get_model_registry
from models.registry import ModelSpec


def format_board_error(exc: Exception, board_cfg: BoardConfig) -> str:
    """将 BrainFlow 连接错误转成可操作的中文提示。"""
    raw = str(exc)
    port = board_cfg.serial_port
    if "UNABLE_TO_OPEN_PORT" in raw or "unable to prepare" in raw.lower():
        if board_cfg.use_synthetic:
            return f"合成板启动失败: {raw}"
        return (
            f"无法打开串口 {port}（BrainFlow: {raw}）。\n"
            f"常见原因：① 串口号不对 ② 上次采集未释放 COM（请先停止采集并等待 1–2 秒）\n"
            f"③ OpenBCI GUI 正占用 CYTON Serial 模式 ④ USB 松动。当前配置串口: {port}"
        )
    return raw


@dataclass
class ServiceManagerConfig:
    """ServiceManager 持有的默认配置（第 9 课可改为从 YAML 加载）。"""

    board_config: BoardConfig
    lsl: LslStreamConfig
    preprocess: PreprocessConfig
    acquisition: AcquisitionConfig
    recording: RecordingConfig = field(default_factory=RecordingConfig)


class ServiceManager:
    """
    管理采集服务生命周期。

    用法:
        mgr = ServiceManager()
        mgr.start_acquisition()
        print(mgr.get_status())
        mgr.stop_acquisition()
    """

    def __init__(
        self,
        config: Optional[ServiceManagerConfig] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        if config is None:
            board = BoardConfig(use_synthetic=True, cyton_eeg_count=8)
            config = ServiceManagerConfig(
                board_config=board,
                lsl=LslStreamConfig(
                    sample_rate=250,
                    channel_count=board.cyton_eeg_count,
                    use_synthetic=board.use_synthetic,
                    eeg_labels=list(DEFAULT_EEG_LABELS[: board.cyton_eeg_count]),
                ),
                preprocess=PreprocessConfig(sample_rate=250),
                acquisition=AcquisitionConfig(),
                recording=RecordingConfig(),
            )
        self._config = config

        self._lock = threading.Lock()
        self._state = ServiceState.IDLE
        self._worker: Optional[AcquisitionWorker] = None
        self._recorder: Optional[RecorderWorker] = None
        self._rec_pushed_baseline: int = 0
        self._rec_started_at: Optional[float] = None
        self._last_recording_report: Optional[RecordingStopReport] = None
        self._last_error: Optional[str] = None
        self._model_workers: dict[str, ModelWorker] = {}
        self._model_specs, self._models_msg = get_model_registry()
        self._event_bus = event_bus

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
            self._log_info("采集已启动 → RUNNING")
            if self._config.recording.auto_start:
                ok, msg = self.start_recording()
                if ok:
                    self._log_info(msg)
                else:
                    self._log_warn(f"自动录制未启动: {msg}")
            return True
        except Exception as exc:
            msg = format_board_error(exc, self._config.board_config)
            self._last_error = msg
            self._log_error(f"采集启动失败: {msg}")
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
        if self._config.recording.stop_when_acquisition_stops:
            self._stop_recording_internal()
        self.stop_all_models()

        worker = None
        with self._lock:
            worker = self._worker
            self._worker = None

        if worker is not None:
            try:
                worker.stop()
            except Exception as exc:
                self._last_error = str(exc)

        # Windows 上串口释放后稍等再允许下一次 open
        if not self._config.board_config.use_synthetic:
            time.sleep(0.35)

        self._set_state(ServiceState.IDLE)
        self._log_info("采集已停止 → IDLE")
        return True

    def _log_info(self, msg: str) -> None:
        if self._event_bus is not None:
            self._event_bus.info(msg)

    def _log_warn(self, msg: str) -> None:
        if self._event_bus is not None:
            self._event_bus.warn(msg)

    def _log_error(self, msg: str) -> None:
        if self._event_bus is not None:
            self._event_bus.error(msg)

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

        rec = self.get_recording_status()
        return {
            "state": state.value,
            "serial_port": port,
            "use_synthetic": board_cfg.use_synthetic,
            "serial_port_raw": board_cfg.serial_port,
            "gui_streaming_enabled": board_cfg.gui_streaming_enabled,
            "sample_rate_hz": self._config.preprocess.sample_rate,
            "channel_count": self._config.lsl.channel_count,
            "samples_pushed": samples,
            "filter_enabled": self._config.preprocess.filter_enabled,
            "last_error": error,
            "worker_running": worker.is_running if worker else False,
            "recording_active": rec.get("active", False),
            "recording_path": rec.get("path"),
            "recording_samples": rec.get("samples_written", 0),
            "eeg_channel_labels": self.get_eeg_channel_labels(),
        }

    def get_eeg_channel_labels(self) -> List[str]:
        n = self._config.lsl.channel_count
        labels = list(self._config.lsl.eeg_labels or DEFAULT_EEG_LABELS[:n])
        if len(labels) < n:
            labels = list(DEFAULT_EEG_LABELS[:n])
        return labels[:n]

    def set_eeg_channel_labels(
        self,
        labels: List[str] | str,
    ) -> tuple[bool, str]:
        """仅 IDLE：设置 CH1…CHn 显示名（= LSL / CSV 列名）。"""
        with self._lock:
            if self._state != ServiceState.IDLE:
                return False, "仅 IDLE 可修改通道名称，请先停止采集"
            n = self._config.lsl.channel_count

        if isinstance(labels, str):
            parsed = labels_from_text(labels, n)
        else:
            parsed = [str(x).strip() for x in labels]

        ok, err = validate_eeg_channel_labels(parsed, n)
        if not ok:
            return False, err

        with self._lock:
            self._config.lsl.eeg_labels = parsed

        return True, f"通道名已更新: {', '.join(parsed)}（下次开始采集生效）"

    def get_config(self) -> ServiceManagerConfig:
        return self._config

    def get_board_settings(self) -> Dict[str, Any]:
        bc = self._config.board_config
        return {
            "use_synthetic": bc.use_synthetic,
            "serial_port": bc.serial_port,
            "gui_streaming_enabled": bc.gui_streaming_enabled,
            "gui_stream_ip": bc.gui_stream_ip,
            "gui_stream_port": bc.gui_stream_port,
            "filter_enabled": self._config.preprocess.filter_enabled,
        }

    def get_recording_settings(self) -> Dict[str, Any]:
        r = self._config.recording
        return {
            "auto_start": r.auto_start,
            "output_dir": r.output_dir,
            "file_prefix": r.file_prefix,
            "stop_when_acquisition_stops": r.stop_when_acquisition_stops,
        }

    def set_recording_auto_start(self, enabled: bool) -> tuple[bool, str]:
        with self._lock:
            if self._state != ServiceState.IDLE:
                return False, "仅 IDLE 可修改录制选项"
            self._config.recording.auto_start = enabled
        label = "ON" if enabled else "OFF"
        return True, f"采集时自动录制已设为 {label}"

    def set_recording_output_dir(self, directory: str) -> tuple[bool, str]:
        with self._lock:
            if self._state != ServiceState.IDLE:
                return False, "仅 IDLE 可修改保存目录"
            self._config.recording.output_dir = directory.strip()
        return True, f"录制保存目录: {directory.strip()}"

    def get_recording_status(self) -> Dict[str, Any]:
        if self._recorder is not None:
            return self._recorder.get_stats()
        return {"active": False, "path": None, "samples_written": 0}

    def start_recording(self, path: Optional[str] = None) -> tuple[bool, str]:
        if self.get_state() != ServiceState.RUNNING:
            return False, "请先 start 采集（RUNNING）后再录制"

        if self._recorder is not None and self._recorder.is_running:
            return False, "已在录制中，请先 record stop"

        explicit = Path(path) if path else None
        csv_path = make_recording_path(self._config.recording, explicit)

        labels = self.get_eeg_channel_labels()

        meta = {
            "sample_rate_hz": self._config.preprocess.sample_rate,
            "channel_count": self._config.lsl.channel_count,
            "filtered": self._config.preprocess.filter_enabled,
            "use_synthetic": self._config.board_config.use_synthetic,
            "serial_port": self._config.board_config.serial_port,
            "csv_file": str(csv_path),
        }

        rec_cfg = RecorderWorkerConfig(
            flush_interval_sec=self._config.recording.flush_interval_sec,
            lsl_buffer_sec=self._config.recording.lsl_buffer_sec,
            sample_rate_hz=self._config.preprocess.sample_rate,
        )
        worker = RecorderWorker(
            config=rec_cfg,
            on_error=self._log_error,
        )
        try:
            worker.start(csv_path, channel_labels=labels, meta=meta)
        except Exception as exc:
            return False, str(exc)

        self._recorder = worker
        self._rec_pushed_baseline = int(self.get_status().get("samples_pushed", 0))
        self._rec_started_at = time.time()
        self._last_recording_report = None
        msg = f"录制已开始 → {csv_path}"
        self._log_info(msg)
        return True, msg

    def get_last_recording_report(self) -> Optional[RecordingStopReport]:
        return self._last_recording_report

    def stop_recording(self) -> tuple[bool, str, Optional[RecordingStopReport]]:
        return self._stop_recording_internal()

    def _stop_recording_internal(self) -> tuple[bool, str, Optional[RecordingStopReport]]:
        worker = self._recorder
        if worker is None or not worker.is_running:
            self._recorder = None
            return False, "当前未在录制", None

        try:
            result = worker.stop()
        except Exception as exc:
            self._recorder = None
            return False, str(exc), None

        self._recorder = None
        n = int(result.get("samples_written", 0) or 0)
        p = result.get("path") or "?"
        gaps = int(result.get("estimated_gap_samples", 0) or 0)
        pushed_now = int(self.get_status().get("samples_pushed", 0))

        report = compute_recording_quality(
            samples_written=n,
            samples_pushed_baseline=self._rec_pushed_baseline,
            samples_pushed_now=pushed_now,
            estimated_gap_samples=gaps,
            sample_rate_hz=self._config.preprocess.sample_rate,
            started_at=self._rec_started_at,
            csv_path=p,
        )
        self._last_recording_report = report
        if p:
            patch_meta_quality(p, report.to_dict())

        msg = (
            f"录制已停止，共 {n} 行 → {p}\n"
            f"推送 {report.samples_pushed_during} / 缺口 {report.missing_vs_lsl} / "
            f"丢包率 {report.drop_rate_pct:.2f}%"
        )
        if report.severity == "bad":
            self._log_warn(msg)
        elif report.severity == "warn":
            self._log_warn(msg)
        else:
            self._log_info(msg)

        self._rec_pushed_baseline = 0
        self._rec_started_at = None
        return True, msg, report

    def set_board_mode(
        self,
        use_synthetic: bool,
        serial_port: Optional[str] = None,
    ) -> tuple[bool, str]:
        """仅 IDLE：切换合成板 / 真机。"""
        with self._lock:
            if self._state != ServiceState.IDLE:
                return False, "仅 IDLE 可切换数据源，请先停止采集"
            self._config.board_config.use_synthetic = use_synthetic
            self._config.lsl.use_synthetic = use_synthetic
            if serial_port is not None:
                self._config.board_config.serial_port = serial_port.strip()
        if use_synthetic:
            return True, "数据源已设为合成板（下次 start 生效）"
        port = self._config.board_config.serial_port
        return True, f"数据源已设为真机 {port}（下次 start 生效）"

    def set_gui_streaming_enabled(self, enabled: bool) -> tuple[bool, str]:
        """仅 IDLE：开关 BrainFlow UDP 推流（供 OpenBCI GUI STREAMING）。"""
        with self._lock:
            if self._state != ServiceState.IDLE:
                return False, "仅 IDLE 可改 GUI 推流，请先 stop"
            self._config.board_config.gui_streaming_enabled = enabled
        label = "ON" if enabled else "OFF"
        return True, f"GUI 推流已设为 {label}（下次 start 生效）"

    def set_serial_port(self, port: str) -> tuple[bool, str]:
        """仅 IDLE 可改串口；自动切到真机模式。"""
        return self.set_board_mode(False, port)

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
        running = self.get_running_models()
        if running:
            lines.append(f"[模型] 运行中: {', '.join(running)}")
        else:
            lines.append("[模型] 无")
        rec = self.get_recording_status()
        if rec.get("active"):
            lines.append(
                f"[录制] ON  |  {rec.get('path')}  |  samples={rec.get('samples_written', 0)}"
            )
        else:
            lines.append("[录制] OFF")
        return "\n".join(lines)

    def set_filter_enabled(self, enabled: bool) -> tuple[bool, str]:
        """RUNNING 时改预处理开关，下一批生效。"""
        with self._lock:
            if self._state != ServiceState.RUNNING:
                return False, "仅 RUNNING 可 config filter"
            self._config.preprocess.filter_enabled = enabled
        label = "ON" if enabled else "OFF"
        return True, f"滤波已设为 {label}（下一批生效）"

    def shutdown(self) -> None:
        """quit 时：先停录制与模型，再停采集。"""
        if self._recorder is not None and self._recorder.is_running:
            self._stop_recording_internal()
        self.stop_all_models()
        if may_stop(self.get_state()):
            self.stop_acquisition()

    def get_models_message(self) -> str:
        """models.yaml 加载说明。"""
        return self._models_msg

    def get_model_specs(self) -> dict[str, ModelSpec]:
        """name -> ModelSpec（含说明、窗口等）。"""
        return dict(self._model_specs)

    def list_models(self) -> list[str]:
        """已登记模型名（来自 models.yaml）。"""
        return sorted(self._model_specs.keys())

    def start_model(self, name: str) -> tuple[bool, str]:
        """
        启动模型 worker。仅 RUNNING 且 LSL 流已存在时允许。
        返回 (成功与否, 说明)。
        """
        name = name.strip()
        if self.get_state() != ServiceState.RUNNING:
            return False, "请先 start 采集，等 status 为 RUNNING 后再 model start"

        if name in self._model_workers:
            return False, f"模型 {name} 已在运行"

        spec = self._model_specs.get(name)
        if spec is None:
            return False, f"未登记模型: {name}，可用 model list 查看"

        try:
            plugin = create_plugin(spec)
            worker_cfg = ModelWorkerConfig(silent=self._event_bus is not None)
            worker = ModelWorker(
                plugin,
                config=worker_cfg,
                on_result=self._make_on_result(name),
                on_error=self._make_on_error(name),
            )
            worker.start()
            self._model_workers[name] = worker
            self._log_info(f"模型 {name} 已启动")
            if self._event_bus is not None:
                self._event_bus.clear_model_error(name)
            return True, f"模型 {name} 已启动"
        except Exception as exc:
            if self._event_bus is not None:
                self._event_bus.set_model_error(name, str(exc))
            return False, str(exc)

    def _make_on_result(self, name: str):
        bus = self._event_bus

        def _cb(raw: Any) -> None:
            if bus is not None:
                bus.push_model_result(name, raw)

        return _cb

    def _make_on_error(self, name: str):
        bus = self._event_bus

        def _cb(msg: str) -> None:
            if bus is not None:
                bus.set_model_error(name, msg)
                bus.error(f"[模型/{name}] {msg}")

        return _cb

    def start_models(self, names: list[str]) -> list[tuple[str, bool, str]]:
        """批量启动模型，返回 [(name, ok, msg), ...]。"""
        results: list[tuple[str, bool, str]] = []
        for name in names:
            ok, msg = self.start_model(name)
            results.append((name, ok, msg))
        return results

    def stop_model(self, name: str) -> tuple[bool, str]:
        name = name.strip()
        worker = self._model_workers.pop(name, None)
        if worker is None:
            return False, f"模型 {name} 未在运行"
        try:
            worker.stop()
        except Exception as exc:
            return False, str(exc)
        self._log_info(f"模型 {name} 已停止")
        return True, f"模型 {name} 已停止"

    def stop_all_models(self) -> None:
        """停止所有 model worker（stop 采集 / quit 时调用）。"""
        for name in list(self._model_workers.keys()):
            self.stop_model(name)

    def get_running_models(self) -> list[str]:
        return sorted(self._model_workers.keys())
