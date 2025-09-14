"""
事件监听系统入口模块
"""

from .models import (
    EventType, SortingType, CommunicationStatus,
    BaseEvent, SortingEvent, CommunicationStatusEvent, PulseFrequencyEvent,
    SortingEventRecord, CommunicationStatusRecord, PulseFrequencyRecord,
    EventStatistics
)
#from .service import EventDataStore, SyncEventDataStore
from .storage import OptimizedEventDataStore, BatchConfig
from .listener import EventListener
from .service import EventService

# 全局事件服务实例
_event_service = None


def init_event_service(db_path: str = "events.db",
                       batch_config: BatchConfig = None,
                       use_optimized_storage: bool = True):
    """初始化全局事件服务实例"""
    global _event_service
    if _event_service is None:
        # 根据参数选择存储实现
        if use_optimized_storage:
            # 使用优化版存储（批量提交）
            if batch_config is None:
                batch_config = BatchConfig(
                    batch_size=30,
                    flush_interval=2.0,
                    max_buffer_size=300
                )
            data_store = OptimizedEventDataStore(db_path, batch_config)
        else:
            # 使用原版存储（立即提交）
            data_store = OptimizedEventDataStore(db_path)

        # 创建事件服务实例
        _event_service = EventService.__new__(EventService)
        _event_service.data_store = data_store
        _event_service.event_listener = EventListener(data_store)

        # 手动初始化其他属性
        _event_service.running = False
        _event_service.loop = None
        _event_service.loop_thread = None
        _event_service.service_stats = {
            'start_time': None,
            'total_events_processed': 0,
            'sorting_events_count': 0,
            'communication_events_count': 0,
            'pulse_frequency_events_count': 0
        }

        import logging
        _event_service.logger = logging.getLogger('EventService')

        # 调用原有的初始化方法
        _event_service._register_internal_handlers()

        print(f"全局事件服务已初始化: {db_path} (优化存储: {use_optimized_storage})")

    return _event_service


def get_event_service():
    """获取全局事件服务实例"""
    global _event_service
    if _event_service is None:
        # 如果还没初始化，使用默认配置初始化
        return init_event_service()
    return _event_service


def reset_event_service():
    """重置全局事件服务实例（主要用于测试）"""
    global _event_service
    if _event_service and _event_service.running:
        _event_service.stop()
    _event_service = None


# 导出所有相关类和函数
__all__ = [
    # 枚举和模型
    'EventType', 'SortingType', 'CommunicationStatus',
    'BaseEvent', 'SortingEvent', 'CommunicationStatusEvent', 'PulseFrequencyEvent',
    'SortingEventRecord', 'CommunicationStatusRecord', 'PulseFrequencyRecord',
    'EventStatistics',

    # 核心类
    'OptimizedEventDataStore', 'BatchConfig',
    'EventListener', 'EventService',

    # 全局实例管理函数
    'init_event_service', 'get_event_service', 'reset_event_service'
]