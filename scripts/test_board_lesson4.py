"""第 4 课验收：在项目根目录执行 python scripts/test_board_lesson4.py"""
import time

from eeg_broadcaster import SERIAL_PORT
from lsl_connect.board import BoardConfig,CytonBoard

def main() -> None:
            # 无硬件：合成板
            cfg = BoardConfig(serial_port='COM10',use_synthetic=False,cyton_eeg_count=8)
            b =CytonBoard(cfg)
            b.connect()
            eeg,accel,ts = b.get_channel_indices()
            print(f"EEG 索引: {eeg} (共 {len(eeg)} 个)")
            print(f"Accel 索引: {accel}")
            print(f"Timestamp 索引: {ts}")
            time.sleep(1.5)
            data = b.fetch_batch(250)
            print(f"试拉 5 点, data.shape = {data.shape}")
            b.disconnect()
            # 有 Cyton 时可取消下面注释（USE_SYNTHESIS=False 时测 COM10）
            # b2 = CytonBoard("COM10")
            # b2.connect()
            # b2.disconnect()
if __name__ == "__main__":
    main()
