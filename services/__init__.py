"""
服务层入口模块 - 修复循环导入
提供服务层的主要接口和工厂方法
"""

from .weight.AsyncWeightDetectionService import AsyncWeightDetectionService
from .storage.sqlite_store import SQLiteWeightDataStore

# 全局变量来存储单例实例
_weight_service_instance = None
_sugar_service_instance = None

def create_weight_service(db_path: str = "weight_detection.db") -> AsyncWeightDetectionService:
    """
    创建并返回重量检测服务的单例实例。
    """
    global _weight_service_instance
    if _weight_service_instance is None:
        data_store = SQLiteWeightDataStore(db_path)
        _weight_service_instance = AsyncWeightDetectionService(data_store)
    return _weight_service_instance

def create_sugar_service(db_path: str = "sugar_detection.db"):
    """
    创建并返回糖度检测服务的单例实例。
    """
    global _sugar_service_instance
    if _sugar_service_instance is None:
        # 延迟导入避免循环导入
        from .sugar.service import SugarDetectionService
        from .sugar.sqlite_store import SQLiteSugarDataStore

        data_store = SQLiteSugarDataStore(db_path)
        _sugar_service_instance = SugarDetectionService(data_store)
    return _sugar_service_instance

__all__ = [
    'AsyncWeightDetectionService',
    'SQLiteWeightDataStore',
    'create_weight_service',
    'create_sugar_service'
]