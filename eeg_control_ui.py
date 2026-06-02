"""
OpenBCI 实验控制台 — 轻量 UI 入口。
用法: python eeg_control_ui.py
"""

from __future__ import annotations

from lsl_connect.config_loader import build_service_manager_config
from lsl_connect.service_manager import ServiceManager
from lsl_connect.ui.app import ControlUIApp
from lsl_connect.ui.event_bus import EventBus


def main() -> None:
    cfg, config_msg = build_service_manager_config()
    bus = EventBus()
    mgr = ServiceManager(cfg, event_bus=bus)
    models_msg = mgr.get_models_message()

    app = ControlUIApp(
        mgr,
        bus,
        config_message=config_msg,
        models_message=models_msg,
    )
    app.run()


if __name__ == "__main__":
    main()
