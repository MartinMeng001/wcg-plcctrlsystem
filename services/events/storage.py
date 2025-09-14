# services/events/optimized_storage.py
"""
优化的事件数据存储实现
采用批量提交、连接池和缓冲区策略提升性能
"""

import asyncio
import aiosqlite
import threading
import logging
import json
import time
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Deque
from collections import deque
from dataclasses import dataclass

from .models import (
    SortingEvent, CommunicationStatusEvent, PulseFrequencyEvent,
    SortingEventRecord, CommunicationStatusRecord, PulseFrequencyRecord,
    EventStatistics, EventType
)


@dataclass
class BatchConfig:
    """批量提交配置"""
    batch_size: int = 50  # 批量大小
    flush_interval: float = 2.0  # 强制刷新间隔（秒）
    max_buffer_size: int = 500  # 最大缓冲区大小
    connection_pool_size: int = 3  # 连接池大小


class EventBuffer:
    """事件缓冲区"""

    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self.sorting_events: Deque[SortingEvent] = deque()
        self.communication_events: Deque[CommunicationStatusEvent] = deque()
        self.pulse_frequency_events: Deque[PulseFrequencyEvent] = deque()
        self.last_flush_time = time.time()
        self._lock = threading.Lock()

    def add_sorting_event(self, event: SortingEvent):
        """添加分拣事件到缓冲区"""
        with self._lock:
            self.sorting_events.append(event)
            if len(self.sorting_events) > self.max_size:
                self.sorting_events.popleft()

    def add_communication_event(self, event: CommunicationStatusEvent):
        """添加通讯事件到缓冲区"""
        with self._lock:
            self.communication_events.append(event)
            if len(self.communication_events) > self.max_size:
                self.communication_events.popleft()

    def add_pulse_frequency_event(self, event: PulseFrequencyEvent):
        """添加脉冲频率事件到缓冲区"""
        with self._lock:
            self.pulse_frequency_events.append(event)
            if len(self.pulse_frequency_events) > self.max_size:
                self.pulse_frequency_events.popleft()

    def get_batch(self, batch_size: int) -> Dict[str, List]:
        """获取一批事件进行处理"""
        with self._lock:
            batch = {
                'sorting': [],
                'communication': [],
                'pulse_frequency': []
            }

            # 获取分拣事件批次
            for _ in range(min(batch_size, len(self.sorting_events))):
                if self.sorting_events:
                    batch['sorting'].append(self.sorting_events.popleft())

            # 获取通讯事件批次
            for _ in range(min(batch_size, len(self.communication_events))):
                if self.communication_events:
                    batch['communication'].append(self.communication_events.popleft())

            # 获取脉冲频率事件批次
            for _ in range(min(batch_size, len(self.pulse_frequency_events))):
                if self.pulse_frequency_events:
                    batch['pulse_frequency'].append(self.pulse_frequency_events.popleft())

            return batch

    def get_total_size(self) -> int:
        """获取缓冲区总大小"""
        with self._lock:
            return len(self.sorting_events) + len(self.communication_events) + len(self.pulse_frequency_events)

    def should_flush(self, batch_size: int, flush_interval: float) -> bool:
        """判断是否应该刷新缓冲区"""
        with self._lock:
            total_size = self.get_total_size()
            time_elapsed = time.time() - self.last_flush_time

            return (
                    total_size >= batch_size or  # 达到批量大小
                    (total_size > 0 and time_elapsed >= flush_interval) or  # 超时且有数据
                    total_size >= self.max_size * 0.8  # 缓冲区接近满
            )

    def update_flush_time(self):
        """更新刷新时间"""
        with self._lock:
            self.last_flush_time = time.time()


class OptimizedEventDataStore:
    """优化的事件数据存储类"""

    def __init__(self, db_path: str = "events.db", batch_config: BatchConfig = None):
        self.db_path = db_path
        self.batch_config = batch_config or BatchConfig()

        # 缓冲区
        self.buffer = EventBuffer(self.batch_config.max_buffer_size)

        # 批处理控制
        self.batch_processor_running = False
        self.batch_processor_task = None

        # 统计信息
        self.stats = {
            'total_events_buffered': 0,
            'total_events_saved': 0,
            'total_batches_processed': 0,
            'batch_save_failures': 0,
            'avg_batch_size': 0,
            'avg_batch_process_time': 0
        }

        self.logger = logging.getLogger(__name__)

        # 同步初始化数据库
        self._init_database_sync()

    def _init_database_sync(self):
        """同步方式初始化数据库表结构"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 分拣事件表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS sorting_events
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               event_id
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               event_type
                               TEXT
                               NOT
                               NULL,
                               sorting_type
                               TEXT
                               NOT
                               NULL,
                               channels
                               TEXT
                               NOT
                               NULL, -- JSON array
                               count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               1,
                               weight
                               REAL,
                               grade
                               INTEGER,
                               timestamp
                               TIMESTAMP
                               NOT
                               NULL,
                               source_data
                               TEXT, -- JSON string
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            # 通讯状态变更事件表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS communication_status_events
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               event_id
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               device_name
                               TEXT
                               NOT
                               NULL,
                               old_status
                               TEXT,
                               new_status
                               TEXT
                               NOT
                               NULL,
                               error_message
                               TEXT,
                               connection_info
                               TEXT, -- JSON string
                               timestamp
                               TIMESTAMP
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            # 光电脉冲频率事件表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS pulse_frequency_events
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               event_id
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               frequency
                               REAL
                               NOT
                               NULL,
                               period
                               REAL
                               NOT
                               NULL,
                               pulse_count
                               INTEGER
                               NOT
                               NULL,
                               measurement_duration
                               REAL
                               NOT
                               NULL,
                               timestamp
                               TIMESTAMP
                               NOT
                               NULL,
                               pulse_data
                               TEXT, -- JSON string for pulse_timestamps
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            # 事件统计表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS event_statistics
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               date
                               DATE
                               NOT
                               NULL,
                               event_type
                               TEXT
                               NOT
                               NULL,
                               total_count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               0,
                               avg_frequency
                               REAL,
                               error_count
                               INTEGER
                               DEFAULT
                               0,
                               success_count
                               INTEGER
                               DEFAULT
                               0,
                               UNIQUE
                           (
                               date,
                               event_type
                           )
                               )
                           ''')

            # 创建索引
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_sorting_events_timestamp ON sorting_events(timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_sorting_events_type ON sorting_events(event_type)',
                'CREATE INDEX IF NOT EXISTS idx_communication_events_device ON communication_status_events(device_name)',
                'CREATE INDEX IF NOT EXISTS idx_communication_events_timestamp ON communication_status_events(timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_pulse_events_timestamp ON pulse_frequency_events(timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_statistics_date ON event_statistics(date)'
            ]

            for index_sql in indexes:
                cursor.execute(index_sql)

            conn.commit()

        self.logger.info("优化版事件数据库初始化完成")

    async def start_batch_processor(self):
        """启动批处理器"""
        if self.batch_processor_running:
            return

        self.batch_processor_running = True
        self.batch_processor_task = asyncio.create_task(self._batch_processor_loop())
        self.logger.info("批处理器已启动")

    async def stop_batch_processor(self):
        """停止批处理器"""
        if not self.batch_processor_running:
            return

        self.batch_processor_running = False

        if self.batch_processor_task:
            self.batch_processor_task.cancel()
            try:
                await self.batch_processor_task
            except asyncio.CancelledError:
                pass

        # 处理剩余的缓冲区数据
        await self._flush_buffer(force=True)
        self.logger.info("批处理器已停止")

    async def _batch_processor_loop(self):
        """批处理主循环"""
        self.logger.info("批处理循环已启动")

        while self.batch_processor_running:
            try:
                # 检查是否需要刷新缓冲区
                if self.buffer.should_flush(
                        self.batch_config.batch_size,
                        self.batch_config.flush_interval
                ):
                    await self._flush_buffer()

                # 休眠一小段时间
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"批处理循环异常: {e}")
                await asyncio.sleep(1.0)

    async def _flush_buffer(self, force: bool = False):
        """刷新缓冲区数据到数据库"""
        batch_size = self.batch_config.batch_size

        # 如果强制刷新，使用更大的批量大小
        if force:
            batch_size = self.buffer.get_total_size()

        if batch_size == 0:
            return

        start_time = time.time()
        batch = self.buffer.get_batch(batch_size)

        # 计算实际批量大小
        actual_batch_size = (
                len(batch['sorting']) +
                len(batch['communication']) +
                len(batch['pulse_frequency'])
        )

        if actual_batch_size == 0:
            return

        try:
            # 批量保存到数据库
            async with aiosqlite.connect(self.db_path) as db:
                # 开始事务
                await db.execute('BEGIN TRANSACTION')

                try:
                    # 批量插入分拣事件
                    if batch['sorting']:
                        await self._batch_insert_sorting_events(db, batch['sorting'])

                    # 批量插入通讯事件
                    if batch['communication']:
                        await self._batch_insert_communication_events(db, batch['communication'])

                    # 批量插入脉冲频率事件
                    if batch['pulse_frequency']:
                        await self._batch_insert_pulse_frequency_events(db, batch['pulse_frequency'])

                    # 提交事务
                    await db.commit()

                    # 更新统计
                    self.stats['total_events_saved'] += actual_batch_size
                    self.stats['total_batches_processed'] += 1

                    # 更新平均批量大小
                    if self.stats['total_batches_processed'] > 0:
                        self.stats['avg_batch_size'] = (
                                self.stats['total_events_saved'] /
                                self.stats['total_batches_processed']
                        )

                    # 更新处理时间
                    process_time = time.time() - start_time
                    if self.stats['total_batches_processed'] == 1:
                        self.stats['avg_batch_process_time'] = process_time
                    else:
                        # 指数移动平均
                        alpha = 0.1
                        self.stats['avg_batch_process_time'] = (
                                alpha * process_time +
                                (1 - alpha) * self.stats['avg_batch_process_time']
                        )

                    self.buffer.update_flush_time()

                    # 记录批处理信息
                    if actual_batch_size >= 10:  # 只记录较大的批次
                        self.logger.info(
                            f"批处理完成: {actual_batch_size}个事件, "
                            f"耗时{process_time * 1000:.1f}ms"
                        )

                except Exception as e:
                    # 回滚事务
                    await db.rollback()
                    self.stats['batch_save_failures'] += 1
                    self.logger.error(f"批处理事务失败: {e}")
                    raise

        except Exception as e:
            self.stats['batch_save_failures'] += 1
            self.logger.error(f"批处理保存失败: {e}")
            # 注意：这里我们不重新抛出异常，以避免影响主事件循环

    async def _batch_insert_sorting_events(self, db: aiosqlite.Connection, events: List[SortingEvent]):
        """批量插入分拣事件"""
        if not events:
            return

        data = []
        for event in events:
            data.append((
                event.event_id,
                event.event_type.value,
                event.sorting_type.value,
                json.dumps(event.channels),
                event.count,
                event.weight,
                event.grade,
                event.timestamp.isoformat(),
                json.dumps(event.source_data) if event.source_data else None
            ))

        await db.executemany('''
                             INSERT
                             OR IGNORE INTO sorting_events 
            (event_id, event_type, sorting_type, channels, count, weight, grade, timestamp, source_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                             ''', data)

        # 批量更新统计
        await self._batch_update_sorting_statistics(db, events)

    async def _batch_insert_communication_events(self, db: aiosqlite.Connection,
                                                 events: List[CommunicationStatusEvent]):
        """批量插入通讯事件"""
        if not events:
            return

        data = []
        for event in events:
            data.append((
                event.event_id,
                event.device_name,
                event.old_status.value if event.old_status else None,
                event.new_status.value,
                event.error_message,
                json.dumps(event.connection_info) if event.connection_info else None,
                event.timestamp.isoformat()
            ))

        await db.executemany('''
                             INSERT
                             OR IGNORE INTO communication_status_events 
            (event_id, device_name, old_status, new_status, error_message, connection_info, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
                             ''', data)

        # 批量更新统计
        await self._batch_update_communication_statistics(db, events)

    async def _batch_insert_pulse_frequency_events(self, db: aiosqlite.Connection, events: List[PulseFrequencyEvent]):
        """批量插入脉冲频率事件"""
        if not events:
            return

        data = []
        for event in events:
            data.append((
                event.event_id,
                event.frequency,
                event.period,
                event.pulse_count,
                event.measurement_duration,
                event.timestamp.isoformat(),
                json.dumps(event.pulse_timestamps) if event.pulse_timestamps else None
            ))

        await db.executemany('''
                             INSERT
                             OR IGNORE INTO pulse_frequency_events 
            (event_id, frequency, period, pulse_count, measurement_duration, timestamp, pulse_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
                             ''', data)

        # 批量更新统计
        await self._batch_update_pulse_frequency_statistics(db, events)

    async def _batch_update_sorting_statistics(self, db: aiosqlite.Connection, events: List[SortingEvent]):
        """批量更新分拣事件统计"""
        if not events:
            return

        # 按日期和事件类型分组统计
        stats_updates = {}

        for event in events:
            event_date = event.timestamp.date().isoformat()
            event_type = event.event_type.value
            key = (event_date, event_type)

            if key not in stats_updates:
                stats_updates[key] = {
                    'total_count': 0,
                    'success_count': 0
                }

            stats_updates[key]['total_count'] += event.count
            if event.grade and event.grade > 0:
                stats_updates[key]['success_count'] += event.count

        # 批量更新统计表
        for (event_date, event_type), stats in stats_updates.items():
            await db.execute('''
                INSERT OR REPLACE INTO event_statistics 
                (date, event_type, total_count, success_count)
                VALUES (
                    ?, ?, 
                    COALESCE((SELECT total_count FROM event_statistics WHERE date = ? AND event_type = ?), 0) + ?,
                    COALESCE((SELECT success_count FROM event_statistics WHERE date = ? AND event_type = ?), 0) + ?
                )
            ''', (
                event_date, event_type,
                event_date, event_type, stats['total_count'],
                event_date, event_type, stats['success_count']
            ))

    async def _batch_update_communication_statistics(self, db: aiosqlite.Connection,
                                                     events: List[CommunicationStatusEvent]):
        """批量更新通讯事件统计"""
        if not events:
            return

        stats_updates = {}

        for event in events:
            event_date = event.timestamp.date().isoformat()
            event_type = event.event_type.value
            key = (event_date, event_type)

            if key not in stats_updates:
                stats_updates[key] = {
                    'total_count': 0,
                    'error_count': 0,
                    'success_count': 0
                }

            stats_updates[key]['total_count'] += 1

            is_error = event.new_status.value in ['error', 'disconnected', 'timeout']
            if is_error:
                stats_updates[key]['error_count'] += 1
            else:
                stats_updates[key]['success_count'] += 1

        # 批量更新统计表
        for (event_date, event_type), stats in stats_updates.items():
            await db.execute('''
                INSERT OR REPLACE INTO event_statistics 
                (date, event_type, total_count, error_count, success_count)
                VALUES (
                    ?, ?, 
                    COALESCE((SELECT total_count FROM event_statistics WHERE date = ? AND event_type = ?), 0) + ?,
                    COALESCE((SELECT error_count FROM event_statistics WHERE date = ? AND event_type = ?), 0) + ?,
                    COALESCE((SELECT success_count FROM event_statistics WHERE date = ? AND event_type = ?), 0) + ?
                )
            ''', (
                event_date, event_type,
                event_date, event_type, stats['total_count'],
                event_date, event_type, stats['error_count'],
                event_date, event_type, stats['success_count']
            ))

    async def _batch_update_pulse_frequency_statistics(self, db: aiosqlite.Connection,
                                                       events: List[PulseFrequencyEvent]):
        """批量更新脉冲频率统计"""
        if not events:
            return

        stats_updates = {}

        for event in events:
            event_date = event.timestamp.date().isoformat()
            event_type = event.event_type.value
            key = (event_date, event_type)

            if key not in stats_updates:
                stats_updates[key] = {
                    'total_count': 0,
                    'frequency_sum': 0.0,
                    'frequency_count': 0
                }

            stats_updates[key]['total_count'] += 1
            stats_updates[key]['frequency_sum'] += event.frequency
            stats_updates[key]['frequency_count'] += 1

        # 批量更新统计表
        for (event_date, event_type), stats in stats_updates.items():
            avg_frequency = stats['frequency_sum'] / stats['frequency_count']

            await db.execute('''
                INSERT OR REPLACE INTO event_statistics 
                (date, event_type, total_count, avg_frequency)
                SELECT 
                    ? as date,
                    ? as event_type,
                    COALESCE(old_stats.total_count, 0) + ? as total_count,
                    (COALESCE(old_stats.avg_frequency * old_stats.total_count, 0) + ?) / 
                    (COALESCE(old_stats.total_count, 0) + ?) as avg_frequency
                FROM (
                    SELECT total_count, avg_frequency 
                    FROM event_statistics 
                    WHERE date = ? AND event_type = ?
                    UNION ALL 
                    SELECT 0, 0 WHERE NOT EXISTS (
                        SELECT 1 FROM event_statistics WHERE date = ? AND event_type = ?
                    )
                    LIMIT 1
                ) as old_stats
            ''', (
                event_date, event_type, stats['total_count'],
                stats['frequency_sum'], stats['total_count'],
                event_date, event_type,
                event_date, event_type
            ))

    # ========== 公共接口方法 ==========

    async def save_sorting_event(self, event: SortingEvent) -> bool:
        """保存分拣事件到缓冲区"""
        try:
            self.buffer.add_sorting_event(event)
            self.stats['total_events_buffered'] += 1
            return True
        except Exception as e:
            self.logger.error(f"缓冲分拣事件失败: {e}")
            return False

    async def save_communication_status_event(self, event: CommunicationStatusEvent) -> bool:
        """保存通讯状态事件到缓冲区"""
        try:
            self.buffer.add_communication_event(event)
            self.stats['total_events_buffered'] += 1
            return True
        except Exception as e:
            self.logger.error(f"缓冲通讯事件失败: {e}")
            return False

    async def save_pulse_frequency_event(self, event: PulseFrequencyEvent) -> bool:
        """保存脉冲频率事件到缓冲区"""
        try:
            self.buffer.add_pulse_frequency_event(event)
            self.stats['total_events_buffered'] += 1
            return True
        except Exception as e:
            self.logger.error(f"缓冲脉冲频率事件失败: {e}")
            return False

    # ========== 查询方法（保持与原版本兼容） ==========

    async def get_sorting_events(self,
                                 start_time: Optional[datetime] = None,
                                 end_time: Optional[datetime] = None,
                                 event_types: Optional[List[EventType]] = None,
                                 limit: int = 100) -> List[SortingEventRecord]:
        """查询分拣事件记录"""
        try:
            query = "SELECT * FROM sorting_events WHERE 1=1"
            params = []

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            if event_types:
                placeholders = ','.join('?' * len(event_types))
                query += f" AND event_type IN ({placeholders})"
                params.extend([et.value for et in event_types])

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                    records = []
                    for row in rows:
                        records.append(SortingEventRecord(
                            id=row[0],
                            event_id=row[1],
                            event_type=row[2],
                            sorting_type=row[3],
                            channels=row[4],
                            count=row[5],
                            weight=row[6],
                            grade=row[7],
                            timestamp=datetime.fromisoformat(row[8]) if row[8] else None,
                            source_data=row[9]
                        ))

                    return records

        except Exception as e:
            self.logger.error(f"查询分拣事件失败: {e}")
            return []

    # 其他查询方法与原版本保持一致...
    # [这里保留原有的查询方法，代码太长省略]

    def get_storage_statistics(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        buffer_stats = {
            'buffer_size': self.buffer.get_total_size(),
            'sorting_events_buffered': len(self.buffer.sorting_events),
            'communication_events_buffered': len(self.buffer.communication_events),
            'pulse_frequency_events_buffered': len(self.buffer.pulse_frequency_events),
        }

        return {
            'batch_config': {
                'batch_size': self.batch_config.batch_size,
                'flush_interval': self.batch_config.flush_interval,
                'max_buffer_size': self.batch_config.max_buffer_size
            },
            'buffer_stats': buffer_stats,
            'processing_stats': self.stats.copy(),
            'batch_processor_running': self.batch_processor_running
        }