"""
OpenBCI EEG 控制面板入口 — 第 8 课。
用法: python eeg_control_panel.py
"""
from __future__ import annotations



from lsl_connect.acquisition_work import AcquisitionConfig
from lsl_connect.board import BoardConfig
from lsl_connect.cli import ControlPanel
from lsl_connect.lsl_streams import LslStreamConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.service_manager import ServiceManager,ServiceManagerConfig
from lsl_connect.config_loader import  build_service_manager_config

def build_manager() ->ServiceManager:
     """ #合成板
      board = BoardConfig(use_synthetic=True,cyton_eeg_count=8)
      #真机
      # board = BoardConfig(serial_port="COM10", use_synthetic=False, cyton_eeg_count=8)
      config =ServiceManagerConfig(
          board_config=board,
          lsl=LslStreamConfig(
              sample_rate=250,
              channel_count=board.cyton_eeg_count,
              use_synthetic=board.use_synthetic,
          ),
          preprocess=PreprocessConfig(sample_rate=250,filter_enabled=True),
          acquisition=AcquisitionConfig(
              quiet=True,  # CLI：后台不 print，避免打断 > 提示符
              stats_every_n_batches=0,
          ),
      )
      """
     config,msg=build_service_manager_config()
     print(f"[配置]{msg}")
     mgr = ServiceManager(config)
     print(f"[模型] {mgr.get_models_message()}")
     return mgr
def main()->None:
    manager = build_manager()
    panel = ControlPanel(manager)
    panel.run()
if __name__ == "__main__":
    main()