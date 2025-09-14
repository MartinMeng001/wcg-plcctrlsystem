# services/events/listener.py
"""
异步事件监听器
提供事件的异步监听、处理和分发功能
"""

import asyncio
import threading
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any
from collections import defaultdict, deque
import json

from .models import (
    BaseEvent, SortingEvent, CommunicationStatusEvent, PulseFrequencyEvent,
    EventType, SortingType, CommunicationStatus
)
from .storage import OptimizedEventDataStore


class EventListener:
    """异步事件监听器"""

    def __init__(self, data_store: OptimizedEventDataStore, max_queue_size: int = 1000):
        self.data_store = data_store
        self.max_queue_size = max_queue_size

        # 事件队列
        self.event_queue = asyncio.Queue(maxsize=max_queue_size)

        # 事件处理器映射
        self.event_handlers: Dict[EventType, List[Callable]] = defaultdict(list)

        # 运行状态
        self.running = False
        self.processing_task: Optional[asyncio.Task] = None

        # 性能监控
        self.event_stats = {
            'total_processed': 0,
            'failed_count': 0,
            'queue_overflow_count': 0,
            'processing_times': deque(maxlen=100)  # 记录最近100次处理时间
        }

        # 状态缓存
        self.current_communication_status = {
            'PLC': CommunicationStatus.DISCONNECTED,
            'Sugar_Detector': CommunicationStatus.DISCONNECTED
        }

        # 频率统计
        self.pulse_frequency_buffer = deque(maxlen=50)  # 保留最近50次频率数据

        self.logger = logging.getLogger(__name__)

    async def start(self):
        """启动事件监听器"""
        if self.running:
            self.logger.warning("事件监听器已在运行")
            return

        self.running = True
        self.processing_task = asyncio.create_task(self._process_events())
        self.logger.info("事件监听器已启动")

    async def stop(self):
        """停止事件监听器"""
        if not self.running:
            return

        self.running = False

        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

        self.logger.info("事件监听器已停止")

    def register_handler(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        self.event_handlers[event_type].append(handler)
        self.logger.info(f"注册事件处理器: {event_type.value}")

    def unregister_handler(self, event_type: EventType, handler: Callable):
        """取消注册事件处理器"""
        if handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
            self.logger.info(f"取消注册事件处理器: {event_type.value}")

    async def emit_event(self, event: BaseEvent):
        """发送事件到队列"""
        try:
            await asyncio.wait_for(
                self.event_queue.put(event),
                timeout=0.1  # 100ms超时
            )
            self.logger.debug(f"事件已入队: {event.event_type.value}")
        except asyncio.TimeoutError:
            self.event_stats['queue_overflow_count'] += 1
            self.logger.warning(f"事件队列已满，丢弃事件: {event.event_type.value}")

    # ========== 便捷的事件发送方法 ==========

    async def emit_sorting_event(self,
                                 sorting_type: SortingType,
                                 channels: List[int],
                                 count: int = 1,
                                 weight: Optional[float] = None,
                                 grade: Optional[int] = None,
                                 source_data: Optional[Dict[str, Any]] = None):
        """发送分拣事件"""
        # 根据分拣类型和通道确定事件类型
        event_type_map = {
            (SortingType.REJECT, [1]): EventType.SORTING_REJECT_CH1,
            (SortingType.REJECT, [2]): EventType.SORTING_REJECT_CH2,
            (SortingType.REJECT, [3]): EventType.SORTING_REJECT_CH3,
            (SortingType.REJECT, [4]): EventType.SORTING_REJECT_CH4,
            (SortingType.QUALIFIED_TYPE1, [5, 6]): EventType.SORTING_QUALIFIED_TYPE1,
            (SortingType.QUALIFIED_TYPE2, [7, 8]): EventType.SORTING_QUALIFIED_TYPE2,
            (SortingType.QUALIFIED_TYPE3, [9, 10]): EventType.SORTING_QUALIFIED_TYPE3,
        }

        # 查找匹配的事件类型
        event_type = None
        for (s_type, s_channels), e_type in event_type_map.items():
            if sorting_type == s_type and set(channels) == set(s_channels):
                event_type = e_type
                break

        if event_type is None:
            self.logger.warning(f"未找到匹配的事件类型: {sorting_type}, 通道: {channels}")
            return

        event = SortingEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            sorting_type=sorting_type,
            channels=channels,
            count=count,
            weight=weight,
            grade=grade,
            source_data=source_data
        )

        await self.emit_event(event)

    async def emit_communication_status_event(self,
                                              device_name: str,
                                              new_status: CommunicationStatus,
                                              error_message: Optional[str] = None,
                                              connection_info: Optional[Dict[str, Any]] = None):
        """发送通讯状态变更事件"""
        old_status = self.current_communication_status.get(device_name)

        # 只有状态真正改变时才发送事件
        if old_status == new_status:
            return

        # 确定事件类型
        if device_name.upper() == 'PLC':
            event_type = EventType.PLC_COMMUNICATION_STATUS
        elif device_name.upper() in ['SUGAR_DETECTOR', 'SUGAR']:
            event_type = EventType.SUGAR_COMMUNICATION_STATUS
        else:
            self.logger.warning(f"未知设备名称: {device_name}")
            return

        event = CommunicationStatusEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            device_name=device_name,
            old_status=old_status,
            new_status=new_status,
            error_message=error_message,
            connection_info=connection_info
        )

        # 更新缓存状态
        self.current_communication_status[device_name] = new_status

        await self.emit_event(event)

    async def emit_pulse_frequency_event(self,
                                         frequency: float,
                                         period: float,
                                         pulse_count: int,
                                         measurement_duration: float,
                                         pulse_timestamps: Optional[List[float]] = None):
        """发送光电脉冲频率事件"""
        event = PulseFrequencyEvent(
            event_type=EventType.PHOTOELECTRIC_PULSE_FREQUENCY,
            timestamp=datetime.now(),
            frequency=frequency,
            period=period,
            pulse_count=pulse_count,
            measurement_duration=measurement_duration,
            pulse_timestamps=pulse_timestamps
        )

        # 更新频率缓存
        self.pulse_frequency_buffer.append({
            'timestamp': datetime.now(),
            'frequency': frequency,
            'period': period
        })

        await self.emit_event(event)

    async def _process_events(self):
        """事件处理主循环"""
        self.logger.info("事件处理循环已启动")

        while self.running:
            try:
                # 等待事件
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )

                # 记录处理开始时间
                process_start_time = asyncio.get_event_loop().time()

                # 处理事件
                await self._handle_event(event)

                # 记录处理时间
                process_time = asyncio.get_event_loop().time() - process_start_time
                self.event_stats['processing_times'].append(process_time)
                self.event_stats['total_processed'] += 1

                # 标记任务完成
                self.event_queue.task_done()

            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                self.event_stats['failed_count'] += 1
                self.logger.error(f"事件处理异常: {e}")

        self.logger.info("事件处理循环已结束")

    async def _handle_event(self, event: BaseEvent):
        """处理单个事件"""
        try:
            # 记录到数据库
            await self._store_event(event)

            # 调用注册的处理器
            handlers = self.event_handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    self.logger.error(f"事件处理器执行失败: {e}")

        except Exception as e:
            self.logger.error(f"事件处理失败: {e}")
            raise

    async def _store_event(self, event: BaseEvent):
        """将事件存储到数据库"""
        try:
            if isinstance(event, SortingEvent):
                await self.data_store.save_sorting_event(event)
            elif isinstance(event, CommunicationStatusEvent):
                await self.data_store.save_communication_status_event(event)
            elif isinstance(event, PulseFrequencyEvent):
                await self.data_store.save_pulse_frequency_event(event)
            else:
                self.logger.warning(f"未知事件类型: {type(event)}")

        except Exception as e:
            self.logger.error(f"事件存储失败: {e}")
            raise

    # ========== 状态查询方法 ==========

    def get_current_communication_status(self, device_name: str) -> Optional[CommunicationStatus]:
        """获取当前通讯状态"""
        return self.current_communication_status.get(device_name)

    def get_recent_pulse_frequency(self, count: int = 10) -> List[Dict[str, Any]]:
        """获取最近的脉冲频率数据"""
        return list(self.pulse_frequency_buffer)[-count:]

    def get_event_statistics(self) -> Dict[str, Any]:
        """获取事件处理统计"""
        processing_times = list(self.event_stats['processing_times'])

        return {
            'total_processed': self.event_stats['total_processed'],
            'failed_count': self.event_stats['failed_count'],
            'queue_overflow_count': self.event_stats['queue_overflow_count'],
            'queue_size': self.event_queue.qsize(),
            'avg_processing_time': sum(processing_times) / len(processing_times) if processing_times else 0,
            'max_processing_time': max(processing_times) if processing_times else 0,
            'current_communication_status': dict(self.current_communication_status),
            'recent_pulse_frequency_count': len(self.pulse_frequency_buffer)
        }