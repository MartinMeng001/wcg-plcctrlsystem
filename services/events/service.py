# services/events/__init__.py
"""
事件监听系统入口模块
"""

from .models import (
    EventType, SortingType, CommunicationStatus,
    BaseEvent, SortingEvent, CommunicationStatusEvent, PulseFrequencyEvent,
    SortingEventRecord, CommunicationStatusRecord, PulseFrequencyRecord,
    EventStatistics
)
from .storage import OptimizedEventDataStore
from .listener import EventListener
# from .service import EventService

__all__ = [
    # 枚举和模型
    'EventType', 'SortingType', 'CommunicationStatus',
    'BaseEvent', 'SortingEvent', 'CommunicationStatusEvent', 'PulseFrequencyEvent',
    'SortingEventRecord', 'CommunicationStatusRecord', 'PulseFrequencyRecord',
    'EventStatistics',

    # 核心类
    'OptimizedEventDataStore', 'EventListener', 'EventService'
]

# services/events/service.py
"""
事件监听服务主类
整合事件监听器和存储，提供统一的服务接口
"""

import asyncio
import threading
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Callable

from .models import (
    EventType, SortingType, CommunicationStatus,
    SortingEvent, CommunicationStatusEvent, PulseFrequencyEvent
)
from .storage import OptimizedEventDataStore
from .listener import EventListener


class EventService:
    """事件监听服务主类"""

    def __init__(self, db_path: str = "events.db", max_queue_size: int = 1000):
        self.db_path = db_path
        self.max_queue_size = max_queue_size

        # 初始化组件
        self.data_store = OptimizedEventDataStore(db_path)
        self.event_listener = EventListener(self.data_store, max_queue_size)

        # 运行状态
        self.running = False
        self.loop = None
        self.loop_thread = None

        # 统计信息
        self.service_stats = {
            'start_time': None,
            'total_events_processed': 0,
            'sorting_events_count': 0,
            'communication_events_count': 0,
            'pulse_frequency_events_count': 0
        }

        self.logger = logging.getLogger(__name__)

        # 注册内置事件处理器
        self._register_internal_handlers()

    def _register_internal_handlers(self):
        """注册内置事件处理器"""

        async def on_sorting_event(event: SortingEvent):
            """分拣事件处理器"""
            self.service_stats['sorting_events_count'] += 1
            self.service_stats['total_events_processed'] += 1
            self.logger.info(f"分拣事件: {event.sorting_type.value}, 通道{event.channels}, 数量{event.count}")

        async def on_communication_event(event: CommunicationStatusEvent):
            """通讯状态事件处理器"""
            self.service_stats['communication_events_count'] += 1
            self.service_stats['total_events_processed'] += 1
            self.logger.info(f"通讯状态变更: {event.device_name} {event.old_status} -> {event.new_status}")

        async def on_pulse_frequency_event(event: PulseFrequencyEvent):
            """脉冲频率事件处理器"""
            self.service_stats['pulse_frequency_events_count'] += 1
            self.service_stats['total_events_processed'] += 1
            self.logger.info(f"脉冲频率: {event.frequency}Hz, 周期: {event.period}s")

        # 注册所有分拣事件处理器
        for event_type in [
            EventType.SORTING_REJECT_CH1, EventType.SORTING_REJECT_CH2,
            EventType.SORTING_REJECT_CH3, EventType.SORTING_REJECT_CH4,
            EventType.SORTING_QUALIFIED_TYPE1, EventType.SORTING_QUALIFIED_TYPE2,
            EventType.SORTING_QUALIFIED_TYPE3
        ]:
            self.event_listener.register_handler(event_type, on_sorting_event)

        # 注册通讯状态事件处理器
        self.event_listener.register_handler(EventType.PLC_COMMUNICATION_STATUS, on_communication_event)
        self.event_listener.register_handler(EventType.SUGAR_COMMUNICATION_STATUS, on_communication_event)

        # 注册脉冲频率事件处理器
        self.event_listener.register_handler(EventType.PHOTOELECTRIC_PULSE_FREQUENCY, on_pulse_frequency_event)

    def start(self):
        """启动事件服务"""
        if self.running:
            self.logger.warning("事件服务已在运行")
            return

        self.running = True
        self.service_stats['start_time'] = datetime.now()

        # 在独立线程中运行事件循环
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()

        self.logger.info("事件服务已启动")

    def stop(self):
        """停止事件服务"""
        if not self.running:
            return

        self.running = False

        # 停止事件循环
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        # 等待线程结束
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=5.0)

        self.logger.info("事件服务已停止")

    def _run_event_loop(self):
        """在独立线程中运行事件循环"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            # 启动事件监听器
            self.loop.run_until_complete(self.event_listener.start())

            # 运行事件循环
            self.loop.run_forever()

        except Exception as e:
            self.logger.error(f"事件循环异常: {e}")
        finally:
            # 停止事件监听器
            try:
                self.loop.run_until_complete(self.event_listener.stop())
            except:
                pass

            self.loop.close()

    # ========== 事件发送接口 ==========

    def emit_sorting_reject_event(self, channel: int, count: int = 1,
                                  weight: Optional[float] = None,
                                  grade: Optional[int] = None,
                                  source_data: Optional[Dict[str, Any]] = None):
        """发送不合格品分拣事件"""
        if channel not in [1, 2, 3, 4]:
            self.logger.warning(f"无效的产品通道: {channel}")
            return

        self._emit_async(self.event_listener.emit_sorting_event(
            sorting_type=SortingType.REJECT,
            channels=[channel],
            count=count,
            weight=weight,
            grade=grade,
            source_data=source_data
        ))

    def emit_sorting_qualified_event(self, qualified_type: int, count: int = 1,
                                     weight: Optional[float] = None,
                                     grade: Optional[int] = None,
                                     source_data: Optional[Dict[str, Any]] = None):
        """发送合格品分拣事件"""
        type_channel_map = {
            1: ([5, 6], SortingType.QUALIFIED_TYPE1),
            2: ([7, 8], SortingType.QUALIFIED_TYPE2),
            3: ([9, 10], SortingType.QUALIFIED_TYPE3)
        }

        if qualified_type not in type_channel_map:
            self.logger.warning(f"无效的合格品类型: {qualified_type}")
            return

        channels, sorting_type = type_channel_map[qualified_type]

        self._emit_async(self.event_listener.emit_sorting_event(
            sorting_type=sorting_type,
            channels=channels,
            count=count,
            weight=weight,
            grade=grade,
            source_data=source_data
        ))

    def emit_plc_communication_status_event(self, new_status: CommunicationStatus,
                                            error_message: Optional[str] = None,
                                            connection_info: Optional[Dict[str, Any]] = None):
        """发送PLC通讯状态变更事件"""
        self._emit_async(self.event_listener.emit_communication_status_event(
            device_name="PLC",
            new_status=new_status,
            error_message=error_message,
            connection_info=connection_info
        ))

    def emit_sugar_communication_status_event(self, new_status: CommunicationStatus,
                                              error_message: Optional[str] = None,
                                              connection_info: Optional[Dict[str, Any]] = None):
        """发送糖度检测器通讯状态变更事件"""
        self._emit_async(self.event_listener.emit_communication_status_event(
            device_name="Sugar_Detector",
            new_status=new_status,
            error_message=error_message,
            connection_info=connection_info
        ))

    def emit_pulse_frequency_event(self, frequency: float, period: float,
                                   pulse_count: int, measurement_duration: float,
                                   pulse_timestamps: Optional[List[float]] = None):
        """发送光电脉冲频率事件"""
        self._emit_async(self.event_listener.emit_pulse_frequency_event(
            frequency=frequency,
            period=period,
            pulse_count=pulse_count,
            measurement_duration=measurement_duration,
            pulse_timestamps=pulse_timestamps
        ))

    def _emit_async(self, coro):
        """异步发送事件"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            self.logger.warning("事件循环未运行，无法发送事件")

    # ========== 扩展接口 ==========

    def register_custom_handler(self, event_type: EventType, handler: Callable):
        """注册自定义事件处理器"""
        self.event_listener.register_handler(event_type, handler)

    def unregister_custom_handler(self, event_type: EventType, handler: Callable):
        """取消注册自定义事件处理器"""
        self.event_listener.unregister_handler(event_type, handler)

    def get_current_communication_status(self, device_name: str) -> Optional[CommunicationStatus]:
        """获取当前通讯状态"""
        return self.event_listener.get_current_communication_status(device_name)

    def get_recent_pulse_frequency(self, count: int = 10) -> List[Dict[str, Any]]:
        """获取最近的脉冲频率数据"""
        return self.event_listener.get_recent_pulse_frequency(count)

    def get_service_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        listener_stats = self.event_listener.get_event_statistics()

        return {
            'service': self.service_stats.copy(),
            'listener': listener_stats,
            'running': self.running,
            'loop_running': self.loop and self.loop.is_running() if self.loop else False
        }

    # ========== 数据查询接口（异步） ==========

    async def get_sorting_events_async(self,
                                       start_time: Optional[datetime] = None,
                                       end_time: Optional[datetime] = None,
                                       event_types: Optional[List[EventType]] = None,
                                       limit: int = 100):
        """异步查询分拣事件"""
        return await self.data_store.get_sorting_events(start_time, end_time, event_types, limit)

    async def get_communication_events_async(self,
                                             device_name: Optional[str] = None,
                                             start_time: Optional[datetime] = None,
                                             end_time: Optional[datetime] = None,
                                             limit: int = 100):
        """异步查询通讯状态事件"""
        return await self.data_store.get_communication_status_events(device_name, start_time, end_time, limit)

    async def get_pulse_frequency_events_async(self,
                                               start_time: Optional[datetime] = None,
                                               end_time: Optional[datetime] = None,
                                               limit: int = 100):
        """异步查询脉冲频率事件"""
        return await self.data_store.get_pulse_frequency_events(start_time, end_time, limit)

    async def cleanup_old_events_async(self, days_to_keep: int = 30):
        """异步清理旧事件"""
        await self.data_store.cleanup_old_events(days_to_keep)


# 全局事件服务实例
_event_service_instance: Optional[EventService] = None


def get_event_service() -> EventService:
    """获取全局事件服务实例"""
    global _event_service_instance
    if _event_service_instance is None:
        _event_service_instance = EventService()
    return _event_service_instance


def create_event_service(db_path: str = "events.db", max_queue_size: int = 1000) -> EventService:
    """创建新的事件服务实例"""
    return EventService(db_path, max_queue_size)