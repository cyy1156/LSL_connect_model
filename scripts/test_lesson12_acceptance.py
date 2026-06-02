"""
第 12 课：联调验收脚本（对应需求文档 §9 T1～T6 中可自动化部分）。

用法:
  cd 项目根目录
  set PYTHONPATH=.
  python scripts/test_lesson12_acceptance.py           # 快速验收 (~30s)
  python scripts/test_lesson12_acceptance.py --stress 60 # T5 简版：跑 60 秒看样本速率
"""

from __future__ import annotations

import argparse
import sys
import time

from lsl_connect.config_loader import build_service_manager_config
from lsl_connect.service_manager import ServiceManager
from lsl_connect.state import ServiceState


def _ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def check_t1_lsl_meta(mgr: ServiceManager) -> None:
    """T1 部分：配置与模型表可读。"""
    st = mgr.get_status()
    if st["channel_count"] != 8:
        _fail(f"通道数应为 8，实际 {st['channel_count']}")
    if st["sample_rate_hz"] != 250:
        _fail(f"采样率应为 250，实际 {st['sample_rate_hz']}")
    names = mgr.list_models()
    if "demo" not in names:
        _fail(f"model list 应含 demo，实际 {names}")
    _ok("T1 配置/模型表")


def check_t2_start_running(mgr: ServiceManager, wait_sec: float = 3.0) -> int:
    """T2：start 后 RUNNING 且 samples_pushed 递增。"""
    if not mgr.start_acquisition():
        err = mgr.get_status().get("last_error")
        _fail(f"start_acquisition 失败: {err}")

    if mgr.get_state() != ServiceState.RUNNING:
        _fail(f"状态应为 RUNNING，实际 {mgr.get_state().value}")

    s0 = mgr.get_status()["samples_pushed"]
    time.sleep(wait_sec)
    s1 = mgr.get_status()["samples_pushed"]
    if s1 <= s0:
        _fail(f"samples_pushed 未递增: {s0} -> {s1}")

    _ok(f"T2 采集 RUNNING，{wait_sec}s 内推送 {s1 - s0} 样本")
    return s1 - s0


def check_t4_model_demo(mgr: ServiceManager, run_sec: float = 3.0) -> None:
    """T4：model start demo 成功（预测日志需肉眼看终端或开 quiet=False）。"""
    ok, msg = mgr.start_model("demo")
    if not ok:
        _fail(f"model start demo 失败: {msg}")
    if "demo" not in mgr.get_running_models():
        _fail("get_running_models 应含 demo")

    time.sleep(run_sec)

    ok2, msg2 = mgr.stop_model("demo")
    if not ok2:
        _fail(f"model stop demo 失败: {msg2}")
    _ok("T4 model start/stop demo")


def check_t6_stop_restart(mgr: ServiceManager) -> None:
    """T6：stop → start 可恢复。"""
    if not mgr.stop_acquisition():
        _fail("stop_acquisition 失败")
    if mgr.get_state() != ServiceState.IDLE:
        _fail(f"stop 后应为 IDLE，实际 {mgr.get_state().value}")

    if not mgr.start_acquisition():
        err = mgr.get_status().get("last_error")
        _fail(f"第二次 start 失败（可能 port busy）: {err}")

    mgr.stop_acquisition()
    _ok("T6 stop → start 恢复")


def _using_synthetic(mgr: ServiceManager) -> bool:
    """get_status 在合成板模式下 serial_port 显示为「合成板」。"""
    return mgr.get_status()["serial_port"] == "合成板"


def check_config_rules(mgr: ServiceManager) -> None:
    """可选：config port / filter 与 §5.4.3 一致。"""
    if _using_synthetic(mgr):
        print("[INFO] 合成板模式：跳过 config port 测试（set_serial_port 会强制切到真机 COM）")

        if not mgr.start_acquisition():
            err = mgr.get_status().get("last_error")
            _fail(f"合成板 start 失败: {err}")

        ok_filter, _ = mgr.set_filter_enabled(False)
        if not ok_filter:
            _fail("RUNNING 下 set_filter_enabled 应成功")
        mgr.stop_acquisition()

        ok_idle_filter, _ = mgr.set_filter_enabled(True)
        if ok_idle_filter:
            _fail("IDLE 下不应允许改 filter")

        _ok("config filter 状态规则（合成板跳过 port）")
        return

    # 真机：IDLE 改 port 应成功（会切到真机模式）
    ok, _ = mgr.set_serial_port("COM10")
    if not ok:
        _fail("IDLE 下 set_serial_port 应成功")

    if not mgr.start_acquisition():
        err = mgr.get_status().get("last_error")
        _fail(f"真机 start 失败: {err}")

    ok2, _ = mgr.set_serial_port("COM11")
    if ok2:
        _fail("RUNNING 下不应允许改 port")
    mgr.stop_acquisition()

    if not mgr.start_acquisition():
        err = mgr.get_status().get("last_error")
        _fail(f"真机 start 失败: {err}")

    ok3, _ = mgr.set_filter_enabled(False)
    if not ok3:
        _fail("RUNNING 下 set_filter_enabled 应成功")
    mgr.stop_acquisition()

    _ok("config port/filter 状态规则")


def check_stress_rate(
    mgr: ServiceManager,
    duration_sec: float,
    expected_hz: float = 250.0,
    tolerance: float = 0.15,
) -> None:
    """T5 简版：只测推送速率，不含 GUI / 双模型。"""
    if not mgr.start_acquisition():
        _fail("stress: start 失败")

    s0 = mgr.get_status()["samples_pushed"]
    t0 = time.time()
    time.sleep(duration_sec)
    s1 = mgr.get_status()["samples_pushed"]
    elapsed = time.time() - t0
    rate = (s1 - s0) / elapsed if elapsed > 0 else 0.0

    mgr.stop_acquisition()

    low = expected_hz * (1.0 - tolerance)
    high = expected_hz * (1.0 + tolerance)
    if not (low <= rate <= high):
        _fail(f"推送速率 {rate:.1f} Hz 不在 [{low:.1f}, {high:.1f}]")
    _ok(f"T5 简版 {duration_sec:.0f}s 平均 {rate:.1f} Hz")


def main() -> None:
    parser = argparse.ArgumentParser(description="第 12 课验收")
    parser.add_argument(
        "--stress",
        type=float,
        default=0,
        metavar="SEC",
        help="额外跑 N 秒速率测试（如 600=10 分钟）",
    )
    args = parser.parse_args()

    cfg, msg = build_service_manager_config()
    print(f"[配置] {msg}")
    mgr = ServiceManager(cfg)
    mode = "合成板" if _using_synthetic(mgr) else f"真机 ({mgr.get_status()['serial_port']})"
    print(f"[模式] {mode}")
    print(f"[模型] {mgr.get_models_message()}")

    check_t1_lsl_meta(mgr)
    check_config_rules(mgr)
    check_t2_start_running(mgr)
    check_t4_model_demo(mgr)
    check_t6_stop_restart(mgr)

    if args.stress > 0:
        check_stress_rate(mgr, args.stress)

    print()
    print("=" * 50)
    print("自动化项已通过。")
    print("请人工完成：")
    print("  T3  OpenBCI GUI → Networking → LSL → OpenBCI_EEG 波形连续")
    print("  T5  控制面板 start + GUI + model start demo 同开 10 分钟")
    print("=" * 50)


if __name__ == "__main__":
    main()