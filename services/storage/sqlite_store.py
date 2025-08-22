"""
SQLite数据存储实现
"""

import sqlite3
import threading
import logging
from datetime import datetime, date
from typing import List, Optional

from .interfaces import IWeightDataStore
from ..weight.models import WeightConfigSet, WeightGradeConfig, WeightDetectionRecord, WeightStatistics


class SQLiteWeightDataStore(IWeightDataStore):
    """基于SQLite的重量数据存储实现"""

    def __init__(self, db_path: str = "weight_detection.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
        self.logger = logging.getLogger(__name__)

    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 配置表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS weight_configs
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               grade_id
                               INTEGER
                               NOT
                               NULL,
                               weight_threshold
                               REAL
                               NOT
                               NULL,
                               kick_channel
                               INTEGER
                               NOT
                               NULL,
                               enabled
                               BOOLEAN
                               NOT
                               NULL,
                               description
                               TEXT,
                               version
                               INTEGER
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP,
                               updated_at
                               TIMESTAMP
                           )
                           ''')

            # 检测记录表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS detection_records
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               timestamp
                               TIMESTAMP
                               NOT
                               NULL,
                               weight
                               REAL
                               NOT
                               NULL,
                               determined_grade
                               INTEGER
                               NOT
                               NULL,
                               kick_channel
                               INTEGER
                               NOT
                               NULL,
                               detection_success
                               BOOLEAN
                               NOT
                               NULL
                               DEFAULT
                               1
                           )
                           ''')

            # 统计数据表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS daily_statistics
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
                               grade_id
                               INTEGER
                               NOT
                               NULL,
                               total_count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               0,
                               weight_sum
                               REAL
                               NOT
                               NULL
                               DEFAULT
                               0.0,
                               weight_avg
                               REAL
                               NOT
                               NULL
                               DEFAULT
                               0.0,
                               UNIQUE
                           (
                               date,
                               grade_id
                           )
                               )
                           ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_records_timestamp ON detection_records(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_statistics_date ON daily_statistics(date)')

            conn.commit()

    def save_config(self, config_set: WeightConfigSet) -> bool:
        """保存配置"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    # 删除旧配置
                    cursor.execute('DELETE FROM weight_configs')

                    # 插入新配置
                    for config in config_set.configs:
                        cursor.execute('''
                                       INSERT INTO weight_configs
                                       (grade_id, weight_threshold, kick_channel, enabled, description, version,
                                        created_at, updated_at)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                       ''', (
                                           config.grade_id, config.weight_threshold, config.kick_channel,
                                           config.enabled, config.description, config_set.version,
                                           config_set.created_at.isoformat(), config_set.updated_at.isoformat()
                                       ))

                    conn.commit()
                    return True
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False

    def load_config(self) -> Optional[WeightConfigSet]:
        """加载配置"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                               SELECT grade_id,
                                      weight_threshold,
                                      kick_channel,
                                      enabled,
                                      description,
                                      version,
                                      created_at,
                                      updated_at
                               FROM weight_configs
                               ORDER BY weight_threshold
                               ''')

                rows = cursor.fetchall()
                if not rows:
                    return None

                configs = []
                version = 1
                created_at = datetime.now()
                updated_at = datetime.now()

                for row in rows:
                    configs.append(WeightGradeConfig(
                        grade_id=row[0],
                        weight_threshold=row[1],
                        kick_channel=row[2],
                        enabled=bool(row[3]),
                        description=row[4] or ""
                    ))
                    version = row[5]
                    created_at = datetime.fromisoformat(row[6]) if row[6] else created_at
                    updated_at = datetime.fromisoformat(row[7]) if row[7] else updated_at

                return WeightConfigSet(
                    configs=configs,
                    version=version,
                    created_at=created_at,
                    updated_at=updated_at
                )
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            return None

    def save_detection_record(self, record: WeightDetectionRecord) -> bool:
        """保存检测记录"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                                   INSERT INTO detection_records
                                       (timestamp, weight, determined_grade, kick_channel, detection_success)
                                   VALUES (?, ?, ?, ?, ?)
                                   ''', (
                                       record.timestamp.isoformat(), record.weight, record.determined_grade,
                                       record.kick_channel, record.detection_success
                                   ))

                    # 获取插入的记录ID
                    record.id = cursor.lastrowid
                    conn.commit()
                    return True
        except Exception as e:
            self.logger.error(f"保存检测记录失败: {e}")
            return False

    def get_recent_records(self, limit: int = 100) -> List[WeightDetectionRecord]:
        """获取最近的检测记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                               SELECT id, timestamp, weight, determined_grade, kick_channel, detection_success
                               FROM detection_records
                               ORDER BY timestamp DESC
                                   LIMIT ?
                               ''', (limit,))

                rows = cursor.fetchall()
                records = []

                for row in rows:
                    records.append(WeightDetectionRecord(
                        id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        weight=row[2],
                        determined_grade=row[3],
                        kick_channel=row[4],
                        detection_success=bool(row[5])
                    ))

                return records
        except Exception as e:
            self.logger.error(f"获取检测记录失败: {e}")
            return []

    def get_daily_statistics(self, target_date: date) -> List[WeightStatistics]:
        """获取指定日期的统计数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                               SELECT date, grade_id, total_count, weight_sum, weight_avg
                               FROM daily_statistics
                               WHERE date = ?
                               ORDER BY grade_id
                               ''', (target_date.isoformat(),))

                rows = cursor.fetchall()
                statistics = []

                for row in rows:
                    statistics.append(WeightStatistics(
                        date=date.fromisoformat(row[0]),
                        grade_id=row[1],
                        total_count=row[2],
                        weight_sum=row[3],
                        weight_avg=row[4]
                    ))

                return statistics
        except Exception as e:
            self.logger.error(f"获取统计数据失败: {e}")
            return []

    def update_statistics(self, record: WeightDetectionRecord):
        """更新统计数据"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    record_date = record.timestamp.date()

                    # 检查是否已存在该日期和分级的统计记录
                    cursor.execute('''
                                   SELECT total_count, weight_sum
                                   FROM daily_statistics
                                   WHERE date = ? AND grade_id = ?
                                   ''', (record_date.isoformat(), record.determined_grade))

                    existing = cursor.fetchone()

                    if existing:
                        # 更新现有记录
                        new_count = existing[0] + 1
                        new_sum = existing[1] + record.weight
                        new_avg = new_sum / new_count

                        cursor.execute('''
                                       UPDATE daily_statistics
                                       SET total_count = ?,
                                           weight_sum  = ?,
                                           weight_avg  = ?
                                       WHERE date = ? AND grade_id = ?
                                       ''',
                                       (new_count, new_sum, new_avg, record_date.isoformat(), record.determined_grade))
                    else:
                        # 创建新记录
                        cursor.execute('''
                                       INSERT INTO daily_statistics (date, grade_id, total_count, weight_sum, weight_avg)
                                       VALUES (?, ?, ?, ?, ?)
                                       ''', (record_date.isoformat(), record.determined_grade, 1, record.weight,
                                             record.weight))

                    conn.commit()
        except Exception as e:
            self.logger.error(f"更新统计数据失败: {e}")