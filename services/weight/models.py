"""
重量检测相关数据模型
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from datetime import datetime, date
from enum import Enum


class DetectionStatus(Enum):
    """检测状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CALIBRATING = "calibrating"


@dataclass
class WeightGradeConfig:
    """重量分级配置"""
    grade_id: int  # 分级ID (1-10)
    weight_threshold: float  # 重量阈值(克)
    kick_channel: int  # 踢出通道编号
    enabled: bool = True  # 启用开关
    description: str = ""  # 描述信息

    def __post_init__(self):
        if not 1 <= self.grade_id <= 10:
            raise ValueError("grade_id must be between 1 and 10")
        if self.weight_threshold < 0:
            raise ValueError("weight_threshold must be non-negative")


@dataclass
class WeightConfigSet:
    """完整的重量配置集合"""
    configs: List[WeightGradeConfig] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1

    def __post_init__(self):
        # 按重量阈值排序
        self.configs.sort(key=lambda x: x.weight_threshold)

    def validate(self) -> Tuple[bool, str]:
        """验证配置的有效性"""
        if len(self.configs) == 0:
            return False, "至少需要一个重量分级配置"

        if len(self.configs) > 10:
            return False, "重量分级配置不能超过10个"

        # 检查重量阈值是否严格递增
        for i in range(1, len(self.configs)):
            if self.configs[i].weight_threshold <= self.configs[i - 1].weight_threshold:
                return False, f"重量阈值必须严格递增，第{i + 1}项配置有误"

        # 检查踢出通道是否重复
        channels = [config.kick_channel for config in self.configs if config.enabled]
        if len(channels) != len(set(channels)):
            return False, "启用的配置中踢出通道不能重复"

        return True, "配置验证通过"


@dataclass
class WeightDetectionRecord:
    """重量检测记录"""
    id: int
    timestamp: datetime
    weight: float  # 检测到的重量
    determined_grade: int  # 判定的分级
    kick_channel: int  # 踢出通道
    detection_success: bool = True  # 检测是否成功


@dataclass
class WeightStatistics:
    """重量检测统计数据"""
    date: date
    grade_id: int
    total_count: int = 0  # 当天该分级总数
    weight_sum: float = 0.0  # 当天该分级重量总和
    weight_avg: float = 0.0  # 当天该分级平均重量

    def add_record(self, weight: float):
        """添加一条记录到统计中"""
        self.total_count += 1
        self.weight_sum += weight
        self.weight_avg = self.weight_sum / self.total_count