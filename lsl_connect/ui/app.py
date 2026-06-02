"""
OpenBCI 实验控制台 — tkinter 主窗口。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from lsl_connect.recording_quality import RecordingStopReport
from lsl_connect.service_manager import ServiceManager
from lsl_connect.ui.controllers.app_controller import AppController
from lsl_connect.ui.event_bus import EventBus
from lsl_connect.ui.theme import apply_theme
from lsl_connect.ui.widgets.acquisition_bar import AcquisitionBar
from lsl_connect.ui.widgets.log_panel import LogPanel
from lsl_connect.ui.widgets.model_grid import ModelGrid
from lsl_connect.ui.widgets.status_bar import StatusBar

POLL_MS = 200


class ControlUIApp:
    """轻量 UI 应用入口。"""

    def __init__(
        self,
        manager: ServiceManager,
        event_bus: EventBus,
        config_message: str = "",
        models_message: str = "",
    ) -> None:
        self._bus = event_bus
        self._controller = AppController(
            manager,
            self._bus,
            config_message=config_message,
            models_message=models_message,
        )

        self._root = tk.Tk()
        self._root.title("OpenBCI 实验控制台")
        self._root.geometry("980x800")
        self._root.minsize(860, 620)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        apply_theme(self._root)
        self._build_ui()
        self._sync_from_settings()
        self._schedule_poll()

    def _build_ui(self) -> None:
        root = self._root
        ctrl = self._controller

        header = ttk.Frame(root, style="Header.TFrame", padding=(16, 12))
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text="OpenBCI Cyton + LSL 控制台",
            style="HeaderTitle.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="数据源、录制目录与 GUI 推流可保存到 default.yaml；models.yaml 修改后请重启",
            style="HeaderSub.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))

        body = ttk.Frame(root, padding=(12, 8))
        body.pack(fill=tk.BOTH, expand=True)

        self._status_bar = StatusBar(body, padding=(12, 8))
        self._status_bar.pack(fill=tk.X, pady=(0, 8))

        self._acq_bar = AcquisitionBar(
            body,
            on_start=self._handle_start,
            on_stop=self._handle_stop,
            on_reset=self._handle_reset,
            on_board_mode=self._handle_board_mode,
            on_filter=self._handle_filter,
            on_gui_streaming=self._handle_gui_streaming,
            on_recording_auto=self._handle_recording_auto,
            on_recording_dir=self._handle_recording_dir,
            on_eeg_labels=self._handle_eeg_labels,
            on_start_recording=self._handle_start_recording,
            on_stop_recording=self._handle_stop_recording,
            on_save_config=self._handle_save_config,
            on_help=self._show_help,
        )
        self._acq_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))

        self._model_grid = ModelGrid(
            body,
            on_start=lambda n: self._handle_model_start(n),
            on_stop=lambda n: self._handle_model_stop(n),
            on_start_all=ctrl.on_start_all_models,
            on_stop_all=ctrl.on_stop_all_models,
        )
        self._model_grid.pack(fill=tk.BOTH, expand=True)
        self._model_grid.build_from_specs(ctrl.get_model_specs())

        self._log_panel = LogPanel(body, height=7)
        self._log_panel.pack(fill=tk.X, pady=(8, 0))

    def _sync_from_settings(self) -> None:
        s = self._controller.get_board_settings()
        r = self._controller.get_recording_settings()
        self._acq_bar.sync_settings(
            use_synthetic=bool(s.get("use_synthetic", True)),
            serial_port=str(s.get("serial_port", "COM10")),
            filter_enabled=bool(s.get("filter_enabled", True)),
            gui_streaming_enabled=bool(s.get("gui_streaming_enabled", False)),
            recording_auto_start=bool(r.get("auto_start", False)),
            recording_output_dir=str(r.get("output_dir", "data/recordings")),
            eeg_channel_labels=self._controller.get_eeg_labels_display(),
        )

    def _handle_start(self) -> None:
        ok, msg = self._controller.on_start_acquisition()
        if not ok:
            messagebox.showerror("开始采集", msg)

    def _handle_stop(self) -> None:
        was_recording = bool(self._controller.get_recording_status().get("active"))
        ok, msg = self._controller.on_stop_acquisition()
        if not ok:
            messagebox.showwarning("停止采集", msg)
            return
        if was_recording:
            report = self._controller.get_last_recording_report()
            if report is not None:
                self._show_recording_quality_report(report)

    def _handle_reset(self) -> None:
        ok, msg = self._controller.on_reset()
        if not ok:
            messagebox.showwarning("重置", msg)

    def _handle_board_mode(self, use_synthetic: bool, port: str) -> None:
        ok, msg = self._controller.on_set_board_mode(use_synthetic, port)
        if not ok:
            messagebox.showwarning("数据源", msg)
            self._sync_from_settings()

    def _handle_gui_streaming(self, enabled: bool) -> None:
        ok, msg = self._controller.on_set_gui_streaming(enabled)
        if not ok:
            messagebox.showwarning("GUI 推流", msg)
            self._sync_from_settings()

    def _handle_recording_auto(self, enabled: bool) -> None:
        ok, msg = self._controller.on_set_recording_auto(enabled)
        if not ok:
            messagebox.showwarning("自动录制", msg)
            self._sync_from_settings()

    def _handle_recording_dir(self, directory: str) -> None:
        ok, msg = self._controller.on_set_recording_dir(directory)
        if not ok:
            messagebox.showwarning("保存目录", msg)
            self._sync_from_settings()

    def _handle_eeg_labels(self, text: str) -> None:
        ok, msg = self._controller.on_set_eeg_labels(text)
        if not ok:
            messagebox.showwarning("通道名称", msg)
            self._sync_from_settings()

    def _handle_start_recording(self) -> None:
        ok, msg = self._controller.on_start_recording()
        if not ok:
            messagebox.showwarning("开始录制", msg)

    def _handle_stop_recording(self) -> None:
        ok, msg, report = self._controller.on_stop_recording()
        if not ok:
            messagebox.showwarning("停止录制", msg)
            return
        if report is not None:
            self._show_recording_quality_report(report)

    @staticmethod
    def _show_recording_quality_report(report: RecordingStopReport) -> None:
        title = report.popup_title()
        body = report.summary_message()
        if report.severity == "ok":
            messagebox.showinfo(title, body)
        else:
            messagebox.showwarning(title, body)

    def _handle_save_config(self) -> None:
        ok, msg = self._controller.on_save_config()
        if ok:
            messagebox.showinfo("保存配置", msg)
        else:
            messagebox.showerror("保存配置", msg)

    def _handle_filter(self, enabled: bool) -> None:
        ok, msg = self._controller.on_set_filter(enabled)
        if not ok:
            messagebox.showwarning("滤波", msg)
            self._sync_from_settings()

    def _handle_model_start(self, name: str) -> None:
        ok, msg = self._controller.on_start_model(name)
        if not ok:
            messagebox.showwarning(f"启动模型 {name}", msg)

    def _handle_model_stop(self, name: str) -> None:
        ok, msg = self._controller.on_stop_model(name)
        if not ok:
            messagebox.showwarning(f"停止模型 {name}", msg)

    def _show_help(self) -> None:
        s = self._controller.get_board_settings()
        text = AppController.build_gui_hint(
            bool(s.get("use_synthetic", True)),
            bool(s.get("gui_streaming_enabled", False)),
        )
        messagebox.showinfo("GUI / 连接帮助", text)

    def _schedule_poll(self) -> None:
        self._root.after(POLL_MS, self._poll_tick)

    def _poll_tick(self) -> None:
        snap = self._controller.poll()
        self._status_bar.update_status(snap.state, snap.status)
        self._acq_bar.update_controls(
            snap.state,
            recording_active=bool(snap.status.get("recording_active")),
        )
        self._model_grid.update_all(
            snap.state,
            snap.running_models,
            snap.latest_results,
            snap.model_errors,
        )
        self._log_panel.append_logs(snap.new_logs)
        self._schedule_poll()

    def _on_close(self) -> None:
        if messagebox.askokcancel("退出", "确定退出？将停止采集、录制与所有模型。"):
            self._controller.on_shutdown()
            self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()
