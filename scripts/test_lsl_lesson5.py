import time

from pylsl import resolve_byprop

from lsl_connect.lsl_streams import (
    EEG_STREAM_NAME,
    ACCEL_STREAM_NAME,
    create_eeg_outlet,
    create_accel_outlet,
    create_outlets,
    push_eeg_chunk,
    LslStreamConfig,
)
from lsl_connect.preprocessing import preprocess_eeg_batch
import numpy as np

def main() -> None:
    cfg = LslStreamConfig(channel_count=8,sample_rate=250,use_synthetic=False)

    # 1) 单独创建 EEG Outlet
    outlet_eeg = create_eeg_outlet(cfg)
    print(f"[OK] create_eeg_outlet: {EEG_STREAM_NAME}, {cfg.channel_count} ch")
    # 2) 成对创建
    outlet_eeg2, outlet_accel = create_outlets(cfg)


    _ = outlet_eeg2  # 仅演示 API
    print(f"[OK] create_outlets: EEG + {ACCEL_STREAM_NAME }")

    # 3) 试推一小段假数据（不连板卡）
    fake_counts = np.random.randn(8, 10)
    eeg_uv = preprocess_eeg_batch(fake_counts)
    n = push_eeg_chunk(outlet_eeg, eeg_uv)
    print(f"[OK] push_eeg_chunk: {n} samples")

    # 4) LSL 发现（本机应能看到流名）
    time.sleep(0.3)
    found = resolve_byprop("name", EEG_STREAM_NAME, minimum=1, timeout=2)
    if found:
        print(f"[OK] resolve_byprop: {found[0].name()} @ {found[0].nominal_srate()} Hz")
    else:
        print("[提示] 未找到流，检查防火墙或稍后再试")
    print("第 5 课验收完成。")


if __name__ == "__main__":
    main()