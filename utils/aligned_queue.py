from collections import deque
from typing import Any, Tuple


class AlignedQueue:
    """
    一个先进先出队列，具有对齐取数功能。
    """

    def __init__(self, max_length: int):
        """
        初始化队列。

        Args:
            max_length (int): 队列的最大长度。
        """
        if not isinstance(max_length, int) or max_length <= 0:
            raise ValueError("队列最大长度必须是大于0的整数。")

        self._queue = deque(maxlen=max_length)

    def put(self, data: Any, position: int):
        """
        将数据放入队列。

        Args:
            data (Any): 要放入队列的数据。
            position (int): 数据的位置。
        """
        self._queue.append((data, position))

    def get_aligned(self, alignment_position: int) -> Tuple[Any, int] | None:
        """
        按照对齐规则从队列中取出一个元素。

        Args:
            alignment_position (int): 用于对齐的位置。

        Returns:
            Tuple[Any, int] | None: 如果成功对齐并取出，返回 (数据, 位置)；如果队列为空或发生错误，返回 None。
        """
        # 如果队列为空，直接返回 None
        if not self._queue:
            return None

        while self._queue:
            # 查看队首元素，但先不取出
            data, current_position = self._queue[0]

            if alignment_position == current_position:
                # 对齐规则1：如果传入位置与当前位置相等，则为已对齐，取出当前数
                return self._queue.popleft()
            elif alignment_position < current_position:
                # 对齐规则2：如果传入位置比当前位置小，为错误情况，中断取数
                print(f"取数错误：传入位置 {alignment_position} 小于当前位置 {current_position}。")
                return None
            else:  # alignment_position > current_position
                # 对齐规则3：如果传入位置比当前位置大，继续取下一个数
                print(f"对齐位置 {alignment_position} 大于当前位置 {current_position}，继续取下一个数。")
                self._queue.popleft()

        # 遍历完队列后没有找到对齐的元素
        return None

    def size(self) -> int:
        """返回队列当前的大小。"""
        return len(self._queue)

    def is_empty(self) -> bool:
        """检查队列是否为空。"""
        return not self._queue


# --- 示例用法 ---
print("--- 创建并使用队列 ---")
# 创建一个最大长度为5的队列
my_queue = AlignedQueue(max_length=5)

# 放入一些数据
print("向队列中放入数据...")
my_queue.put("数据A", 100)
my_queue.put("数据B", 101)
my_queue.put("数据C", 103)
my_queue.put("数据D", 104)
print(f"当前队列大小：{my_queue.size()}")
print("-" * 20)

# 示例1: 成功对齐取数
print("--- 示例1: 成功对齐取数（对齐位置 101）---")
retrieved_item = my_queue.get_aligned(101)
if retrieved_item:
    data, pos = retrieved_item
    print(f"成功取出元素：数据='{data}', 位置={pos}")
print(f"队列剩余大小：{my_queue.size()}")
print("-" * 20)

# 示例2: 传入位置小于当前位置，取数失败
print("--- 示例2: 传入位置小于当前位置，取数失败（对齐位置 100）---")
retrieved_item = my_queue.get_aligned(100)
if retrieved_item is None:
    print("取数操作因错误而中断。")
print(f"队列剩余大小：{my_queue.size()}")
print("-" * 20)

# 示例3: 跳过元素后对齐取数
print("--- 示例3: 跳过元素后对齐取数（对齐位置 104）---")
retrieved_item = my_queue.get_aligned(104)
if retrieved_item:
    data, pos = retrieved_item
    print(f"成功取出元素：数据='{data}', 位置={pos}")
print(f"队列剩余大小：{my_queue.size()}")
print("-" * 20)

# 示例4: 队列中没有对齐的元素
print("--- 示例4: 队列中没有对齐的元素（对齐位置 109）---")
retrieved_item = my_queue.get_aligned(109)
if retrieved_item is None:
    print("队列中没有找到与给定位置对齐的元素。")