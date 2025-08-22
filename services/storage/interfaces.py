"""
存储层接口定义
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date

# 导入数据模型（从weight模块）
from ..weight.models import WeightConfigSet, WeightDetectionRecord, WeightStatistics


class IWeightDataStore(ABC):
    """重量数据存储接口"""

    @abstractmethod
    def save_config(self, config_set: WeightConfigSet) -> bool:
        """保存配置"""
        pass

    @abstractmethod
    def load_config(self) -> Optional[WeightConfigSet]:
        """加载配置"""
        pass

    @abstractmethod
    def save_detection_record(self, record: WeightDetectionRecord) -> bool:
        """保存检测记录"""
        pass

    @abstractmethod
    def get_recent_records(self, limit: int = 100) -> List[WeightDetectionRecord]:
        """获取最近的检测记录"""
        pass

    @abstractmethod
    def get_daily_statistics(self, target_date: date) -> List[WeightStatistics]:
        """获取指定日期的统计数据"""
        pass

    @abstractmethod
    def update_statistics(self, record: WeightDetectionRecord):
        """更新统计数据"""
        pass