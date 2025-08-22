"""
重量检测服务主类
"""

import logging
import threading
from collections import deque
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from .models import WeightConfigSet, WeightGradeConfig, WeightDetectionRecord, DetectionStatus
from ..storage.interfaces import IWeightDataStore


class WeightDetectionService:
    """重量检测服务主类"""

    def __init__(self, data_store: IWeightDataStore):
        self.data_store = data_store
        self.current_config: Optional[WeightConfigSet] = None
        self.status = DetectionStatus.INACTIVE
        self.recent_records = deque(maxlen=100)  # 内存中保持最近100条记录
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        # 加载配置
        self.reload_config()

    def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            self.current_config = self.data_store.load_config()
            if self.current_config:
                is_valid, message = self.current_config.validate()
                if not is_valid:
                    self.logger.error(f"配置验证失败: {message}")
                    return False
                self.logger.info("配置加载成功")
                return True
            else:
                self.logger.warning("未找到配置，将使用默认配置")
                return self._create_default_config()
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            return False

    def _create_default_config(self) -> bool:
        """创建默认配置"""
        default_configs = [
            WeightGradeConfig(1, 50.0, 1, True, "轻量级"),
            WeightGradeConfig(2, 100.0, 2, True, "中量级"),
            WeightGradeConfig(3, 150.0, 3, True, "重量级"),
        ]

        config_set = WeightConfigSet(configs=default_configs)
        return self.update_config(config_set)

    def update_config(self, config_set: WeightConfigSet) -> Tuple[bool, str]:
        """更新配置"""
        # 验证配置
        is_valid, message = config_set.validate()
        if not is_valid:
            return False, message

        # 更新时间戳和版本
        config_set.updated_at = datetime.now()
        if self.current_config:
            config_set.version = self.current_config.version + 1

        # 保存到数据库
        if self.data_store.save_config(config_set):
            with self.lock:
                self.current_config = config_set
            self.logger.info(f"配置更新成功，版本: {config_set.version}")
            return True, "配置更新成功"
        else:
            return False, "配置保存失败"

    def get_current_config(self) -> Optional[WeightConfigSet]:
        """获取当前配置"""
        return self.current_config

    def determine_grade(self, weight: float) -> Tuple[Optional[int], Optional[int]]:
        """根据重量确定分级和踢出通道"""
        if not self.current_config:
            return None, None

        enabled_configs = [config for config in self.current_config.configs if config.enabled]
        if not enabled_configs:
            return None, None

        # 按重量阈值查找合适的分级
        for config in enabled_configs:
            if weight <= config.weight_threshold:
                return config.grade_id, config.kick_channel

        # 如果超过所有阈值，使用最后一个分级
        last_config = enabled_configs[-1]
        return last_config.grade_id, last_config.kick_channel

    def process_detection(self, weight: float) -> WeightDetectionRecord:
        """处理一次重量检测"""
        timestamp = datetime.now()
        grade, kick_channel = self.determine_grade(weight)

        if grade is None:
            # 检测失败的情况
            record = WeightDetectionRecord(
                id=0,  # 将在数据库保存时分配
                timestamp=timestamp,
                weight=weight,
                determined_grade=0,
                kick_channel=0,
                detection_success=False
            )
        else:
            record = WeightDetectionRecord(
                id=0,
                timestamp=timestamp,
                weight=weight,
                determined_grade=grade,
                kick_channel=kick_channel,
                detection_success=True
            )

        # 保存记录
        if self.data_store.save_detection_record(record):
            # 更新统计数据
            if record.detection_success:
                self.data_store.update_statistics(record)

            # 更新内存中的最近记录
            with self.lock:
                self.recent_records.appendleft(record)

        return record

    def get_recent_records(self, limit: int = 100) -> List[WeightDetectionRecord]:
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

    def get_daily_statistics(self, target_date: Optional[date] = None):
        """获取指定日期的统计数据"""
        if target_date is None:
            target_date = date.today()

        return self.data_store.get_daily_statistics(target_date)

    def get_status(self) -> Dict:
        """获取服务状态"""
        with self.lock:
            recent_count = len(self.recent_records)
            last_detection = self.recent_records[0].timestamp if recent_count > 0 else None

        config_info = None
        if self.current_config:
            enabled_count = sum(1 for config in self.current_config.configs if config.enabled)
            config_info = {
                "total_grades": len(self.current_config.configs),
                "enabled_grades": enabled_count,
                "version": self.current_config.version,
                "updated_at": self.current_config.updated_at.isoformat()
            }

        return {
            "status": self.status.value,
            "recent_records_count": recent_count,
            "last_detection_time": last_detection.isoformat() if last_detection else None,
            "config_info": config_info
        }