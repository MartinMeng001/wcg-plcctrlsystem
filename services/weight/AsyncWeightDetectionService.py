"""
异步重量检测服务 - 优化实时性能
将数据存储从实时检测中分离出来
"""

import threading
import queue
import time
import logging
from collections import deque
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from .models import WeightConfigSet, WeightGradeConfig, WeightDetectionRecord, DetectionStatus
from ..storage.interfaces import IWeightDataStore


class AsyncWeightDetectionService:
    """
    异步重量检测服务
    将实时检测与数据存储分离，确保检测的实时性
    """

    def __init__(self, data_store: IWeightDataStore, buffer_size: int = 1000):
        self.data_store = data_store
        self.current_config: Optional[WeightConfigSet] = None
        self.status = DetectionStatus.INACTIVE

        # 实时数据缓存 - 无锁访问
        self.recent_records = deque(maxlen=100)
        self.config_lock = threading.RLock()  # 配置读写锁

        # 异步处理队列
        self.record_queue = queue.Queue(maxsize=buffer_size)
        self.statistics_queue = queue.Queue(maxsize=buffer_size)

        # 异步处理线程
        self.storage_thread = None
        self.statistics_thread = None
        self.running = False

        # 性能监控
        self.performance_stats = {
            'detection_count': 0,
            'avg_detection_time': 0.0,
            'queue_overflow_count': 0,
            'last_detection_time': 0.0
        }

        self.logger = logging.getLogger(__name__)

        # 加载配置并启动后台线程
        self.reload_config()
        self.start_background_threads()

    def start_background_threads(self):
        """启动后台处理线程"""
        if self.running:
            return

        self.running = True

        # 数据存储线程
        self.storage_thread = threading.Thread(
            target=self._storage_worker,
            name="WeightStorage",
            daemon=True
        )
        self.storage_thread.start()

        # 统计更新线程
        self.statistics_thread = threading.Thread(
            target=self._statistics_worker,
            name="WeightStatistics",
            daemon=True
        )
        self.statistics_thread.start()

        self.logger.info("异步处理线程已启动")

    def stop_background_threads(self):
        """停止后台处理线程"""
        self.running = False

        # 等待队列处理完成
        if self.storage_thread:
            self.storage_thread.join(timeout=5.0)
        if self.statistics_thread:
            self.statistics_thread.join(timeout=5.0)

        self.logger.info("异步处理线程已停止")

    def _storage_worker(self):
        """数据存储工作线程"""
        batch_records = []
        batch_size = 10  # 批量处理提高效率
        last_flush_time = time.time()

        while self.running:
            try:
                # 从队列获取记录，非阻塞模式
                try:
                    record = self.record_queue.get(timeout=0.1)
                    batch_records.append(record)
                except queue.Empty:
                    pass

                # 批量保存条件：达到批量大小或超时
                current_time = time.time()
                should_flush = (
                        len(batch_records) >= batch_size or
                        (batch_records and current_time - last_flush_time > 1.0)
                )

                if should_flush:
                    self._save_batch_records(batch_records)
                    batch_records.clear()
                    last_flush_time = current_time

            except Exception as e:
                self.logger.error(f"存储线程异常: {e}")
                time.sleep(0.1)

        # 线程退出时保存剩余记录
        if batch_records:
            self._save_batch_records(batch_records)

    def _statistics_worker(self):
        """统计更新工作线程"""
        while self.running:
            try:
                try:
                    record = self.statistics_queue.get(timeout=0.1)
                    self.data_store.update_statistics(record)
                except queue.Empty:
                    pass
            except Exception as e:
                self.logger.error(f"统计线程异常: {e}")
                time.sleep(0.1)

    def _save_batch_records(self, records: List[WeightDetectionRecord]):
        """批量保存记录"""
        for record in records:
            if self.data_store.save_detection_record(record):
                # 更新内存缓存
                self.recent_records.appendleft(record)
            else:
                self.logger.error(f"保存记录失败: {record.id}")

    def reload_config(self) -> bool:
        """重新加载配置 - 线程安全"""
        try:
            config = self.data_store.load_config()
            if config:
                is_valid, message = config.validate()
                if not is_valid:
                    self.logger.error(f"配置验证失败: {message}")
                    return False

                with self.config_lock:
                    self.current_config = config

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
        """更新配置 - 线程安全"""
        # 验证配置
        is_valid, message = config_set.validate()
        if not is_valid:
            return False, message

        # 更新时间戳和版本
        config_set.updated_at = datetime.now()
        with self.config_lock:
            if self.current_config:
                config_set.version = self.current_config.version + 1

        # 保存到数据库（异步）
        if self.data_store.save_config(config_set):
            with self.config_lock:
                self.current_config = config_set
            self.logger.info(f"配置更新成功，版本: {config_set.version}")
            return True, "配置更新成功"
        else:
            return False, "配置保存失败"

    def get_current_config(self) -> Optional[WeightConfigSet]:
        """获取当前配置 - 线程安全"""
        with self.config_lock:
            return self.current_config

    def determine_grade_fast(self, weight: float) -> Tuple[Optional[int], Optional[int]]:
        """
        快速确定分级和踢出通道 - 优化版本
        无锁访问，专为实时检测优化
        """
        # 获取配置快照，避免长时间持有锁
        with self.config_lock:
            config = self.current_config

        if not config:
            return None, None

        enabled_configs = [c for c in config.configs if c.enabled]
        if not enabled_configs:
            return None, None

        # 二分查找优化（如果配置较多）
        if len(enabled_configs) > 5:
            return self._binary_search_grade(weight, enabled_configs)
        else:
            # 线性查找（配置较少时更快）
            for config_item in enabled_configs:
                if weight <= config_item.weight_threshold:
                    return config_item.grade_id, config_item.kick_channel

            # 超过所有阈值，使用最后一个分级
            last_config = enabled_configs[-1]
            return last_config.grade_id, last_config.kick_channel

    def _binary_search_grade(self, weight: float, configs: List[WeightGradeConfig]) -> Tuple[int, int]:
        """二分查找分级（优化大量配置的情况）"""
        left, right = 0, len(configs) - 1

        while left <= right:
            mid = (left + right) // 2
            if weight <= configs[mid].weight_threshold:
                if mid == 0 or weight > configs[mid - 1].weight_threshold:
                    return configs[mid].grade_id, configs[mid].kick_channel
                right = mid - 1
            else:
                left = mid + 1

        # 超过所有阈值
        last_config = configs[-1]
        return last_config.grade_id, last_config.kick_channel

    def process_detection_fast(self, weight: float) -> WeightDetectionRecord:
        """
        快速处理检测 - 实时优化版本
        只进行必要的计算，存储操作异步处理
        """
        start_time = time.perf_counter()

        timestamp = datetime.now()
        grade, kick_channel = self.determine_grade_fast(weight)

        if grade is None or grade == 1:
            record = WeightDetectionRecord(
                id=0,
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

        # 异步保存记录
        if record.detection_success:
            try:
                self.record_queue.put_nowait(record)
                self.statistics_queue.put_nowait(record)
            except queue.Full:
                self.performance_stats['queue_overflow_count'] += 1
                self.logger.warning("队列已满，丢弃记录")

        # 更新性能统计
        detection_time = time.perf_counter() - start_time
        self._update_performance_stats(detection_time)

        return record

    def _update_performance_stats(self, detection_time: float):
        """更新性能统计"""
        stats = self.performance_stats
        stats['detection_count'] += 1
        stats['last_detection_time'] = detection_time

        # 计算移动平均
        alpha = 0.1  # 平滑因子
        if stats['avg_detection_time'] == 0:
            stats['avg_detection_time'] = detection_time
        else:
            stats['avg_detection_time'] = (
                    alpha * detection_time +
                    (1 - alpha) * stats['avg_detection_time']
            )

    def get_recent_records(self, limit: int = 100) -> List[WeightDetectionRecord]:
        """获取最近的检测记录"""
        # 优先从内存缓存获取
        memory_records = list(self.recent_records)[:limit]

        if len(memory_records) >= limit:
            return memory_records
        else:
            # 从数据库补充
            db_records = self.data_store.get_recent_records(limit)
            return db_records

    def get_daily_statistics(self, target_date: Optional[date] = None):
        """获取指定日期的统计数据"""
        if target_date is None:
            target_date = date.today()

        return self.data_store.get_daily_statistics(target_date)

    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        stats = self.performance_stats.copy()
        stats.update({
            'record_queue_size': self.record_queue.qsize(),
            'statistics_queue_size': self.statistics_queue.qsize(),
            'recent_records_count': len(self.recent_records),
            'background_threads_running': self.running
        })
        return stats

    def get_status(self) -> Dict:
        """获取服务状态"""
        recent_count = len(self.recent_records)
        last_detection = self.recent_records[0].timestamp if recent_count > 0 else None

        config_info = None
        with self.config_lock:
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
            "config_info": config_info,
            "performance": self.get_performance_stats()
        }

    def __del__(self):
        """析构函数，确保线程正确关闭"""
        self.stop_background_threads()