# detectors/base_detector.py

from abc import ABC, abstractmethod

class BaseDetector(ABC):
    """
    所有检测单元的抽象基类。
    定义了每个检测单元必须实现的方法。
    """

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def start_detection(self):
        """
        开始执行具体的检测任务。
        此方法可以启动传感器读取、图像处理等操作。
        """
        pass

    @abstractmethod
    def start_detection_with_counter(self, counter):
        """
        使用配置信息开始执行具体的检测任务。
        此方法应传入一个 `counter` 字典或对象来配置检测过程。
        """
        pass

    @abstractmethod
    def get_result(self):
        """
        获取检测结果。
        此方法应返回一个清晰的、可被主控制器理解的结果。
        """
        pass