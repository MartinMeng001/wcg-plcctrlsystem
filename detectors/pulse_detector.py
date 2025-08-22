# detectors/pulse_detector.py

import time
from Automation.BDaq import *
from Automation.BDaq.InstantDiCtrl import InstantDiCtrl
from Automation.BDaq.BDaqApi import AdxEnumToString, BioFailed
from .base_detector import BaseDetector  # 继承我们的抽象基类


class PulseDetector(BaseDetector):
    """
    一个用于脉冲信号检测的数字输入检测单元。
    它负责检测特定端口的数字输入状态。DemoDevice,BID -- PCIE-1730,BID
    """

    def __init__(self, device_description="DemoDevice,BID#0", profile_path="../../profile/DemoDevice.xml", port=0):
        super().__init__('PulseDetector')
        self.device_description = device_description
        self.profile_path = profile_path
        self.port = port
        self.di_ctrl = None  # 存储 InstantDiCtrl 实例
        self._last_state = -1  # 上一个周期的端口状态
        self._current_state = -1  # 当前周期的端口状态

    def start_detection(self):
        """
        开始进行数字输入读取。
        这个方法在每次上升沿到来时被调用，用于获取当前信号状态。
        """
        if self.di_ctrl is None:
            # 首次调用时创建并初始化设备实例
            self.di_ctrl = InstantDiCtrl(self.device_description)
            self.di_ctrl.loadProfile = self.profile_path
            print(f"[{self.name}] - 设备 '{self.device_description}' 已初始化。")

        # 读取指定端口（你提到的端口0）的DI状态
        # 因为我们只需要bit0，所以可以只读取1个字节，然后通过位运算获取
        ret, data = self.di_ctrl.readAny(self.port, 1)  # 读取一个端口的数据

        if BioFailed(ret):
            enumStr = AdxEnumToString("ErrorCode", ret.value, 256)
            print(f"[{self.name}] - 读取DI失败，错误码: {ret.value} [{enumStr}]")
            self._current_state = -1  # 失败时标记为无效状态
        else:
            # 获取端口0的bit0状态
            bit0_state = (data[0] & 0x1)
            self._current_state = bit0_state
            # print(f"[{self.name}] - 端口 {self.port} 的 DI 状态: {self._current_state}")

    def get_result(self):
        """
        返回当前检测结果。
        在这里，这个方法不需要做太多，因为它只提供一个状态值给主控制器。
        主控制器会负责边缘检测。
        """
        return self._current_state

    def dispose(self):
        """
        在程序结束时调用，用于释放硬件资源。
        """
        if self.di_ctrl:
            self.di_ctrl.dispose()
            print(f"[{self.name}] - 硬件资源已释放。")
