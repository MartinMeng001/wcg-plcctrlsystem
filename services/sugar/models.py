# services/sugar/models.py
"""
糖度检测相关数据模型
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from enum import Enum


class SugarDetectionStatus(Enum):
    """糖度检测状态枚举"""
    INACTIVE = "inactive"
    COLLECTING = "collecting"
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class SugarDetectionRecord:
    """糖度检测记录"""
    id: int
    timestamp: datetime
    sugar_content: float  # 糖度值
    acid_content: Optional[float] = None  # 酸度值
    serial_number: Optional[int] = None  # 流水号
    exception_code: Optional[int] = None  # 异常码
    detection_success: bool = True  # 检测是否成功

    def __post_init__(self):
        if self.sugar_content < 0:
            raise ValueError("糖度值不能为负数")


@dataclass
class SugarStatistics:
    """糖度检测统计数据"""
    date: date
    total_count: int = 0  # 当天检测总数
    success_count: int = 0  # 成功检测数
    failed_count: int = 0  # 失败检测数
    sugar_sum: float = 0.0  # 糖度总和
    sugar_avg: float = 0.0  # 平均糖度
    acid_sum: float = 0.0  # 酸度总和
    acid_avg: float = 0.0  # 平均酸度
    acid_count: int = 0  # 有效酸度检测数

    def add_record(self, record: SugarDetectionRecord):
        """添加一条记录到统计中"""
        self.total_count += 1

        if record.detection_success:
            self.success_count += 1
            self.sugar_sum += record.sugar_content
            self.sugar_avg = self.sugar_sum / self.success_count

            if record.acid_content is not None:
                self.acid_count += 1
                self.acid_sum += record.acid_content
                self.acid_avg = self.acid_sum / self.acid_count if self.acid_count > 0 else 0.0
        else:
            self.failed_count += 1