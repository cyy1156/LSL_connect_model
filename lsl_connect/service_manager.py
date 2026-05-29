"""
第 7 课：服务管理器 — 状态机 + AcquisitionWorker。
第 8 课 CLI 将调用本模块。
"""

from __future__ import annotations
import threading
from dataclasses import dataclass
from typing import Any,Dict,Optional

from lsl_connect.acquisition_work import AcquisitionWorker,AcquisitionConfig
from lsl_connect.board import BoardConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.state import (
         ServiceStatus,
         can_transition,
         may_reset,
         may_start,
         may_stop,
)

from lsl_connect.lsl_streams import LslStreamConfig
@dataclass
class ServiceManagerConfig:
    """ServiceManager 持有的默认配置（第 9 课可改为从 YAML 加载）。"""
    board_config: BoardConfig
    lsl: LslStreamConfig
    preprocess: PreprocessConfig
    acquisition: AcquisitionConfig

class ServiceManager:
    """
      管理采集服务生命周期。
      用法:
          mgr = ServiceManager()
          mgr.start_acquisition()
          print(mgr.get_status())
          mgr.stop_acquisition()
    """
    def __int__(self,config:Optional[ServiceManagerConfig]=None)->None:
        if config is None:
            board = BoardConfig(use_synthetic=True,cyton_eeg_count=8)
            config = ServiceManagerConfig(

                board_config=board,
                lsl=LslStreamConfig(
                    sample_rate=250,
                    channel_count=board.cyton_eeg_count,
                    use_synthetic=board.use_synthetic,
                ),
                preprocess=PreprocessConfig(sample_rate=250),
                acquisition=AcquisitionConfig()
            )
            self.config = config
            self._lock = threading.Lock()
            self._worker:Optional[AcquisitionWorker]=None
            self._last_error:Optional[str]=None

    def get_status(self) -> ServiceStatus:
        with self._lock:
            return self._state

    def _set_state(self,new_state:ServiceStatus)->None:
        with self._lock:
            if not can_transition(self._state,new_state):
                raise RuntimeError(
                    f"非法状态转移: {self._state.value} -> {new_state.value}"
                )
            self._state = new_state

    def start_acquisition(self)->bool:
        """
                启动采集。仅 IDLE 允许。
                成功 → RUNNING；失败 → ERROR。
        """
        with self._lock:
            if not may_start(self._state):
                return False

        self._set_state(ServiceStatus.RUNNING)
        self._last_error = None

        try:
            worker = AcquisitionWorker(
                board_config=self.config.board_config,
                lsl_config=self.config.lsl,
                preprocess_config=self._config.preprocess,
                acq_config=self._config.acquisition,
            )
            worker.start()
            with self._lock:
               self._worker = worker
               self._set_state(ServiceStatus.RUNNING)
               return True
        except Exception as exc:
            self.last_error =str(exc)
            if self._worker is not None:
                try:
                    self._worker.stop()
                except Exception :
                    pass
                self._worker =None
            self._set_state(ServiceStatus.ERROR)
            return False
