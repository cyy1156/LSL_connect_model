"""第 4 课验收：在项目根目录执行 python scripts/test_board_lesson4.py"""
import time

from lsl_connect.board import BoardConfig, CytonBoard

def main() -> None:
    # 无硬件：合成板（有 Cyton 时可改 use_synthetic=False, serial_port="COM10"）
    cfg = BoardConfig(use_synthetic=True, cyton_eeg_count=8)
    b = CytonBoard(cfg)
    b.connect()
    eeg, accel, ts = b.get_channel_indices()
    print(f"EEG 索引: {eeg} (共 {len(eeg)} 个)")
    print(f"Accel 索引: {accel}")
    print(f"Timestamp 索引: {ts}")
    time.sleep(1.5)
    data = b.fetch_batch(250)
    print(f"试拉 batch, data.shape = {data.shape}")
    b.disconnect()
if __name__ == "__main__":
    main()
