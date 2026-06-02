"""第 11 课验收：models.yaml 驱动 model list / model start demo。"""

import time

from lsl_connect.config_loader import load_models_yaml_dict
from lsl_connect.service_manager import ServiceManager
from lsl_connect.config_loader import build_service_manager_config
from models.registry import parse_models_yaml


def main() -> None:
    raw, yaml_msg = load_models_yaml_dict()
    print(f"[YAML] {yaml_msg}")
    specs = parse_models_yaml(raw)
    assert "demo" in specs, "models.yaml 中应有 demo 条目"
    demo = specs["demo"]
    print(f"[OK] demo: 说明={demo.description!r} 窗口={demo.window_size}")

    cfg, msg = build_service_manager_config()
    print(f"[配置] {msg}")
    mgr = ServiceManager(cfg)
    print(f"[模型] {mgr.get_models_message()}")
    print(f"[list] {mgr.list_models()}")

    if not mgr.start_acquisition():
        print("[失败] start:", mgr.get_status().get("last_error"))
        return
    time.sleep(1)

    ok, text = mgr.start_model("demo")
    print(f"{'[OK]' if ok else '[失败]'} {text}")
    time.sleep(3)

    mgr.stop_model("demo")
    mgr.stop_acquisition()
    print("第 11 课验收完成。")
    print("提示: 改 models.yaml 里 demo 的「说明」或「窗口采样点数」，quit 重启后 model list 应变化。")


if __name__ == "__main__":
    main()