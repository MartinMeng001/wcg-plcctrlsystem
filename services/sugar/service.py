# services/sugar/service.py
"""
糖度检测服务主类
"""

import logging
import threading
from collections import deque
from datetime import datetime, date
from typing import Dict, List, Optional

from .models import SugarDetectionRecord, SugarStatistics, SugarDetectionStatus
from .interfaces import ISugarDataStore


class SugarDetectionService:
    """糖度检测服务主类"""

    def __init__(self, data_store: ISugarDataStore):
        self.data_store = data_store
        self.status = SugarDetectionStatus.INACTIVE
        self.recent_records = deque(maxlen=100)  # 内存中保持最近100条记录
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def process_detection(self, sugar_content: float, acid_content: Optional[float] = None,
                         serial_number: Optional[int] = None,
                         exception_code: Optional[int] = None) -> SugarDetectionRecord:
        """处理一次糖度检测"""
        timestamp = datetime.now()

        # 检测成功的条件：糖度值有效且无异常码
        detection_success = (sugar_content is not None and
                           sugar_content >= 0 and
                           (exception_code is None or exception_code == 0))

        record = SugarDetectionRecord(
            id=0,  # 将在数据库保存时分配
            timestamp=timestamp,
            sugar_content=sugar_content,
            acid_content=acid_content,
            serial_number=serial_number,
            exception_code=exception_code,
            detection_success=detection_success
        )

        # 保存记录
        if self.data_store.save_detection_record(record):
            # 更新统计数据
            self.data_store.update_statistics(record)

            # 更新内存中的最近记录
            with self.lock:
                self.recent_records.appendleft(record)

        return record

    def get_recent_records(self, limit: int = 100) -> List[SugarDetectionRecord]:
        """获取最近的检测记录"""
        # 优先从内存获取，如果不足则从数据库补充
        with self.lock:
            memory_records = list(self.recent_records)[:limit]

        if len(memory_records) >= limit:
            return memory_records
        else:
            # 从数据库获取更多记录
            db_records = self.data_store.get_recent_records(limit)
            return db_records

    def get_daily_statistics(self, target_date: Optional[date] = None) -> SugarStatistics:
        """获取指定日期的统计数据"""
        if target_date is None:
            target_date = date.today()

        stats = self.data_store.get_daily_statistics(target_date)
        return stats if stats else SugarStatistics(date=target_date)

    def get_status(self) -> Dict:
        """获取服务状态"""
        with self.lock:
            recent_count = len(self.recent_records)
            last_detection = self.recent_records[0].timestamp if recent_count > 0 else None

        return {
            "status": self.status.value,
            "recent_records_count": recent_count,
            "last_detection_time": last_detection.isoformat() if last_detection else None
        }