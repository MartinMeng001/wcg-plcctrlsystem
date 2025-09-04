# core/detection_manager.py

class DetectionManager:
    """
    负责管理和协调所有检测单元。
    """

    def __init__(self):
        self.detectors = []

    def register_detector(self, detector):
        """
        注册一个检测单元。
        """
        if hasattr(detector, 'start_detection') and hasattr(detector, 'get_result'):
            self.detectors.append(detector)
            print(f"注册检测器: {detector.name}")
        else:
            print(f"警告: {detector} 不是一个有效的检测器，未注册。")

    def start_all_detections(self):
        """
        通知所有已注册的检测单元开始检测。
        """
        print("\n[DetectionManager] - 开始所有检测...")
        for detector in self.detectors:
            detector.start_detection()
        print("[DetectionManager] - 所有检测已启动。")

    def sync_counts(self, count):
        for detector in self.detectors:
            detector.start_detection_with_counter(count)

    def get_all_results(self):
        """
        从所有检测单元获取结果并组合。
        返回一个字典，键为检测器名称，值为检测结果。
        """
        print("\n[DetectionManager] - 获取所有检测结果...")
        results = {}
        for detector in self.detectors:
            results[detector.name] = detector.get_result()

        print(f"[DetectionManager] - 结果获取完成: {results}")
        return results