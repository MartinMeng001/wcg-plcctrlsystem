"""
服务层入口模块
提供服务层的主要接口和工厂方法
"""

from .weight.AsyncWeightDetectionService import AsyncWeightDetectionService
from .storage.sqlite_store import SQLiteWeightDataStore

# 全局变量来存储单例实例
_service_instance = None

def create_weight_service(db_path: str = "weight_detection.db") -> AsyncWeightDetectionService:
    """
    创建并返回重量检测服务的单例实例。
    """
    global _service_instance
    if _service_instance is None:
        data_store = SQLiteWeightDataStore(db_path)
        _service_instance = AsyncWeightDetectionService(data_store)
    return _service_instance

__all__ = [
    'AsyncWeightDetectionService',
    'SQLiteWeightDataStore',
    'create_weight_service'
]