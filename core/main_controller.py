# core/main_controller.py

from .detection_manager import DetectionManager
from .plc_communicator import PLCCommunicator
from core.plc_communicator import PLCCommunicator
from config import PLC_HOST, PLC_PORT, CHANNEL_MAP


class MainController:
    """
    主控制器，负责信号监测和任务协调。
    """

    def __init__(self, detection_manager, plc_communicator):
        self.detection_manager = detection_manager
        self.plc_communicator = plc_communicator
        self.last_signal_state = 0  # 假设初始信号为低电平

    def run_cycle(self, current_signal):
        """
        执行一个周期，检查信号边缘并执行相应操作。
        """
        print(f"\n[MainController] - 检查信号...")
        is_rising_edge = (current_signal == 1 and self.last_signal_state == 0)
        is_falling_edge = (current_signal == 0 and self.last_signal_state == 1)

        if is_rising_edge:
            print("[MainController] - 检测到上升沿，开始检测！")
            self.detection_manager.start_all_detections()

        if is_falling_edge:

            print("[MainController] - 检测到下降沿，检查结果并执行！")

            # 获取所有检测单元的结果

            all_results = self.detection_manager.get_all_results()

            # 假设你的业务逻辑是将“重量”和“颜色”结合起来确定分选值

            # 这里的逻辑需要根据你的实际情况来编写

            weight_results = all_results.get('WeightDetector', {})

            color_result = all_results.get('ColorDetector')

            # 假设我们只关心通道1的重量，并根据重量来决定分选等级

            weight = weight_results.get('ch1')

            if weight is not None:

                # 示例业务逻辑：根据重量决定分选等级（grade）和通道（channel）

                # 假设：

                # 1. 业务只处理一个通道，例如'A'

                # 2. 'sequence' 是固定的，例如为1

                # 3. 根据重量判断分选等级

                grade = self._calculate_grade_from_weight(weight)

                channel_letter = 'A'

                sequence = 1

                # 调用 PLCCommunicator 的方法来执行分选结果

                if self.plc_communicator.set_channel_grade(channel_letter, sequence, grade):

                    print(f"[MainController] - 成功执行结果：设置通道 {channel_letter} 的分选值为 {grade}")

                else:

                    print(f"[MainController] - 执行结果失败：设置通道 {channel_letter} 的分选值为 {grade}")

            else:

                print("[MainController] - 未获取到有效的重量数据，无法执行结果。")

        self.last_signal_state = current_signal

    def _calculate_grade_from_weight(self, weight):
        """
        业务逻辑：根据重量计算分选等级。
        这部分需要你根据你的实际需求来编写。
        """
        if weight > 100:
            return 1  # 示例：重量大于100，分选到等级1
        elif weight > 50:
            return 2
        else:
            return 3