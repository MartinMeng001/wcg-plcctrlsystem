# detectors/color_detector.py

from .base_detector import BaseDetector


class ColorDetector(BaseDetector):
    """
    一个具体的颜色检测单元。
    """

    def __init__(self):
        super().__init__('ColorDetector')
        self._result = None  # 内部变量用于存储检测结果

    def start_detection(self):
        """
        模拟开始颜色检测。
        在实际项目中，这里会是传感器数据读取或图像处理逻辑。
        """
        print(f"[{self.name}] - 开始检测颜色...")
        # 实际代码：
        # raw_data = read_from_sensor()
        # self._result = process_color_data(raw_data)

        # 模拟结果
        import random
        self._result = random.choice(['red', 'green'])
        print(f"[{self.name}] - 检测完成，结果: {self._result}")

    def get_result(self):
        """
        返回检测到的颜色。
        """
        return self._result