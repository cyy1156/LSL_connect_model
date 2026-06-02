"""
选修 B / FR-31：CSV 本地录制验收。

用法:
  cd 项目根目录
  set PYTHONPATH=.
  python scripts/test_recorder_lessonB.py
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from lsl_connect.config_loader import build_service_manager_config, project_root
from lsl_connect.service_manager import ServiceManager
from lsl_connect.state import ServiceState


def _ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def main() -> None:
    cfg, msg = build_service_manager_config()
    print(f"[配置] {msg}")

    mgr = ServiceManager(cfg)
    if not mgr.start_acquisition():
        _fail(mgr.get_status().get("last_error") or "start_acquisition 失败")

    time.sleep(1.0)

    ok, start_msg = mgr.start_recording()
    if not ok:
        mgr.stop_acquisition()
        _fail(f"start_recording: {start_msg}")
    print(f"[INFO] {start_msg}")

    duration = 5.0
    time.sleep(duration)

    rec_live = mgr.get_recording_status()
    csv_path_str = rec_live.get("path")
    if not csv_path_str:
        mgr.stop_acquisition()
        _fail("录制中路径为空")

    ok2, stop_msg, report = mgr.stop_recording()
    if not ok2:
        mgr.stop_acquisition()
        _fail(f"stop_recording: {stop_msg}")
    print(f"[INFO] {stop_msg}")

    mgr.stop_acquisition()

    csv_path = Path(csv_path_str)
    if not csv_path.is_file():
        _fail(f"CSV 不存在: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or header[0] != "lsl_time":
            _fail(f"表头异常: {header}")
        rows = list(reader)

    expected = int(250 * duration * 0.85)
    if len(rows) < expected:
        _fail(f"行数过少: {len(rows)} < {expected}（约 {duration}s @250Hz）")

    meta_path = csv_path.with_suffix(".meta.json")
    if not meta_path.is_file():
        _fail(f"缺少元数据: {meta_path}")

    _ok(f"CSV 行数={len(rows)} 文件={csv_path.relative_to(project_root())}")
    _ok("选修 B CSV 录制验收通过")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断]")
        sys.exit(130)
