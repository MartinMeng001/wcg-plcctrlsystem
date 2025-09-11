# core/main_controller.py

from .detection_manager import DetectionManager
from .plc_communicator import PLCCommunicator
from core.plc_communicator import PLCCommunicator
from core.sorting_task_manager import SortingTaskManager
from config import PLC_HOST, PLC_PORT, CHANNEL_MAP

class MainController:
    """
    主控制器，负责信号监测和任务协调。
    """

    def __init__(self, detection_manager, plc_communicator, task_manager): # 增加 task_manager 参数
        self.detection_manager = detection_manager
        self.plc_communicator = plc_communicator
        self.task_manager = task_manager # 保存 SortingTaskManager 实例
        self.last_signal_state = 0  # 假设初始信号为低电平
        self.new_count = 0
        self.detection_manager.start_all_detections()

    def run_cycle(self, current_signal):
        """
        执行一个周期，检查信号边缘并执行相应操作。
        """
        # print(f"\n[MainController] - 检查信号...")
        is_rising_edge = (current_signal == 1 and self.last_signal_state == 0)
        is_falling_edge = (current_signal == 0 and self.last_signal_state == 1)

        if is_rising_edge:
            # print("[MainController] - 检测到上升沿，开始检测！")
            #self.detection_manager.start_all_detections()
            # 在这里增加计数值
            new_count = self.task_manager.increment_count()
            self.detection_manager.sync_counts(new_count)
            # self.task_manager.set_count(new_count)
            print(f"[MainController] - 计数器更新：新值为 {new_count}")

        # if is_falling_edge:
            # ... (这部分代码保持不变)
            # print("[MainController] - 检测到下降沿，检查结果并执行！")
            # all_results = self.detection_manager.get_all_results()
            # weight_results = all_results.get('WeightDetector', {})
            # color_result = all_results.get('ColorDetector')
            # weight = weight_results.get('ch1')
            # if weight is not None:
            #     grade = self._calculate_grade_from_weight(weight)
            #     channel_letter = 'A'
            #     sequence = 1
            #     if self.plc_communicator.set_channel_grade(channel_letter, sequence, grade):
            #         print(f"[MainController] - 成功执行结果：设置通道 {channel_letter} 的分选值为 {grade}")
            #     else:
            #         print(f"[MainController] - 执行结果失败：设置通道 {channel_letter} 的分选值为 {grade}")
            # else:
            #     print("[MainController] - 未获取到有效的重量数据，无法执行结果。")

        self.last_signal_state = current_signal
