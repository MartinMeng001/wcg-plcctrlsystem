"""
服务层入口模块
提供服务层的主要接口和工厂方法
"""

from .weight.service import WeightDetectionService
from .storage.sqlite_store import SQLiteWeightDataStore

def create_weight_service(db_path: str = "weight_detection.db") -> WeightDetectionService:
    """创建重量检测服务实例"""
    data_store = SQLiteWeightDataStore(db_path)
    return WeightDetectionService(data_store)

__all__ = [
    'WeightDetectionService',
    'SQLiteWeightDataStore',
    'create_weight_service'
]