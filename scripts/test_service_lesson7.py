"""
第 7 课验收：
  start → RUNNING → stop → IDLE
  RUNNING 时再次 start 被拒绝
"""
import time

from lsl_connect.acquisition_work import AcquisitionConfig
from lsl_connect.board import BoardConfig
from lsl_connect.lsl_streams import LslStreamConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.service_manager import ServiceManager, ServiceManagerConfig
from lsl_connect.state import ServiceState


def main() -> None:
    # 合成板
    board_cfg = BoardConfig(use_synthetic=True, cyton_eeg_count=8)

    # 真机（关 GUI）
    # board_cfg = BoardConfig(serial_port="COM10", use_synthetic=False, cyton_eeg_count=8)

    mgr = ServiceManager(
        ServiceManagerConfig(
            board_config=board_cfg,  # 注意：字段名是 board_config，不是 board
            lsl=LslStreamConfig(
                sample_rate=250,
                channel_count=8,
                use_synthetic=board_cfg.use_synthetic,
            ),
            preprocess=PreprocessConfig(sample_rate=250),
            acquisition=AcquisitionConfig(),
        )
    )

    print("=" * 50)
    print("第 7 课 — ServiceManager 测试")
    print("=" * 50)

    assert mgr.get_state() == ServiceState.IDLE
    print("[OK] 初始状态 IDLE")

    ok = mgr.start_acquisition()
    assert ok, "start_acquisition 应成功"
    assert mgr.get_state() == ServiceState.RUNNING
    print("[OK] start 后 RUNNING")
    print(mgr.format_status())

    ok2 = mgr.start_acquisition()
    assert not ok2, "RUNNING 时二次 start 应失败"
    print("[OK] RUNNING 时拒绝重复 start")

    for sec in range(5):
        time.sleep(1)
        st = mgr.get_status()
        print(f"  t={sec + 1}s  state={st['state']}  samples={st['samples_pushed']}")

    ok3 = mgr.stop_acquisition()
    assert ok3, "stop_acquisition 应成功"
    assert mgr.get_state() == ServiceState.IDLE
    print("[OK] stop 后 IDLE")
    print(mgr.format_status())
    print("第 7 课验收完成。")


if __name__ == "__main__":
    main()
