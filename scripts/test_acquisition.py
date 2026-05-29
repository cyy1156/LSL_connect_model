"""
第 6 课验收：主线程 sleep，samples_pushed 持续增长；stop() 后线程结束。
"""
import time
from lsl_connect.acquisition_work import AcquisitionWorker
from lsl_connect.board import BoardConfig

def main() -> None:

    #无硬件合成板
    board_cfg = BoardConfig(use_synthetic=True,cyton_eeg_count=8)

    #真机Cyton
    #board_cfg=BoardConfig(serial_port='COM10',use_synthetic=False,cyton_eeg_count=8)

    worker = AcquisitionWorker(board_config=board_cfg)

    print("=" * 50)
    print("第 6 课 — AcquisitionWorker 测试")
    print("=" * 50)

    worker.start()
    try:
        for sec in range(10):
            time.sleep(1)
            print(f"  t={sec + 1:2d}s  samples_pushed={worker.get_samples_pushed()}")
    finally:
        print("正在 stop()...")
        worker.stop()

    print(f"结束。总推送约 {worker.get_samples_pushed()} 个 EEG 样本")
    print("第 6 课验收完成。")

if __name__ == "__main__":
    main()