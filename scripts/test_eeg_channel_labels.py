"""验收：自定义 eeg通道标签 写入 LSL/CSV 表头。"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from lsl_connect.config_loader import build_service_manager_config
from lsl_connect.service_manager import ServiceManager


def main() -> None:
    cfg, _ = build_service_manager_config()
    custom = ["左前", "右前", "左运动", "右运动", "左顶", "右顶", "左枕", "右枕"]
    cfg.lsl.eeg_labels = custom
    mgr = ServiceManager(cfg)

    ok, _ = mgr.set_eeg_channel_labels(custom)
    assert ok, "set_eeg_channel_labels 失败"
    assert mgr.get_eeg_channel_labels() == custom

    if not mgr.start_acquisition():
        print(mgr.get_status().get("last_error"))
        sys.exit(1)
    time.sleep(1.0)

    ok2, msg = mgr.start_recording()
    if not ok2:
        mgr.stop_acquisition()
        print(msg)
        sys.exit(1)

    time.sleep(2.0)
    rec = mgr.get_recording_status()
    path = Path(rec["path"])
    mgr.stop_recording()
    mgr.stop_acquisition()

    with path.open(encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    expected = ["lsl_time", *custom]
    if header != expected:
        print(f"表头不符:\n  期望 {expected}\n  实际 {header}")
        sys.exit(1)

    print(f"[PASS] CSV 表头与自定义通道名一致: {header}")


if __name__ == "__main__":
    main()
