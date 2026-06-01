"""第 10 课验收：start → model start demo → 看输出 → stop。"""
import time

from lsl_connect.config_loader import build_service_manager_config
from lsl_connect.service_manager import ServiceManager


def main() -> None:
    cfg, msg = build_service_manager_config()
    print(f"[配置] {msg}")
    mgr = ServiceManager(cfg)

    if not mgr.start_acquisition():
        err = mgr.get_status().get("last_error")
        print(f"[失败] start_acquisition: {err}")
        print(f"  状态: {mgr.get_state().value}")
        print("  提示: 关 GUI / 检查 COM 口，或 default.yaml 设 使用合成板: true")
        return
    print("[OK] 采集 RUNNING")
    time.sleep(1)

    ok, text = mgr.start_model("demo")
    if not ok:
        print(f"[失败] start_model: {text}")
        mgr.stop_acquisition()
        return
    print(f"[OK] {text}")

    print("等待 5 秒，应看到 [模型/demo] mean=... std=...")
    time.sleep(5)

    mgr.stop_model("demo")
    mgr.stop_acquisition()
    print("第 10 课验收完成。")


if __name__ == "__main__":
    main()
