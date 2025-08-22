# sorting_task_manager.py

import time
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class WeightRange:
    """重量范围配置"""
    min_weight: int
    max_weight: int
    grade: int

    def matches(self, weight: int) -> bool:
        """检查重量是否在范围内"""
        return self.min_weight <= weight <= self.max_weight

    def __str__(self):
        return f"{self.min_weight}-{self.max_weight}g->等级{self.grade}"


@dataclass
class CustomSortingTask:
    """自定义分拣任务"""
    target_count: int
    sort_channel: int
    target_channel: str
    created_time: datetime = None
    executed: bool = False  # 标记是否已处理（执行成功或失效）
    executed_at: datetime = None  # 处理时间
    success: bool = None  # 新增：是否成功执行（True=成功, False=失效, None=未处理）

    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()
        self.target_channel = self.target_channel.upper()

    def mark_executed(self, success: bool = True):
        """标记任务已处理"""
        self.executed = True
        self.success = success
        self.executed_at = datetime.now()

    def __str__(self):
        if not self.executed:
            return f"计数{self.target_count}->通道{self.target_channel}分拣{self.sort_channel}(待执行)"
        elif self.success:
            return f"计数{self.target_count}->通道{self.target_channel}分拣{self.sort_channel}(已成功)"
        else:
            return f"计数{self.target_count}->通道{self.target_channel}分拣{self.sort_channel}(已失效)"


class Counter:
    """线程安全的计数器"""

    def __init__(self, initial_value: int = 0):
        self._value = initial_value
        self._lock = threading.Lock()
        self._observers = []  # 观察者列表

    def get(self) -> int:
        """获取当前计数值"""
        with self._lock:
            return self._value

    def set(self, value: int) -> int:
        """设置计数值"""
        with self._lock:
            old_value = self._value
            self._value = value
            # 通知观察者
            self._notify_observers(old_value, value)
            return old_value

    def tick(self, increment: int = 1) -> int:
        """增加计数值"""
        with self._lock:
            old_value = self._value
            self._value += increment
            # 通知观察者
            self._notify_observers(old_value, self._value)
            return self._value

    def reset(self) -> int:
        """重置计数器"""
        return self.set(0)

    def add_observer(self, callback):
        """添加观察者回调函数"""
        with self._lock:
            if callback not in self._observers:
                self._observers.append(callback)

    def remove_observer(self, callback):
        """移除观察者回调函数"""
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def _notify_observers(self, old_value: int, new_value: int):
        """通知所有观察者"""
        for callback in self._observers:
            try:
                callback(old_value, new_value)
            except Exception as e:
                print(f"[{datetime.now()}] 计数器观察者回调出错: {e}")


class SortingTaskManager:
    """分拣任务管理器"""

    def __init__(self, plc_communicator, counter: Counter = None):
        """
        初始化分拣任务管理器

        Args:
            plc_communicator: PLC通信器实例
            counter: 计数器实例，如果为None则创建新的
        """
        self.plc = plc_communicator
        self.counter = counter if counter is not None else Counter()

        # 配置参数
        self.weight_ranges: List[WeightRange] = []  # 重量分拣配置
        self.custom_tasks: List[CustomSortingTask] = []  # 自定义分拣任务列表
        self.enable_weight_sorting = False  # 是否启用重量分拣
        self.enable_custom_sorting = False  # 是否启用自定义分拣

        # 运行状态
        self.running = False
        self.thread = None
        self._lock = threading.Lock()

        # 监控参数
        self.monitor_interval = 0.1  # 监控间隔（秒）
        self.log_interval = 100  # 每100次循环打印一次状态
        self.loop_count = 0

        # 统计信息
        self.stats = {
            'weight_sorted_count': 0,
            'custom_sorted_count': 0,
            'missed_tasks': 0,  # 新增：错过的任务数量
            'total_processed': 0,
            'start_time': None
        }

        # 注册计数器观察者
        self.counter.add_observer(self._on_count_changed)

        print(f"[{datetime.now()}] 分拣任务管理器已初始化")

    def _on_count_changed(self, old_value: int, new_value: int):
        """计数器变化时的回调（现在主要用于日志，实际处理在主循环）"""
        if self.enable_custom_sorting and new_value > old_value:
            # 简单日志，主要处理逻辑在主循环的 _process_custom_sorting 中
            if new_value % 10 == 0:  # 每10个计数打印一次
                print(f"[{datetime.now()}] 📊 计数更新: {old_value} -> {new_value}")

            # 注意：实际的自定义分拣处理现在在主循环中进行
            # 这里保留回调主要是为了兼容性和日志记录

    # --- 重量分拣配置 ---

    def configure_weight_sorting(self, weight_ranges: List[WeightRange], enable: bool = True):
        """配置重量分拣"""
        with self._lock:
            self.weight_ranges = weight_ranges.copy()
            self.enable_weight_sorting = enable

        ranges_str = ", ".join(str(r) for r in weight_ranges)
        print(f"[{datetime.now()}] 重量分拣配置更新: {len(weight_ranges)}个范围({ranges_str}), 启用={enable}")

    def add_weight_range(self, min_weight: int, max_weight: int, grade: int):
        """添加重量范围"""
        weight_range = WeightRange(min_weight, max_weight, grade)
        with self._lock:
            self.weight_ranges.append(weight_range)
            # 按最小重量排序，优先匹配小重量范围
            self.weight_ranges.sort(key=lambda x: x.min_weight)
        print(f"[{datetime.now()}] 添加重量范围: {weight_range}")

    def clear_weight_ranges(self):
        """清空所有重量范围"""
        with self._lock:
            count = len(self.weight_ranges)
            self.weight_ranges.clear()
        print(f"[{datetime.now()}] 已清空{count}个重量范围")

    def get_weight_ranges(self) -> List[WeightRange]:
        """获取所有重量范围"""
        with self._lock:
            return self.weight_ranges.copy()

    def set_weight_sorting_enabled(self, enabled: bool):
        """启用/禁用重量分拣"""
        with self._lock:
            self.enable_weight_sorting = enabled
        print(f"[{datetime.now()}] 重量分拣{'启用' if enabled else '禁用'}")

    # --- 自定义分拣任务管理 ---

    def add_custom_task_with_priority(self, target_count: int, sort_channel: int, target_channel: str,
                                      priority: str = "high"):
        """添加自定义分拣任务（支持优先级设置）"""
        task = CustomSortingTask(target_count, sort_channel, target_channel)
        with self._lock:
            self.custom_tasks.append(task)
            self.custom_tasks.sort(key=lambda x: x.target_count)  # 按计数值排序

        priority_desc = "高优先级" if priority == "high" else "普通优先级"
        print(f"[{datetime.now()}] 添加自定义分拣任务({priority_desc}): {task}")

        if priority == "high":
            print(f"[{datetime.now()}] ⚠️ 通道{target_channel}在计数{target_count}时将使用自定义分拣，暂停重量分拣")

    def add_custom_task(self, target_count: int, sort_channel: int, target_channel: str):
        """添加自定义分拣任务"""
        return self.add_custom_task_with_priority(target_count, sort_channel, target_channel, "high")

    def remove_custom_task(self, target_count: int, target_channel: str = None) -> bool:
        """移除自定义分拣任务"""
        with self._lock:
            for i, task in enumerate(self.custom_tasks):
                if (task.target_count == target_count and
                        (target_channel is None or task.target_channel == target_channel.upper())):
                    removed_task = self.custom_tasks.pop(i)
                    print(f"[{datetime.now()}] 移除自定义分拣任务: {removed_task}")
                    return True
        return False

    def clear_custom_tasks(self):
        """清空所有自定义分拣任务"""
        with self._lock:
            count = len(self.custom_tasks)
            self.custom_tasks.clear()
        print(f"[{datetime.now()}] 已清空{count}个自定义分拣任务")

    def get_custom_tasks(self, include_executed: bool = False) -> List[CustomSortingTask]:
        """获取所有自定义分拣任务"""
        with self._lock:
            if include_executed:
                return self.custom_tasks.copy()
            else:
                return [task for task in self.custom_tasks if not task.executed]

    def set_custom_sorting_enabled(self, enabled: bool):
        """启用/禁用自定义分拣"""
        with self._lock:
            self.enable_custom_sorting = enabled
        print(f"[{datetime.now()}] 自定义分拣{'启用' if enabled else '禁用'}")

    # --- 计数器管理 ---

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
        return self.counter.tick(increment)

    def reset_count(self) -> int:
        """重置计数器"""
        return self.counter.reset()

    # --- 分拣处理逻辑 ---

    def _has_pending_custom_task_for_channel(self, channel_letter: str, sequence: int) -> bool:
        """检查并执行指定通道和序号的待处理自定义分拣任务"""
        if not self.enable_custom_sorting or sequence != 1:  # 通常自定义分拣针对分选1
            return False

        current_count = self.get_current_count()
        task_executed = False

        with self._lock:
            tasks_to_remove = []
            for task in self.custom_tasks:
                if not task.executed and task.target_channel == channel_letter.upper():
                    if current_count == task.target_count:
                        # 计数值恰好等于目标值，执行分拣
                        if self.plc.set_channel_grade(task.target_channel, sequence, task.sort_channel):
                            print(
                                f"[{datetime.now()}] 🎯 自定义分拣执行: 计数{current_count}等于目标{task.target_count}, 通道{task.target_channel}分选1设置为{task.sort_channel}")
                            task.mark_executed(success=True)
                            tasks_to_remove.append(task)
                            self.stats['custom_sorted_count'] += 1
                            task_executed = True
                        else:
                            print(f"[{datetime.now()}] ❌ 自定义分拣失败: {task}")
                            task_executed = False
                        break  # 找到并处理了任务，跳出循环
                    elif current_count > task.target_count:
                        # 计数值超过目标值，任务失效
                        print(
                            f"[{datetime.now()}] ⚠️ 自定义分拣任务失效: 计数{current_count}超过目标{task.target_count}, 目标对象已错过")
                        task.mark_executed(success=False)
                        tasks_to_remove.append(task)
                        self.stats['missed_tasks'] += 1

            # 移除已处理的任务
            for task in tasks_to_remove:
                self.custom_tasks.remove(task)

        return task_executed

    def _process_weight_sorting(self, all_channels_data: Dict[str, List[Dict[str, Any]]]):
        """处理重量分拣"""
        if not self.enable_weight_sorting or not self.weight_ranges:
            return

        processed_count = 0
        for channel_name, channel_data in all_channels_data.items():
            if not channel_data:
                continue

            channel_letter = channel_name.split('_')[1]

            for item in channel_data:
                if item['grade'] == 100:  # 待处理
                    # 🔑 优先检查并执行自定义分拣
                    if self.enable_custom_sorting and self._has_pending_custom_task_for_channel(channel_letter,
                                                                                                item['sequence']):
                        continue  # 自定义分拣已处理，跳过重量分拣

                    # 执行重量分拣
                    weight = item['weight']

                    # 根据重量范围确定分拣等级
                    for weight_range in self.weight_ranges:
                        if weight_range.matches(weight):
                            if self.plc.set_channel_grade(channel_letter, item['sequence'], weight_range.grade):
                                print(
                                    f"[{datetime.now()}] ✅ 通道{channel_letter}分选{item['sequence']}: 重量{weight}g → 等级{weight_range.grade} (重量分拣)")
                                processed_count += 1
                            else:
                                print(f"[{datetime.now()}] ❌ 通道{channel_letter}分选{item['sequence']}: 设置失败")
                            break
                    else:
                        # 没有匹配的重量范围
                        self.plc.set_channel_grade(channel_letter, item['sequence'], 0)
                        print(
                            f"[{datetime.now()}] ⚠️ 通道{channel_letter}分选{item['sequence']}: 重量{weight}g 无匹配,默认0")

        if processed_count > 0:
            self.stats['weight_sorted_count'] += processed_count
            self.stats['total_processed'] += processed_count
            print(f"[{datetime.now()}] 🎯 本次按重量分选了 {processed_count} 个")

    def _monitor_loop(self):
        """监控循环"""
        print(f"[{datetime.now()}] 分拣任务管理器监控线程已启动")
        self.stats['start_time'] = datetime.now()

        while self.running:
            try:
                # 读取所有通道数据
                all_channels_data = self.plc.get_all_channels_grades_data()

                if all_channels_data:
                    # 处理重量分拣
                    self._process_weight_sorting(all_channels_data)

                    # 处理自定义分拣（从PLC同步计数或检查待处理任务）
                    # self._process_custom_sorting()

                    # 定期打印状态
                    if self.loop_count % self.log_interval == 0:
                        self._print_status(all_channels_data)
                else:
                    if self.loop_count % self.log_interval == 0:
                        print(f"[{datetime.now()}] ⚠️ 读取通道数据失败")

                self.loop_count += 1

            except Exception as e:
                if self.loop_count % (self.log_interval // 10) == 0:
                    print(f"[{datetime.now()}] 分拣监控出错: {str(e)}")

            time.sleep(self.monitor_interval)

        print(f"[{datetime.now()}] 分拣任务管理器监控线程已停止")

    def _print_status(self, all_channels_data: Dict[str, List[Dict[str, Any]]]):
        """打印系统状态"""
        pending_count = 0
        for channel_data in all_channels_data.values():
            if channel_data:
                pending_count += sum(1 for item in channel_data if item['grade'] == 100)

        pending_tasks = len([task for task in self.custom_tasks if not task.executed])
        successful_tasks = len([task for task in self.custom_tasks if task.executed and task.success])
        missed_tasks = len([task for task in self.custom_tasks if task.executed and not task.success])
        current_count = self.get_current_count()

        # 运行时间
        runtime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else None
        runtime_str = f"{int(runtime.total_seconds())}s" if runtime else "未知"

        print(f"[{datetime.now()}] 📊 状态报告:")
        print(f"  ├─ 待处理分选: {pending_count}")
        print(f"  ├─ 自定义任务: {pending_tasks}待执行 + {successful_tasks}成功 + {missed_tasks}失效")
        print(f"  ├─ 当前计数: {current_count}")
        print(f"  ├─ 重量分拣: {self.stats['weight_sorted_count']} (启用={self.enable_weight_sorting})")
        print(
            f"  ├─ 自定义分拣: {self.stats['custom_sorted_count']}成功 + {self.stats['missed_tasks']}失效 (启用={self.enable_custom_sorting})")
        print(f"  ├─ 总处理数: {self.stats['total_processed']}")
        print(f"  └─ 运行时间: {runtime_str}")

    # --- 生命周期管理 ---

    def start(self):
        """启动监控"""
        if self.running:
            print(f"[{datetime.now()}] 分拣任务管理器已在运行中")
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"[{datetime.now()}] 分拣任务管理器已启动")

    def stop(self):
        """停止监控"""
        if not self.running:
            print(f"[{datetime.now()}] 分拣任务管理器未在运行")
            return

        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        print(f"[{datetime.now()}] 分拣任务管理器已停止")

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        runtime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else None

        # 统计任务状态
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
            'runtime_seconds': int(runtime.total_seconds()) if runtime else 0,
            'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None
        }


# 使用示例
# if __name__ == '__main__':
#     # 模拟PLC通信器
#     class MockPLCCommunicator:
#         def get_all_channels_grades_data(self):
#             # 模拟返回一些测试数据
#             return {
#                 'channel_A': [
#                     {'sequence': 1, 'weight': 950, 'grade': 100, 'address': 14},
#                     {'sequence': 2, 'weight': 750, 'grade': 0, 'address': 17},
#                 ],
#                 'channel_B': [],
#                 'channel_C': [],
#                 'channel_D': []
#             }
#
#         def set_channel_grade(self, channel, sequence, grade):
#             print(f"模拟PLC: 设置通道{channel}分选{sequence}为等级{grade}")
#             return True
#
#
#     # 创建计数器
#     counter = Counter(0)
#
#     # 创建模拟PLC和任务管理器
#     mock_plc = MockPLCCommunicator()
#     task_manager = SortingTaskManager(mock_plc, counter)
#
#     # 配置重量分拣
#     weight_ranges = [
#         WeightRange(901, 9999, 1),  # >900g -> 等级1
#         WeightRange(801, 900, 2),  # 801-900g -> 等级2
#         WeightRange(501, 800, 3),  # 501-800g -> 等级3
#         WeightRange(0, 500, 4),  # ≤500g -> 等级4
#     ]
#     task_manager.configure_weight_sorting(weight_ranges, True)
#
#     # 添加自定义分拣任务
#     task_manager.add_custom_task(5, 5, 'A')  # 计数5时触发
#     task_manager.add_custom_task(10, 6, 'B')  # 计数10时触发
#     task_manager.set_custom_sorting_enabled(True)
#
#     # 启动监控
#     task_manager.start()
#
#     try:
#         print("分拣系统运行中，模拟计数增长...")
#
#         # 模拟计数增长
#         for i in range(15):
#             time.sleep(2)
#             counter.tick()  # 计数+1
#             print(f"当前计数: {counter.get()}")
#
#         # 打印最终统计
#         stats = task_manager.get_statistics()
#         print(f"\n最终统计: {stats}")
#
#     except KeyboardInterrupt:
#         print("\n正在停止系统...")
#     finally:
#         task_manager.stop()
#         print("系统已停止")
