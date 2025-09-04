# services/sugar/interfaces.py
"""
糖度数据存储接口定义 - 独立文件避免循环导入
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from .models import SugarDetectionRecord, SugarStatistics


class ISugarDataStore(ABC):
    """糖度数据存储接口"""

    @abstractmethod
    def save_detection_record(self, record: SugarDetectionRecord) -> bool:
        """保存检测记录"""
        pass

    @abstractmethod
    def get_recent_records(self, limit: int = 100) -> List[SugarDetectionRecord]:
        """获取最近的检测记录"""
        pass

    @abstractmethod
    def get_daily_statistics(self, target_date: date) -> Optional[SugarStatistics]:
        """获取指定日期的统计数据"""
        pass

    @abstractmethod
    def update_statistics(self, record: SugarDetectionRecord):
        """更新统计数据"""
        pass