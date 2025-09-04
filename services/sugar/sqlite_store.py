"""
糖度检测数据的SQLite存储实现
"""

import sqlite3
import threading
import logging
from datetime import datetime, date
from typing import List, Optional

from .interfaces import ISugarDataStore
from .models import SugarDetectionRecord, SugarStatistics


class SQLiteSugarDataStore(ISugarDataStore):
    """基于SQLite的糖度数据存储实现"""

    def __init__(self, db_path: str = "sugar_detection.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
        self.logger = logging.getLogger(__name__)

    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 糖度检测记录表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS sugar_detection_records
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
                               sugar_content
                               REAL
                               NOT
                               NULL,
                               acid_content
                               REAL,
                               serial_number
                               INTEGER,
                               exception_code
                               INTEGER,
                               detection_success
                               BOOLEAN
                               NOT
                               NULL
                               DEFAULT
                               1
                           )
                           ''')

            # 糖度统计数据表
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS sugar_daily_statistics
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               date
                               DATE
                               NOT
                               NULL
                               UNIQUE,
                               total_count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               0,
                               success_count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               0,
                               failed_count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               0,
                               sugar_sum
                               REAL
                               NOT
                               NULL
                               DEFAULT
                               0.0,
                               sugar_avg
                               REAL
                               NOT
                               NULL
                               DEFAULT
                               0.0,
                               acid_sum
                               REAL
                               NOT
                               NULL
                               DEFAULT
                               0.0,
                               acid_avg
                               REAL
                               NOT
                               NULL
                               DEFAULT
                               0.0,
                               acid_count
                               INTEGER
                               NOT
                               NULL
                               DEFAULT
                               0
                           )
                           ''')

            # 创建索引
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_sugar_records_timestamp ON sugar_detection_records(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sugar_statistics_date ON sugar_daily_statistics(date)')

            conn.commit()

    def save_detection_record(self, record: SugarDetectionRecord) -> bool:
        """保存检测记录"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                                   INSERT INTO sugar_detection_records
                                   (timestamp, sugar_content, acid_content, serial_number, exception_code,
                                    detection_success)
                                   VALUES (?, ?, ?, ?, ?, ?)
                                   ''', (
                                       record.timestamp.isoformat(),
                                       record.sugar_content,
                                       record.acid_content,
                                       record.serial_number,
                                       record.exception_code,
                                       record.detection_success
                                   ))

                    # 获取分配的ID
                    record.id = cursor.lastrowid
                    conn.commit()
                    return True
        except Exception as e:
            self.logger.error(f"保存糖度检测记录失败: {e}")
            return False

    def get_recent_records(self, limit: int = 100) -> List[SugarDetectionRecord]:
        """获取最近的检测记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                               SELECT id, timestamp, sugar_content, acid_content, serial_number, exception_code, detection_success
                               FROM sugar_detection_records
                               ORDER BY timestamp DESC
                                   LIMIT ?
                               ''', (limit,))

                records = []
                for row in cursor.fetchall():
                    records.append(SugarDetectionRecord(
                        id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        sugar_content=row[2],
                        acid_content=row[3],
                        serial_number=row[4],
                        exception_code=row[5],
                        detection_success=bool(row[6])
                    ))

                return records
        except Exception as e:
            self.logger.error(f"获取糖度检测记录失败: {e}")
            return []

    def get_daily_statistics(self, target_date: date) -> Optional[SugarStatistics]:
        """获取指定日期的统计数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                               SELECT total_count,
                                      success_count,
                                      failed_count,
                                      sugar_sum,
                                      sugar_avg,
                                      acid_sum,
                                      acid_avg,
                                      acid_count
                               FROM sugar_daily_statistics
                               WHERE date = ?
                               ''', (target_date.isoformat(),))

                row = cursor.fetchone()
                if row:
                    return SugarStatistics(
                        date=target_date,
                        total_count=row[0],
                        success_count=row[1],
                        failed_count=row[2],
                        sugar_sum=row[3],
                        sugar_avg=row[4],
                        acid_sum=row[5],
                        acid_avg=row[6],
                        acid_count=row[7]
                    )
                else:
                    return SugarStatistics(date=target_date)

        except Exception as e:
            self.logger.error(f"获取糖度统计数据失败: {e}")
            return SugarStatistics(date=target_date)

    def update_statistics(self, record: SugarDetectionRecord):
        """更新统计数据"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    record_date = record.timestamp.date().isoformat()

                    # 使用INSERT OR REPLACE更新统计
                    cursor.execute('''
                        INSERT OR REPLACE INTO sugar_daily_statistics 
                        (date, total_count, success_count, failed_count, 
                         sugar_sum, sugar_avg, acid_sum, acid_avg, acid_count)
                        SELECT ?, 
                            COALESCE(total_count, 0) + 1,
                            COALESCE(success_count, 0) + ?,
                            COALESCE(failed_count, 0) + ?,
                            COALESCE(sugar_sum, 0) + ?,
                            0,
                            COALESCE(acid_sum, 0) + ?,
                            0,
                            COALESCE(acid_count, 0) + ?
                        FROM (
                            SELECT * FROM sugar_daily_statistics WHERE date = ?
                            UNION SELECT ?, 0, 0, 0, 0, 0, 0, 0, 0
                            LIMIT 1
                        )
                    ''', (
                        record_date,
                        1 if record.detection_success else 0,
                        0 if record.detection_success else 1,
                        record.sugar_content if record.detection_success else 0,
                        record.acid_content if (record.detection_success and record.acid_content) else 0,
                        1 if (record.detection_success and record.acid_content) else 0,
                        record_date,
                        record_date
                    ))

                    # 重新计算平均值
                    cursor.execute('''
                                   UPDATE sugar_daily_statistics
                                   SET sugar_avg = CASE WHEN success_count > 0 THEN sugar_sum / success_count ELSE 0 END,
                                       acid_avg  = CASE WHEN acid_count > 0 THEN acid_sum / acid_count ELSE 0 END
                                   WHERE date = ?
                                   ''', (record_date,))

                    conn.commit()

        except Exception as e:
            self.logger.error(f"更新糖度统计数据失败: {e}")