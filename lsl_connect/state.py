"""
第 7 课：服务级状态机定义与转移规则。
对应需求文档 §5.4。
"""
from __future__ import annotations

from enum import Enum
from typing import FrozenSet,Tuple

class ServiceStatus(str,Enum):
    """ServiceManager 主状态。"""

    IDLE = "IDLE"
    STARTING = "STREAMING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


# (当前状态, 目标状态) 是否允许
_ALLOWED_TRANSITIONS:FrozenSet[Tuple[ServiceStatus,ServiceStatus]] = frozenset(
   {
    (ServiceStatus.IDLE,ServiceStatus.STARTING),
    (ServiceStatus.STARTING,ServiceStatus.RUNNING),
    (ServiceStatus.STARTING,ServiceStatus.ERROR),
    (ServiceStatus.RUNNING,ServiceStatus.IDLE),
    (ServiceStatus.RUNNING,ServiceStatus.STOPPING),
    (ServiceStatus.STOPPING,ServiceStatus.ERROR),
    (ServiceStatus.ERROR,ServiceStatus.IDLE),
    (ServiceStatus.ERROR,ServiceStatus.STOPPING),
   }
)
def can_transition(from_status: ServiceStatus, to_status: ServiceStatus) -> bool:
    """是否允许从 from_state 转到 to_state。"""
    if from_status ==to_status:
        return True
    return (from_status,to_status) in _ALLOWED_TRANSITIONS

def may_start(state: ServiceStatus) -> bool:
    return state == ServiceStatus.IDLE

def may_stop(state: ServiceStatus) -> bool:
    return state in (ServiceStatus.RUNNING, ServiceStatus.ERROR)

def may_reset(state: ServiceStatus) -> bool:
    """ERROR 可 reset 回 IDLE。"""
    return state == ServiceStatus.ERROR

