"""
连接 ServiceManager、EventBus 与 UI 控件。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from lsl_connect.eeg_labels import labels_to_display_text
from lsl_connect.recording_quality import RecordingStopReport
from lsl_connect.config_loader import save_default_config
from lsl_connect.service_manager import ServiceManager
from lsl_connect.state import ServiceState
from lsl_connect.ui.event_bus import EventBus, LogEntry, ModelResult


@dataclass
class UiSnapshot:
    state: ServiceState
    status: Dict[str, Any]
    running_models: List[str]
    latest_results: Dict[str, ModelResult]
    model_errors: Dict[str, str]
    new_logs: List[LogEntry] = field(default_factory=list)


class AppController:
    """UI 事件 → ServiceManager；定时 poll 供界面刷新。"""

    def __init__(
        self,
        manager: ServiceManager,
        event_bus: EventBus,
        config_message: str = "",
        models_message: str = "",
    ) -> None:
        self._mgr = manager
        self._bus = event_bus
        self.config_message = config_message
        self.models_message = models_message

        if config_message:
            self._bus.info(f"[配置] {config_message}")
        if models_message:
            self._bus.info(f"[模型] {models_message}")
        self._bus.info("控制台 UI 已就绪。请先「开始采集」。")

    @property
    def manager(self) -> ServiceManager:
        return self._mgr

    @property
    def bus(self) -> EventBus:
        return self._bus

    def get_model_specs(self):
        return self._mgr.get_model_specs()

    def on_start_acquisition(self) -> tuple[bool, str]:
        if self._mgr.get_state() == ServiceState.ERROR:
            return False, "当前 ERROR，请先重置或停止"
        if self._mgr.start_acquisition():
            return True, "采集已启动"
        err = self._mgr.get_status().get("last_error") or "未知错误"
        return False, err

    def on_stop_acquisition(self) -> tuple[bool, str]:
        if self._mgr.stop_acquisition():
            return True, "采集已停止"
        return False, f"无法停止（当前 {self._mgr.get_state().value}）"

    def on_reset(self) -> tuple[bool, str]:
        if self._mgr.reset():
            self._bus.info("已重置 → IDLE")
            return True, "已重置"
        return False, f"无法重置（当前 {self._mgr.get_state().value}）"

    def on_set_board_mode(self, use_synthetic: bool, port: str) -> tuple[bool, str]:
        ok, msg = self._mgr.set_board_mode(use_synthetic, port if not use_synthetic else None)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_set_gui_streaming(self, enabled: bool) -> tuple[bool, str]:
        ok, msg = self._mgr.set_gui_streaming_enabled(enabled)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_save_config(self) -> tuple[bool, str]:
        ok, msg = save_default_config(self._mgr.get_config())
        if ok:
            self._bus.info(msg)
        else:
            self._bus.error(msg)
        return ok, msg

    def get_board_settings(self) -> Dict[str, Any]:
        return self._mgr.get_board_settings()

    def get_recording_settings(self) -> Dict[str, Any]:
        return self._mgr.get_recording_settings()

    def on_set_recording_auto(self, enabled: bool) -> tuple[bool, str]:
        ok, msg = self._mgr.set_recording_auto_start(enabled)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_set_recording_dir(self, directory: str) -> tuple[bool, str]:
        ok, msg = self._mgr.set_recording_output_dir(directory)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_set_eeg_labels(self, labels_text: str) -> tuple[bool, str]:
        ok, msg = self._mgr.set_eeg_channel_labels(labels_text)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def get_eeg_labels_display(self) -> str:
        return labels_to_display_text(self._mgr.get_eeg_channel_labels())

    def on_start_recording(self) -> tuple[bool, str]:
        ok, msg = self._mgr.start_recording()
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def get_recording_status(self) -> Dict[str, Any]:
        return self._mgr.get_recording_status()

    def get_last_recording_report(self) -> Optional[RecordingStopReport]:
        return self._mgr.get_last_recording_report()

    def on_stop_recording(self) -> tuple[bool, str, Optional[RecordingStopReport]]:
        ok, msg, report = self._mgr.stop_recording()
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg, report

    @staticmethod
    def build_gui_hint(use_synthetic: bool, gui_streaming: bool) -> str:
        board = "Synthetic（合成板）" if use_synthetic else "Cyton（真机）"
        stream = "已启用" if gui_streaming else "未启用（请在 UI 勾选或 default.yaml 开启）"
        return f"""
[OpenBCI GUI 7 — STREAMING 验证（推荐 T3/T5）]
1. 控制台勾选「GUI UDP 推流」或 default.yaml 设 gui推流.启用: true（当前: {stream}）
2. 点击「开始采集」→ 状态栏为 RUNNING
3. GUI 左侧选: STREAMING (from external)
4. 右侧填写:
     IP:   225.1.1.1
     PORT: 6677
     BOARD: {board}
5. START SESSION → 再点绿色 Start Data Stream
6. T5: 保持 GUI + 控制台启动模型，跑 10 分钟

说明:
- BrainFlow UDP 推流专供 GUI 7 STREAMING，与 LSL 模型并行
- 模型走 LSL(OpenBCI_EEG)，两路互不冲突
- 不要用 CYTON (live) Serial，会抢 COM 口

[备选: LabRecorder 录 LSL 流 OpenBCI_EEG]
""".strip()

    def on_set_port(self, port: str) -> tuple[bool, str]:
        ok, msg = self._mgr.set_serial_port(port)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_set_filter(self, enabled: bool) -> tuple[bool, str]:
        ok, msg = self._mgr.set_filter_enabled(enabled)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_start_model(self, name: str) -> tuple[bool, str]:
        ok, msg = self._mgr.start_model(name)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
            self._bus.set_model_error(name, msg)
        return ok, msg

    def on_stop_model(self, name: str) -> tuple[bool, str]:
        ok, msg = self._mgr.stop_model(name)
        if ok:
            self._bus.info(msg)
        else:
            self._bus.warn(msg)
        return ok, msg

    def on_start_all_models(self) -> None:
        names = self._mgr.list_models()
        for name, ok, msg in self._mgr.start_models(names):
            if ok:
                self._bus.info(msg)
            else:
                self._bus.warn(f"{name}: {msg}")
                self._bus.set_model_error(name, msg)

    def on_stop_all_models(self) -> None:
        running = self._mgr.get_running_models()
        for name in running:
            self.on_stop_model(name)

    def on_shutdown(self) -> None:
        self._bus.info("正在退出...")
        self._mgr.shutdown()

    def poll(self) -> UiSnapshot:
        status = self._mgr.get_status()
        state = self._mgr.get_state()
        running = self._mgr.get_running_models()
        latest = self._bus.get_all_latest()
        errors: Dict[str, str] = {}
        for name in self._mgr.list_models():
            err = self._bus.get_model_error(name)
            if err:
                errors[name] = err
        logs = self._bus.drain_logs()
        return UiSnapshot(
            state=state,
            status=status,
            running_models=running,
            latest_results=latest,
            model_errors=errors,
            new_logs=logs,
        )

    @staticmethod
    def format_time(ts: float) -> str:
        return time.strftime("%H:%M:%S", time.localtime(ts))
