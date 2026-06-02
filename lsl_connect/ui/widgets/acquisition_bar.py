"""采集控制栏：启停、数据源、串口、滤波、GUI 推流、CSV 录制、保存配置。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from lsl_connect.state import ServiceState


class AcquisitionBar(ttk.Frame):
    def __init__(
        self,
        master,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_reset: Callable[[], None],
        on_board_mode: Callable[[bool, str], None],
        on_filter: Callable[[bool], None],
        on_gui_streaming: Callable[[bool], None],
        on_recording_auto: Callable[[bool], None],
        on_recording_dir: Callable[[str], None],
        on_eeg_labels: Callable[[str], None],
        on_start_recording: Callable[[], None],
        on_stop_recording: Callable[[], None],
        on_save_config: Callable[[], None],
        on_help: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)

        self._on_board_mode = on_board_mode
        self._on_gui_streaming = on_gui_streaming
        self._on_recording_auto = on_recording_auto
        self._on_recording_dir = on_recording_dir
        self._on_eeg_labels = on_eeg_labels
        self._updating = False

        # --- 第一行：采集控制 ---
        row1 = ttk.Frame(self)
        row1.pack(fill=tk.X, pady=(0, 6))

        self._btn_start = ttk.Button(row1, text="▶ 开始采集", style="Accent.TButton", command=on_start)
        self._btn_start.pack(side=tk.LEFT, padx=(0, 4))

        self._btn_stop = ttk.Button(row1, text="■ 停止采集", command=on_stop)
        self._btn_stop.pack(side=tk.LEFT, padx=4)

        self._btn_reset = ttk.Button(row1, text="重置", command=on_reset)
        self._btn_reset.pack(side=tk.LEFT, padx=4)

        ttk.Button(row1, text="💾 保存配置", command=on_save_config).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(row1, text="GUI 帮助", command=on_help).pack(side=tk.RIGHT, padx=4)

        # --- 第二行：数据源 + 串口 ---
        row2 = ttk.LabelFrame(self, text="数据源", padding=(8, 6))
        row2.pack(fill=tk.X, pady=(0, 6))

        self._mode_var = tk.StringVar(value="synthetic")

        self._rb_syn = ttk.Radiobutton(
            row2,
            text="合成板（无硬件）",
            variable=self._mode_var,
            value="synthetic",
            command=self._on_mode_change,
        )
        self._rb_syn.grid(row=0, column=0, sticky=tk.W, padx=(0, 16))

        self._rb_real = ttk.Radiobutton(
            row2,
            text="真机 Cyton",
            variable=self._mode_var,
            value="real",
            command=self._on_mode_change,
        )
        self._rb_real.grid(row=0, column=1, sticky=tk.W, padx=(0, 16))

        ttk.Label(row2, text="串口:").grid(row=0, column=2, sticky=tk.W)
        self._port_var = tk.StringVar(value="COM10")
        self._port_combo = ttk.Combobox(
            row2,
            textvariable=self._port_var,
            values=["COM3", "COM4", "COM5", "COM10", "COM11"],
            width=10,
        )
        self._port_combo.grid(row=0, column=3, padx=4)
        self._btn_port = ttk.Button(row2, text="应用串口", command=self._apply_port)
        self._btn_port.grid(row=0, column=4, padx=4)

        # --- 第三行：运行时选项 ---
        row3 = ttk.Frame(self)
        row3.pack(fill=tk.X, pady=(0, 6))

        self._filter_var = tk.BooleanVar(value=True)
        self._filter_chk = ttk.Checkbutton(
            row3,
            text="实时滤波",
            variable=self._filter_var,
            command=self._toggle_filter,
        )
        self._filter_chk.pack(side=tk.LEFT, padx=(0, 16))

        self._gui_stream_var = tk.BooleanVar(value=True)
        self._gui_stream_chk = ttk.Checkbutton(
            row3,
            text="GUI UDP 推流 (225.1.1.1:6677)",
            variable=self._gui_stream_var,
            command=self._toggle_gui_stream,
        )
        self._gui_stream_chk.pack(side=tk.LEFT)

        self._on_filter = on_filter

        # --- 第四行：CSV 录制 ---
        row4 = ttk.LabelFrame(self, text="CSV 本地录制", padding=(8, 6))
        row4.pack(fill=tk.X)

        self._rec_auto_var = tk.BooleanVar(value=False)
        self._rec_auto_chk = ttk.Checkbutton(
            row4,
            text="开始采集时自动录制",
            variable=self._rec_auto_var,
            command=self._toggle_rec_auto,
        )
        self._rec_auto_chk.grid(row=0, column=0, sticky=tk.W, padx=(0, 12))

        ttk.Label(row4, text="保存目录:").grid(row=0, column=1, sticky=tk.W)
        self._rec_dir_var = tk.StringVar(value="data/recordings")
        self._rec_dir_entry = ttk.Entry(row4, textvariable=self._rec_dir_var, width=28)
        self._rec_dir_entry.grid(row=0, column=2, padx=4, sticky=tk.W)
        self._btn_rec_dir = ttk.Button(row4, text="应用目录", command=self._apply_rec_dir)
        self._btn_rec_dir.grid(row=0, column=3, padx=4)

        self._btn_rec_start = ttk.Button(row4, text="● 开始录制", command=on_start_recording)
        self._btn_rec_start.grid(row=0, column=4, padx=(12, 4))

        self._btn_rec_stop = ttk.Button(row4, text="■ 停止录制", command=on_stop_recording)
        self._btn_rec_stop.grid(row=0, column=5, padx=4)

        # --- 第五行：EEG 通道名称 ---
        row5 = ttk.LabelFrame(
            self,
            text="EEG 通道名称（CH1→CH8，与 CSV 表头一致）",
            padding=(8, 6),
        )
        row5.pack(fill=tk.X, pady=(6, 0))

        ttk.Label(row5, text="逗号分隔:").grid(row=0, column=0, sticky=tk.W)
        self._labels_var = tk.StringVar(
            value="Fp1, Fp2, C3, C4, P7, P8, O1, O2"
        )
        self._labels_entry = ttk.Entry(row5, textvariable=self._labels_var, width=72)
        self._labels_entry.grid(row=0, column=1, padx=4, sticky=tk.EW)
        self._btn_labels = ttk.Button(row5, text="应用通道名", command=self._apply_labels)
        self._btn_labels.grid(row=0, column=2, padx=4)
        row5.columnconfigure(1, weight=1)

    def _apply_labels(self) -> None:
        self._on_eeg_labels(self._labels_var.get())

    def _on_mode_change(self) -> None:
        if self._updating:
            return
        use_syn = self._mode_var.get() == "synthetic"
        self._on_board_mode(use_syn, self._port_var.get())
        self._refresh_port_state()

    def _apply_port(self) -> None:
        self._mode_var.set("real")
        self._on_board_mode(False, self._port_var.get())

    def _toggle_filter(self) -> None:
        self._on_filter(self._filter_var.get())

    def _toggle_gui_stream(self) -> None:
        if self._updating:
            return
        self._on_gui_streaming(self._gui_stream_var.get())

    def _toggle_rec_auto(self) -> None:
        if self._updating:
            return
        self._on_recording_auto(self._rec_auto_var.get())

    def _apply_rec_dir(self) -> None:
        self._on_recording_dir(self._rec_dir_var.get())

    def sync_settings(
        self,
        use_synthetic: bool,
        serial_port: str,
        filter_enabled: bool,
        gui_streaming_enabled: bool,
        recording_auto_start: bool = False,
        recording_output_dir: str = "data/recordings",
        eeg_channel_labels: str = "",
    ) -> None:
        self._updating = True
        try:
            self._mode_var.set("synthetic" if use_synthetic else "real")
            self._port_var.set(serial_port)
            self._filter_var.set(filter_enabled)
            self._gui_stream_var.set(gui_streaming_enabled)
            self._rec_auto_var.set(recording_auto_start)
            self._rec_dir_var.set(recording_output_dir)
            if eeg_channel_labels:
                self._labels_var.set(eeg_channel_labels)
        finally:
            self._updating = False
        self._refresh_port_state()

    def set_filter(self, enabled: bool) -> None:
        self._updating = True
        self._filter_var.set(enabled)
        self._updating = False

    def _refresh_port_state(self) -> None:
        synthetic = self._mode_var.get() == "synthetic"
        if synthetic:
            self._port_combo.state(["disabled"])
            self._btn_port.state(["disabled"])
        else:
            self._port_combo.state(["!disabled"])
            self._btn_port.state(["!disabled"])

    def update_controls(
        self,
        state: ServiceState,
        recording_active: bool = False,
    ) -> None:
        idle = state == ServiceState.IDLE
        running = state == ServiceState.RUNNING
        error = state == ServiceState.ERROR

        self._btn_start.state(["!disabled"] if idle else ["disabled"])
        self._btn_stop.state(["!disabled"] if (running or error) else ["disabled"])
        self._btn_reset.state(["!disabled"] if error else ["disabled"])

        mode_state = "normal" if idle else "disabled"
        self._rb_syn.configure(state=mode_state)
        self._rb_real.configure(state=mode_state)

        rec_cfg_state = "normal" if idle else "disabled"
        self._rec_auto_chk.configure(state=rec_cfg_state)
        self._rec_dir_entry.configure(state=rec_cfg_state)
        self._btn_rec_dir.configure(state=rec_cfg_state)
        self._labels_entry.configure(state=rec_cfg_state)
        self._btn_labels.configure(state=rec_cfg_state)

        if idle:
            self._refresh_port_state()
            self._gui_stream_chk.state(["!disabled"])
        else:
            self._port_combo.state(["disabled"])
            self._btn_port.state(["disabled"])
            self._gui_stream_chk.state(["disabled"])

        if running:
            self._filter_chk.state(["!disabled"])
            self._btn_rec_start.state(
                ["disabled"] if recording_active else ["!disabled"]
            )
            self._btn_rec_stop.state(["!disabled"] if recording_active else ["disabled"])
        else:
            self._filter_chk.state(["disabled"])
            self._btn_rec_start.state(["disabled"])
            self._btn_rec_stop.state(["disabled"])
