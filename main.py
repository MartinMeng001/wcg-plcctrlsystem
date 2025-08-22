# main.py (部分修改)

import time
from core.main_controller import MainController
from core.detection_manager import DetectionManager
from core.plc_communicator import PLCCommunicator
from core.sorting_task_manager import SortingTaskManager, Counter, WeightRange 
from detectors.color_detector import ColorDetector
# 新增: 导入你新的检测器
from detectors.pulse_detector import PulseDetector
from detectors.weight_detector import WeightDetector
from config import PLC_HOST, PLC_PORT
from api import start_api_server_thread


# 模拟一个简单的信号源
# 注意：现在我们的脉冲检测功能将由 PulseDetector 实例本身完成，
# 所以 main.py 不再需要模拟信号，而是从 PulseDetector 获取实时信号状态。
# 因此，我们移除 get_simulated_signal() 函数，直接调用 PulseDetector。

if __name__ == "__main__":
    # 1. 实例化各个模块
    detection_manager = DetectionManager()
    plc_communicator = PLCCommunicator(PLC_HOST, PLC_PORT)
    pulse_detector = PulseDetector()  # 实例化脉冲检测器

    # 新增: 实例化计数器和 SortingTaskManager
    task_counter = Counter()
    sorting_task_manager = SortingTaskManager(plc_communicator, task_counter)

    # 配置重量分拣
    weight_ranges = [
        WeightRange(901, 9999, 1),  # >900g -> 等级1
        WeightRange(801, 900, 2),  # 801-900g -> 等级2
        WeightRange(501, 800, 3),  # 501-800g -> 等级3
        # WeightRange(0, 500, 4),  # ≤500g -> 等级4
    ]
    sorting_task_manager.configure_weight_sorting(weight_ranges, True)
    # 2. 注册检测单元
    # 这里注册了你所有具体的检测单元实例
    detection_manager.register_detector(ColorDetector())
    detection_manager.register_detector(pulse_detector)  # 你的脉冲检测器
    # 新增: 注册重量检测器，将 plc_communicator 实例传递给它
    detection_manager.register_detector(WeightDetector(plc_communicator))
    # ... 注册其他检测器，例如： size_detector

    # 3. 实例化主控制器并传入依赖
    # 核心变更: 将 sorting_task_manager 实例作为参数传递给 MainController
    main_controller = MainController(detection_manager, plc_communicator, sorting_task_manager)

    # 启动API服务器（独立线程）
    api_thread = start_api_server_thread(port=5000)
    # 5. 启动 SortingTaskManager 任务
    sorting_task_manager.start()
    # 4. 运行主循环
    print("开始运行主循环...")
    try:
        while True:
            # 核心变更：不再模拟信号，而是直接调用 PulseDetector 来获取当前状态
            pulse_detector.start_detection()
            current_signal = pulse_detector.get_result()

            # 将获取到的信号状态传递给主控制器进行边缘检测
            if current_signal != -1:  # 确保读取成功
                main_controller.run_cycle(current_signal)

            time.sleep(0.01)  # 可以设置一个更短的循环间隔，以更实时地检测脉冲

    except KeyboardInterrupt:
        print("\n程序已终止。")
    finally:
        # 确保在程序结束时释放资源
        pulse_detector.dispose()
        plc_communicator.close()  # 在程序结束时关闭PLC连接
        # 新增: 停止 SortingTaskManager 任务
        sorting_task_manager.stop()
