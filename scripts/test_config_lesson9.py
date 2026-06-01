"""第 9 课验收：能加载 YAML，且 COM / 合成板 与文件一致。"""
from lsl_connect.config_loader import build_service_manager_config, load_yaml_dict


def main() -> None:
    raw, msg = load_yaml_dict()
    print(f"[OK] load_yaml_dict: {msg}")
    print(f"     串口={raw.get('串口', raw.get('serial_port', '?'))}")

    cfg, msg2 = build_service_manager_config()
    print(f"[OK] build_service_manager_config: {msg2}")
    b = cfg.board_config
    print(
        f"     board: port={b.serial_port} synthetic={b.use_synthetic} "
        f"ch={b.cyton_eeg_count}"
    )
    print(f"     filter={cfg.preprocess.filter_enabled} fs={cfg.preprocess.sample_rate}")
    print(f"     acquisition quiet={cfg.acquisition.quiet}")
    print("第 9 课配置加载验收完成。")


if __name__ == "__main__":
    main()