"""
第 7 课：服务级状态机定义与转移规则。
对应需求文档 §5.4。
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Tuple


class ServiceState(str, Enum):
    """ServiceManager 主状态。"""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


_ALLOWED_TRANSITIONS: FrozenSet[Tuple[ServiceState, ServiceState]] = frozenset(
    {
        (ServiceState.IDLE, ServiceState.STARTING),
        (ServiceState.STARTING, ServiceState.RUNNING),
        (ServiceState.STARTING, ServiceState.ERROR),
        (ServiceState.RUNNING, ServiceState.STOPPING),
        (ServiceState.RUNNING, ServiceState.ERROR),
        (ServiceState.STOPPING, ServiceState.IDLE),
        (ServiceState.ERROR, ServiceState.STOPPING),
        (ServiceState.ERROR, ServiceState.IDLE),
    }
)


def can_transition(from_state: ServiceState, to_state: ServiceState) -> bool:
    """是否允许从 from_state 转到 to_state。"""
    if from_state == to_state:
        return True
    return (from_state, to_state) in _ALLOWED_TRANSITIONS


def may_start(state: ServiceState) -> bool:
    """仅 IDLE 可 start（§5.4.3）。"""
    return state == ServiceState.IDLE


def may_stop(state: ServiceState) -> bool:
    """RUNNING / ERROR 可 stop。"""
    return state in (ServiceState.RUNNING, ServiceState.ERROR)


def may_reset(state: ServiceState) -> bool:
    """ERROR 可 reset 回 IDLE。"""
    return state == ServiceState.ERROR
