"""
第 10 课：模型 worker — 订阅 LSL EEG 流，滑动窗口调用 ModelPlugin.predict。
UI 模式：on_result 回调 + 短 pull 超时，便于快速 stop。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
from pylsl import StreamInlet, resolve_byprop

from lsl_connect.lsl_streams import EEG_STREAM_NAME
from models.base import ModelPlugin


@dataclass
class ModelWorkerConfig:
    stream_name: str = EEG_STREAM_NAME
    resolve_timeout: float = 5.0
    pull_timeout: float = 0.3
    print_every_n_predicts: int = 1
    silent: bool = False


class ModelWorker:
    """
    在独立线程中订阅 LSL 并周期性 predict。

    用法:
        worker = ModelWorker(DemoStatsModel())
        worker.start()
        ...
        worker.stop()
    """

    def __init__(
        self,
        plugin: ModelPlugin,
        config: Optional[ModelWorkerConfig] = None,
        on_result: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._plugin = plugin
        self._config = config or ModelWorkerConfig()
        self._on_result = on_result
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._inlet: Optional[StreamInlet] = None
        self._predict_count = 0

    @property
    def name(self) -> str:
        return self._plugin.name

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError(f"模型 {self._plugin.name} 已在运行")

        self._plugin.load()
        self._stop_event.clear()
        self._predict_count = 0

        streams = resolve_byprop(
            "name",
            self._config.stream_name,
            minimum=1,
            timeout=self._config.resolve_timeout,
        )
        if not streams:
            raise RuntimeError(
                f"未找到 LSL 流 {self._config.stream_name!r}，请先 start 采集"
            )

        self._inlet = StreamInlet(streams[0])
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"ModelWorker-{self._plugin.name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop_event.set()
        inlet = self._inlet
        if inlet is not None:
            try:
                inlet.close_stream()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            self._thread = None
        self._inlet = None

    def _run_loop(self) -> None:
        assert self._inlet is not None

        plugin = self._plugin
        cfg = self._config
        window = plugin.window_size
        hop = plugin.hop_size

        buf: Optional[np.ndarray] = None
        filled = 0

        while not self._stop_event.is_set():
            chunk, _ts = self._inlet.pull_chunk(
                timeout=cfg.pull_timeout,
                max_samples=hop,
            )
            if self._stop_event.is_set():
                break
            if not chunk:
                continue

            samples = np.asarray(chunk, dtype=np.float32)
            if samples.ndim == 1:
                samples = samples.reshape(-1, 1)
            n_new = samples.shape[0]
            n_ch = samples.shape[1]
            samples_ct = samples.T

            if buf is None:
                buf = np.zeros((n_ch, window), dtype=np.float32)
                filled = 0

            for i in range(n_new):
                if self._stop_event.is_set():
                    break

                if filled < window:
                    buf[:, filled] = samples_ct[:, i]
                    filled += 1
                else:
                    buf[:, :-1] = buf[:, 1:]
                    buf[:, -1] = samples_ct[:, i]

                if filled >= window:
                    data = buf.copy()
                    try:
                        result = plugin.predict(data)
                    except Exception as exc:
                        msg = f"predict 异常: {exc}"
                        if self._on_error:
                            self._on_error(msg)
                        elif not cfg.silent:
                            print(f"[模型/{plugin.name}] {msg}")
                        continue

                    self._predict_count += 1
                    if self._predict_count % cfg.print_every_n_predicts == 0:
                        self._emit_result(result)

    def _emit_result(self, result: Any) -> None:
        if self._on_result is not None:
            self._on_result(result)
            return
        if self._config.silent:
            return
        if isinstance(result, dict):
            mean_uv = result.get("mean_uv")
            std_uv = result.get("std_uv")
            if mean_uv is not None and std_uv is not None:
                print(
                    f"[模型/{self._plugin.name}] "
                    f"mean={float(mean_uv):.2f} uV  std={float(std_uv):.2f} uV"
                )
                return
        print(f"[模型/{self._plugin.name}] {result}")
