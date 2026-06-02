"""
线程安全：系统日志队列 + 各模型结果存储。
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class LogEntry:
    level: str
    message: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModelResult:
    model_name: str
    timestamp: float
    raw: Any
    summary: str
    fields: dict[str, str]


class EventBus:
    """UI 与后台线程之间的消息总线。"""

    def __init__(self, history_size: int = 50) -> None:
        self._history_size = history_size
        self._log_queue: queue.Queue[LogEntry] = queue.Queue()
        self._lock = threading.Lock()
        self._history: Dict[str, Deque[ModelResult]] = {}
        self._latest: Dict[str, ModelResult] = {}
        self._errors: Dict[str, str] = {}

    def log(self, level: str, message: str) -> None:
        self._log_queue.put(LogEntry(level=level, message=message))

    def info(self, message: str) -> None:
        self.log("INFO", message)

    def warn(self, message: str) -> None:
        self.log("WARN", message)

    def error(self, message: str) -> None:
        self.log("ERROR", message)

    def push_model_result(self, model_name: str, raw: Any) -> None:
        from lsl_connect.ui.result_renderer import render_model_result

        result = render_model_result(model_name, raw)
        with self._lock:
            if model_name not in self._history:
                self._history[model_name] = deque(maxlen=self._history_size)
            self._history[model_name].append(result)
            self._latest[model_name] = result
            self._errors.pop(model_name, None)

    def set_model_error(self, model_name: str, message: str) -> None:
        with self._lock:
            self._errors[model_name] = message

    def clear_model_error(self, model_name: str) -> None:
        with self._lock:
            self._errors.pop(model_name, None)

    def drain_logs(self, max_items: int = 200) -> List[LogEntry]:
        items: List[LogEntry] = []
        for _ in range(max_items):
            try:
                items.append(self._log_queue.get_nowait())
            except queue.Empty:
                break
        return items

    def get_latest_result(self, model_name: str) -> Optional[ModelResult]:
        with self._lock:
            return self._latest.get(model_name)

    def get_all_latest(self) -> Dict[str, ModelResult]:
        with self._lock:
            return dict(self._latest)

    def get_model_error(self, model_name: str) -> Optional[str]:
        with self._lock:
            return self._errors.get(model_name)

    def get_history(self, model_name: str, limit: int = 10) -> List[ModelResult]:
        with self._lock:
            hist = self._history.get(model_name)
            if not hist:
                return []
            return list(hist)[-limit:]
