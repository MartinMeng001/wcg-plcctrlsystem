# services/events/models.py
"""
事件监听系统的数据模型定义
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class EventType(Enum):
    """事件类型枚举"""
    # 分拣事件
    SORTING_REJECT_CH1 = "sorting_reject_ch1"
    SORTING_REJECT_CH2 = "sorting_reject_ch2"
    SORTING_REJECT_CH3 = "sorting_reject_ch3"
    SORTING_REJECT_CH4 = "sorting_reject_ch4"
    SORTING_QUALIFIED_TYPE1 = "sorting_qualified_type1"  # 通道5,6
    SORTING_QUALIFIED_TYPE2 = "sorting_qualified_type2"  # 通道7,8
    SORTING_QUALIFIED_TYPE3 = "sorting_qualified_type3"  # 通道9,10

    # 通讯状态事件
    PLC_COMMUNICATION_STATUS = "plc_communication_status"
    SUGAR_COMMUNICATION_STATUS = "sugar_communication_status"

    # 光电脉冲频率事件
    PHOTOELECTRIC_PULSE_FREQUENCY = "photoelectric_pulse_frequency"


class SortingType(Enum):
    """分拣类型枚举"""
    REJECT = "reject"  # 不合格品
    QUALIFIED_TYPE1 = "qualified_type1"  # 合格品类型1
    QUALIFIED_TYPE2 = "qualified_type2"  # 合格品类型2
    QUALIFIED_TYPE3 = "qualified_type3"  # 合格品类型3


class CommunicationStatus(Enum):
    """通讯状态枚举"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TIMEOUT = "timeout"
    RECONNECTING = "reconnecting"


@dataclass
class BaseEvent:
    """事件基类"""
    event_type: EventType
    timestamp: datetime
    event_id: Optional[str]  # 事件唯一标识
    metadata: Optional[Dict[str, Any]]  # 附加元数据

    def __post_init__(self):
        if self.event_id is None:
            # 生成唯一事件ID
            import uuid
            self.event_id = str(uuid.uuid4())


@dataclass
class SortingEvent(BaseEvent):
    """分拣事件"""
    sorting_type: SortingType
    channels: list[int]  # 涉及的通道号列表
    count: int = 1  # 分拣数量
    weight: Optional[float] = None  # 物品重量
    grade: Optional[int] = None  # 分拣等级
    source_data: Optional[Dict[str, Any]] = None  # 原始数据


@dataclass
class CommunicationStatusEvent(BaseEvent):
    """通讯状态变更事件"""
    device_name: str  # 设备名称 (PLC, Sugar_Detector等)
    old_status: Optional[CommunicationStatus]
    new_status: CommunicationStatus
    error_message: Optional[str] = None
    connection_info: Optional[Dict[str, Any]] = None  # 连接信息(IP, 端口等)


@dataclass
class PulseFrequencyEvent(BaseEvent):
    """光电脉冲频率事件"""
    frequency: float  # 频率 (Hz)
    period: float  # 周期 (秒)
    pulse_count: int  # 统计周期内的脉冲数量
    measurement_duration: float  # 测量时长 (秒)
    pulse_timestamps: Optional[list[float]] = None  # 脉冲时间戳列表


# 数据库记录模型
@dataclass
class SortingEventRecord:
    """分拣事件数据库记录"""
    id: Optional[int] = None
    event_id: str = ""
    event_type: str = ""
    sorting_type: str = ""
    channels: str = ""  # JSON字符串存储通道列表
    count: int = 1
    weight: Optional[float] = None
    grade: Optional[int] = None
    timestamp: Optional[datetime] = None
    source_data: Optional[str] = None  # JSON字符串


@dataclass
class CommunicationStatusRecord:
    """通讯状态变更记录"""
    id: Optional[int] = None
    event_id: str = ""
    device_name: str = ""
    old_status: Optional[str] = None
    new_status: str = ""
    error_message: Optional[str] = None
    connection_info: Optional[str] = None  # JSON字符串
    timestamp: Optional[datetime] = None


@dataclass
class PulseFrequencyRecord:
    """光电脉冲频率记录"""
    id: Optional[int] = None
    event_id: str = ""
    frequency: float = 0.0
    period: float = 0.0
    pulse_count: int = 0
    measurement_duration: float = 0.0
    timestamp: Optional[datetime] = None
    pulse_data: Optional[str] = None  # JSON字符串存储详细脉冲数据


@dataclass
class EventStatistics:
    """事件统计数据"""
    date: datetime
    event_type: str
    total_count: int = 0
    avg_frequency: Optional[float] = None  # 针对频率事件
    error_count: int = 0  # 针对通讯事件
    success_count: int = 0