# cached_sorting_task_manager.py

import threading
import time
from datetime import datetime
from typing import List, Dict, Optional, Any

# 导入原有的数据结构
from core.sorting_task_manager import WeightRange, CustomSortingTask, Counter
from services.events import get_event_service
from utils import get_data_manager


class CachedSortingTaskManager:
    """
    缓存优化版分拣任务管理器

    核心优化：
    1. 一次读取所有数据并缓存
    2. 在缓存数据上直接修改分选等级
    3. 一次性批量写入所有修改

    性能提升：网络通信从"1读+N写" → "1读+1写"
    """

    def __init__(self, plc_communicator, counter: Counter = None):
        """
        初始化缓存优化版分拣任务管理器

        Args:
            plc_communicator: PLC通信器实例（需要支持batch_write_from_cached_data方法）
            weight_service: 重量检测服务实例
            counter: 计数器实例，如果为None则创建新的
        """
        self.plc = plc_communicator
        self.counter = counter if counter is not None else Counter()
        self._count = 0

        # 配置参数（与原版本相同）
        self.weight_ranges: List[WeightRange] = []
        self.custom_tasks: List[CustomSortingTask] = []
        self.enable_weight_sorting = False
        self.enable_custom_sorting = False

        # 运行状态
        self.running = False
        self.thread = None
        self._lock = threading.Lock()

        # 缓存相关
        self.cached_channels_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self.cache_timestamp = None

        # 监控参数
        self.monitor_interval = 0.05
        self.log_interval = 100
        self.loop_count = 0

        # 统计信息（增强版）
        self.stats = {
            'weight_sorted_count': 0,
            'custom_sorted_count': 0,
            'missed_tasks': 0,
            'total_processed': 0,
            'cache_hits': 0,
            'batch_writes': 0,
            'batch_write_failures': 0,
            'start_time': None
        }

        # 注册计数器观察者
        self.counter.add_observer(self._on_count_changed)

        print(f"[{datetime.now()}] 缓存优化版分拣任务管理器已初始化")

    def set_count(self, count: int):
        self._count = count

    def _on_count_changed(self, old_value: int, new_value: int):
        """计数器变化时的回调"""
        if self.enable_custom_sorting and new_value > old_value:
            if new_value % 10 == 0:  # 每10个计数打印一次
                print(f"[{datetime.now()}] 计数更新: {old_value} -> {new_value}")

    # --- 配置方法（与原版本相同） ---

    def configure_weight_sorting(self, weight_ranges: List[WeightRange], enable: bool = True):
        """配置重量分拣"""
        with self._lock:
            self.weight_ranges = weight_ranges.copy()
            self.enable_weight_sorting = enable

        ranges_str = ", ".join(str(r) for r in weight_ranges)
        print(f"[{datetime.now()}] 重量分拣配置更新: {len(weight_ranges)}个范围({ranges_str}), 启用={enable}")

    def add_custom_task(self, target_count: int, sort_channel: int, target_channel: str):
        """添加自定义分拣任务"""
        task = CustomSortingTask(target_count, sort_channel, target_channel)
        with self._lock:
            self.custom_tasks.append(task)
            self.custom_tasks.sort(key=lambda x: x.target_count)

        print(f"[{datetime.now()}] 添加自定义分拣任务: {task}")

    def set_weight_sorting_enabled(self, enabled: bool):
        """启用/禁用重量分拣"""
        with self._lock:
            self.enable_weight_sorting = enabled
        print(f"[{datetime.now()}] 重量分拣{'启用' if enabled else '禁用'}")

    def set_custom_sorting_enabled(self, enabled: bool):
        """启用/禁用自定义分拣"""
        with self._lock:
            self.enable_custom_sorting = enabled
        print(f"[{datetime.now()}] 自定义分拣{'启用' if enabled else '禁用'}")

    # --- 计数器管理（与原版本相同） ---

    def get_counter(self) -> Counter:
        """获取计数器实例"""
        return self.counter

    def get_current_count(self) -> int:
        """获取当前计数值"""
        return self.counter.get()

    def set_count(self, value: int) -> int:
        """设置计数值"""
        return self.counter.set(value)

    def increment_count(self, increment: int = 1) -> int:
        """增加计数值"""
        self._count = self.counter.tick(increment)
        return self._count

    def reset_count(self) -> int:
        """重置计数器"""
        return self.counter.reset()

    # --- 缓存优化版核心处理逻辑 ---

    def _process_weight_sorting_cached(self, cached_channels_data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """
        基于缓存数据的重量分拣处理

        Args:
            cached_channels_data: 缓存的结构化通道数据

        Returns:
            bool: 是否有数据被修改
        """
        if not self.enable_weight_sorting or not self.weight_ranges or not cached_channels_data:
            return False

        data_modified = False
        processed_count = 0
        event_service = get_event_service()

        for channel_name, channel_data in cached_channels_data.items():
            if not channel_data:
                continue

            channel_letter = channel_name.split('_')[1].upper()

            for item in channel_data:
                if item['grade'] == 100:  # 待处理
                    weight = item['weight']
                    sequence = item['sequence']


                    # 优先检查自定义分拣
                    # if self.enable_custom_sorting and self._has_pending_custom_task_for_channel_cached(
                    #         channel_letter, sequence, cached_channels_data):
                    #     continue

                    # 使用重量检测服务进行分拣判断
                    # detection_record = self.weight_service.process_detection_fast(weight)

                    kick_ch = get_data_manager().set_value(channel_letter, 'weight', int(weight), self._count)
                    if kick_ch is not None:
                    #if detection_record.detection_success:
                        # 直接修改缓存数据中的分选等级
                        # item['grade'] = detection_record.kick_channel
                        item['grade'] = int(kick_ch)
                        data_modified = True
                        processed_count += 1

                        source_data={"channel": channel_letter, "sequence": sequence, "weight": weight}
                        event_service.emit_sorting_reject_event(
                            channel=kick_ch,
                            weight=weight,
                            grade=kick_ch,
                            source_data=source_data
                        )
                        if kick_ch in [1, 2, 3, 4]:
                            event_service.emit_sorting_reject_event(
                                channel=kick_ch,
                                weight=weight,
                                grade=kick_ch,
                                source_data=source_data
                            )
                        elif kick_ch in [5, 6]:
                            event_service.emit_sorting_qualified_event(
                                qualified_type=1,
                                weight=weight,
                                grade=kick_ch,
                                source_data=source_data
                            )
                        elif kick_ch in [7, 8]:
                            event_service.emit_sorting_qualified_event(
                                qualified_type=2,
                                weight=weight,
                                grade=kick_ch,
                                source_data=source_data
                            )
                        elif kick_ch in [9, 10]:
                            event_service.emit_sorting_qualified_event(
                                qualified_type=3,
                                weight=weight,
                                grade=kick_ch,
                                source_data=source_data
                            )
                        print(f"[{datetime.now()}] 缓存修改: 通道{channel_letter}序号{sequence}: "
                              f"重量{weight}g → 等级{kick_ch}")
                    else:
                        # 检测失败，设置为默认等级0
                        if item['grade'] != 0:
                            item['grade'] = 0
                            data_modified = True

        # if processed_count > 0:
        #     self.stats['weight_sorted_count'] += processed_count
        #     self.stats['total_processed'] += processed_count
        #     print(f"[{datetime.now()}] 本次重量分拣处理: {processed_count}个项目")

        return data_modified

    def _process_custom_sorting_cached(self, cached_channels_data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """
        基于缓存数据的自定义分拣处理

        Args:
            cached_channels_data: 缓存的结构化通道数据

        Returns:
            bool: 是否有数据被修改
        """
        if not self.enable_custom_sorting or not cached_channels_data:
            return False

        current_count = self.get_current_count()
        data_modified = False

        with self._lock:
            tasks_to_remove = []

            for task in self.custom_tasks:
                if not task.executed:
                    if current_count == task.target_count:
                        # 找到目标通道和序号
                        channel_key = f'channel_{task.target_channel}'
                        if channel_key in cached_channels_data and cached_channels_data[channel_key]:

                            # 查找目标序号（通常是1）
                            target_sequence = 1
                            target_item = None

                            for item in cached_channels_data[channel_key]:
                                if item['sequence'] == target_sequence:
                                    target_item = item
                                    break

                            if target_item and target_item['grade'] == 100:  # 确保是待处理状态
                                # 直接修改缓存数据
                                target_item['grade'] = task.sort_channel
                                data_modified = True

                                # 标记任务完成
                                task.mark_executed(success=True)
                                tasks_to_remove.append(task)
                                self.stats['custom_sorted_count'] += 1

                                print(f"[{datetime.now()}] 缓存修改: 自定义分拣执行 - 计数{current_count}, "
                                      f"通道{task.target_channel}序号{target_sequence}→等级{task.sort_channel}")

                    elif current_count > task.target_count:
                        # 计数值超过目标值，任务失效
                        task.mark_executed(success=False)
                        tasks_to_remove.append(task)
                        self.stats['missed_tasks'] += 1

                        print(f"[{datetime.now()}] 自定义分拣失效: 计数{current_count}超过目标{task.target_count}")

            # 移除已处理的任务
            for task in tasks_to_remove:
                self.custom_tasks.remove(task)

        return data_modified

    def _has_pending_custom_task_for_channel_cached(self, channel_letter: str, sequence: int,
                                                    cached_channels_data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """
        检查是否有待处理的自定义分拣任务（缓存版本）
        """
        if not self.enable_custom_sorting or sequence != 1:
            return False

        current_count = self.get_current_count()

        with self._lock:
            for task in self.custom_tasks:
                if (not task.executed and
                        task.target_channel == channel_letter.upper() and
                        current_count == task.target_count):
                    return True

        return False

    def _monitor_loop_cached(self):
        """
        缓存优化版监控循环
        """
        print(f"[{datetime.now()}] 缓存优化版分拣任务管理器监控线程已启动")
        self.stats['start_time'] = datetime.now()

        last_loop_time = time.time()

        while self.running:
            try:
                # 记录循环时间
                current_loop_time = time.time()
                time_diff_ms = (current_loop_time - last_loop_time) * 1000

                if time_diff_ms > 1000:  # 超过1000ms警告
                    print(f"[{datetime.now()}] 监控循环延迟警告: 间隔{time_diff_ms:.2f}ms")

                last_loop_time = current_loop_time

                # 一次性读取所有通道数据并缓存
                read_start_time = time.time()
                self.cached_channels_data = self.plc.get_all_channels_grades_data()
                self.cache_timestamp = datetime.now()
                # read_duration = (time.time() - read_start_time) * 1000

                # 打印数据获取的基本信息
                # if self.cached_channels_data:
                #     self._print_cache_info(read_duration)
                # else:
                #     print(f"[{datetime.now()}] 数据获取失败，耗时{read_duration:.2f}ms")

                if self.cached_channels_data:
                    self.stats['cache_hits'] += 1
                    data_modified = False

                    # 处理自定义分拣（优先级更高）
                    if self.enable_custom_sorting:
                        custom_modified = self._process_custom_sorting_cached(self.cached_channels_data)
                        data_modified = data_modified or custom_modified

                    # 处理重量分拣
                    if self.enable_weight_sorting:
                        weight_modified = self._process_weight_sorting_cached(self.cached_channels_data)
                        data_modified = data_modified or weight_modified

                    # 如果有数据修改，执行批量写入
                    if data_modified:
                        # write_start_time = time.time()
                        success = self.plc.batch_write_from_cached_data(self.cached_channels_data)
                        write_duration = (time.time() - read_start_time) * 1000

                        if success:
                            self.stats['batch_writes'] += 1
                            print(f"[{datetime.now()}] 批量写入成功，耗时{write_duration:.2f}ms")
                        else:
                            self.stats['batch_write_failures'] += 1
                            print(f"[{datetime.now()}] 批量写入失败，耗时{write_duration:.2f}ms")

                    # 定期打印状态
                    # if self.loop_count % self.log_interval == 0:
                    #     self._print_status_cached()

                else:
                    if self.loop_count % self.log_interval == 0:
                        print(f"[{datetime.now()}] 读取通道数据失败")

                self.loop_count += 1

            except Exception as e:
                if self.loop_count % (self.log_interval // 10) == 0:
                    print(f"[{datetime.now()}] 分拣监控出错: {str(e)}")

            time.sleep(self.monitor_interval)

        print(f"[{datetime.now()}] 缓存优化版分拣任务管理器监控线程已停止")

    def _print_status_cached(self):
        """基于缓存数据打印系统状态"""
        pending_count = 0
        total_items = 0

        if self.cached_channels_data:
            for channel_data in self.cached_channels_data.values():
                if channel_data:
                    total_items += len(channel_data)
                    pending_count += sum(1 for item in channel_data if item['grade'] == 100)

        # 统计任务情况
        pending_tasks = len([task for task in self.custom_tasks if not task.executed])
        successful_tasks = len([task for task in self.custom_tasks if task.executed and task.success])
        missed_tasks = len([task for task in self.custom_tasks if task.executed and not task.success])
        current_count = self.get_current_count()

        # 运行时间
        runtime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else None
        runtime_str = f"{int(runtime.total_seconds())}s" if runtime else "未知"

        print(f"[{datetime.now()}] 缓存优化版状态报告:")
        print(f"  ├─ 数据项总数: {total_items}")
        print(f"  ├─ 待处理分选: {pending_count}")
        print(f"  ├─ 自定义任务: {pending_tasks}待执行 + {successful_tasks}成功 + {missed_tasks}失效")
        print(f"  ├─ 当前计数: {current_count}")
        print(f"  ├─ 重量分拣: {self.stats['weight_sorted_count']} (启用={self.enable_weight_sorting})")
        print(f"  ├─ 自定义分拣: {self.stats['custom_sorted_count']}成功 + {self.stats['missed_tasks']}失效")
        print(f"  ├─ 缓存命中: {self.stats['cache_hits']} 次")
        print(f"  ├─ 批量写入: {self.stats['batch_writes']}成功 + {self.stats['batch_write_failures']}失败")
        print(f"  ├─ 总处理数: {self.stats['total_processed']}")
        print(f"  └─ 运行时间: {runtime_str}")

    def _print_cache_info(self, read_duration: float):
        """打印缓存数据的基本信息"""
        if not self.cached_channels_data:
            return

        total_items = 0
        pending_items = 0
        processed_items = 0
        channel_summary = []

        for channel_name, channel_data in self.cached_channels_data.items():
            if channel_data:
                channel_total = len(channel_data)
                channel_pending = sum(1 for item in channel_data if item['grade'] == 100)
                channel_processed = channel_total - channel_pending

                total_items += channel_total
                pending_items += channel_pending
                processed_items += channel_processed

                channel_letter = channel_name.split('_')[1].upper()
                channel_summary.append(f"{channel_letter}:{channel_pending}/{channel_total}")
            else:
                channel_letter = channel_name.split('_')[1].upper()
                channel_summary.append(f"{channel_letter}:无数据")

        # 每50次循环打印一次详细信息，其他时候打印简要信息
        if self.loop_count % 50 == 0:
            print(f"[{datetime.now()}] 数据获取详情:")
            print(f"  ├─ 耗时: {read_duration:.2f}ms")
            print(f"  ├─ 总项目: {total_items}个")
            print(f"  ├─ 待处理: {pending_items}个")
            print(f"  ├─ 已处理: {processed_items}个")
            print(f"  └─ 各通道: {' | '.join(channel_summary)}")
        else:
            # 简要信息：只在有待处理项目时打印
            if pending_items > 0:
                print(f"[{datetime.now()}] 数据获取: 耗时{read_duration:.2f}ms, "
                      f"待处理{pending_items}个 ({' '.join(channel_summary)})")

        # 如果读取时间过长，发出警告
        if read_duration > 500:  # 超过500ms
            print(f"[{datetime.now()}] 警告: 数据读取时间过长 {read_duration:.2f}ms")
        """基于缓存数据打印系统状态"""
        pending_count = 0
        total_items = 0

        if self.cached_channels_data:
            for channel_data in self.cached_channels_data.values():
                if channel_data:
                    total_items += len(channel_data)
                    pending_count += sum(1 for item in channel_data if item['grade'] == 100)

        # 统计任务情况
        pending_tasks = len([task for task in self.custom_tasks if not task.executed])
        successful_tasks = len([task for task in self.custom_tasks if task.executed and task.success])
        missed_tasks = len([task for task in self.custom_tasks if task.executed and not task.success])
        current_count = self.get_current_count()

        # 运行时间
        runtime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else None
        runtime_str = f"{int(runtime.total_seconds())}s" if runtime else "未知"

        print(f"[{datetime.now()}] 缓存优化版状态报告:")
        print(f"  ├─ 数据项总数: {total_items}")
        print(f"  ├─ 待处理分选: {pending_count}")
        print(f"  ├─ 自定义任务: {pending_tasks}待执行 + {successful_tasks}成功 + {missed_tasks}失效")
        print(f"  ├─ 当前计数: {current_count}")
        print(f"  ├─ 重量分拣: {self.stats['weight_sorted_count']} (启用={self.enable_weight_sorting})")
        print(f"  ├─ 自定义分拣: {self.stats['custom_sorted_count']}成功 + {self.stats['missed_tasks']}失效")
        print(f"  ├─ 缓存命中: {self.stats['cache_hits']} 次")
        print(f"  ├─ 批量写入: {self.stats['batch_writes']}成功 + {self.stats['batch_write_failures']}失败")
        print(f"  ├─ 总处理数: {self.stats['total_processed']}")
        print(f"  └─ 运行时间: {runtime_str}")
    # --- 生命周期管理 ---

    def start(self):
        """启动缓存优化版监控"""
        if self.running:
            print(f"[{datetime.now()}] 缓存优化版分拣任务管理器已在运行中")
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop_cached, daemon=True)
        self.thread.start()
        print(f"[{datetime.now()}] 缓存优化版分拣任务管理器已启动")

    def stop(self):
        """停止监控"""
        if not self.running:
            print(f"[{datetime.now()}] 缓存优化版分拣任务管理器未在运行")
            return

        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        print(f"[{datetime.now()}] 缓存优化版分拣任务管理器已停止")

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息（增强版）"""
        runtime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else None

        pending_tasks = len([task for task in self.custom_tasks if not task.executed])
        successful_tasks = len([task for task in self.custom_tasks if task.executed and task.success])
        missed_tasks = len([task for task in self.custom_tasks if task.executed and not task.success])

        return {
            'running': self.running,
            'current_count': self.get_current_count(),
            'weight_sorting_enabled': self.enable_weight_sorting,
            'custom_sorting_enabled': self.enable_custom_sorting,
            'weight_ranges_count': len(self.weight_ranges),
            'custom_tasks_pending': pending_tasks,
            'custom_tasks_successful': successful_tasks,
            'custom_tasks_missed': missed_tasks,
            'weight_sorted_count': self.stats['weight_sorted_count'],
            'custom_sorted_count': self.stats['custom_sorted_count'],
            'missed_tasks_count': self.stats.get('missed_tasks', 0),
            'total_processed': self.stats['total_processed'],
            'cache_hits': self.stats['cache_hits'],
            'batch_writes': self.stats['batch_writes'],
            'batch_write_failures': self.stats['batch_write_failures'],
            'runtime_seconds': int(runtime.total_seconds()) if runtime else 0,
            'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
            'cache_timestamp': self.cache_timestamp.isoformat() if self.cache_timestamp else None
        }

    # --- 额外的便利方法 ---

    def get_cached_data(self) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """获取当前缓存的数据"""
        return self.cached_channels_data

    def clear_cache(self):
        """清除缓存"""
        self.cached_channels_data = None
        self.cache_timestamp = None
        print(f"[{datetime.now()}] 缓存已清除")

    def force_cache_refresh(self) -> bool:
        """强制刷新缓存"""
        try:
            self.cached_channels_data = self.plc.get_all_channels_grades_data()
            self.cache_timestamp = datetime.now()
            return self.cached_channels_data is not None
        except Exception as e:
            print(f"[{datetime.now()}] 强制刷新缓存失败: {e}")
            return False


# 使用示例和对比
# if __name__ == '__main__':
#     print("缓存优化版SortingTaskManager使用示例:")
#     print("")
#     print("# 导入")
#     print("from cached_sorting_task_manager import CachedSortingTaskManager")
#     print("from sorting_task_manager import SortingTaskManager, WeightRange")
#     print("")
#     print("# 选择版本")
#     print("# 原版本（逐个写入）")
#     print("# task_manager = SortingTaskManager(plc, weight_service, counter)")
#     print("")
#     print("# 缓存优化版本（批量写入）")
#     print("task_manager = CachedSortingTaskManager(plc, weight_service, counter)")
#     print("")
#     print("# 其余使用方式完全相同")
#     print("task_manager.configure_weight_sorting(weight_ranges, True)")
#     print("task_manager.add_custom_task(5, 5, 'A')")
#     print("task_manager.start()