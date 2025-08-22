# detectors/weight_detector.py
import time
from typing import Optional

from .base_detector import BaseDetector
from core.plc_communicator import PLCCommunicator
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from services.weight.AsyncWeightDetectionService import AsyncWeightDetectionService


class WeightDetector(BaseDetector):
    """
    一个具体的重量检测单元。
    它负责通过Modbus协议从PLC读取重量数据。
    """

    def __init__(self, plc_communicator):
        super().__init__('WeightDetector')
        self.plc_communicator = plc_communicator
        self._results = {}  # 存储四个通道的重量

    def start_detection(self):
        """
        从PLC读取四个通道的实时重量数据。
        """
        print(f"[{self.name}] - 开始读取实时重量...")
        if not self.plc_communicator.connect():
            print(f"[{self.name}] - 无法连接到PLC，读取失败。")
            self._results = {}
            return

        for i, channel in enumerate(['ch1', 'ch2', 'ch3', 'ch4'], 1):
            addr_key = f'realtime_weight_ch{i}'
            registers = self.plc_communicator._read_holding_registers(
                HOLDING_REGISTER_ADDRESSES[addr_key], 2
            )
            if registers:
                decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                weight = decoder.decode_32bit_int()
                self._results[channel] = weight
            else:
                self._results[channel] = None

        self.plc_communicator.close()
        print(f"[{self.name}] - 实时重量读取完成: {self._results}")

    def get_result(self):
        """
        返回所有通道的重量结果。
        """
        return self._results


class OptimizedWeightDetector(BaseDetector):
    """
    优化的重量检测器 - 集成异步服务
    继承BaseDetector，保持架构统一性
    专注于实时性能
    """

    def __init__(self, plc_communicator, weight_service: AsyncWeightDetectionService):
        super().__init__('WeightDetector')  # 调用父类构造函数
        self.plc_communicator = plc_communicator
        self.weight_service = weight_service
        self._last_record = None
        self._results = {}  # 保持与原WeightDetector接口兼容

    def start_detection(self):
        """
        快速检测版本 - 最小延迟
        实现BaseDetector的抽象方法
        """
        start_time = time.perf_counter()

        # 快速读取重量（可以优化PLC通信为单次读取）
        weight = self._read_weight_fast()

        if weight is not None:
            # 使用异步服务快速处理
            self._last_record = self.weight_service.process_detection_fast(weight)

            # 保持与原接口的兼容性
            self._results = {
                'ch1': weight,
                'detection_record': self._last_record
            }
        else:
            self._last_record = None
            self._results = {}

        # 性能监控（开发阶段）
        detection_time = time.perf_counter() - start_time
        if detection_time > 0.005:  # 超过5ms警告
            print(f"[PERF] 检测耗时: {detection_time * 1000:.2f}ms")

    def _read_weight_fast(self) -> Optional[float]:
        """
        快速读取重量 - 可以进一步优化
        比如：
        1. 保持PLC连接不断开
        2. 使用更快的通信协议
        3. 批量读取多个通道
        """
        try:
            # 这里可以优化为持久连接
            if not self.plc_communicator.connect():
                return None

            # 只读取主要通道，减少通信次数
            from core.plc_communicator import HOLDING_REGISTER_ADDRESSES
            addr_key = 'realtime_weight_ch1'
            registers = self.plc_communicator._read_holding_registers(
                HOLDING_REGISTER_ADDRESSES[addr_key], 2
            )

            if registers:
                from pymodbus.payload import BinaryPayloadDecoder
                from pymodbus.constants import Endian
                decoder = BinaryPayloadDecoder.fromRegisters(
                    registers, byteorder=Endian.Big, wordorder=Endian.Big
                )
                weight = decoder.decode_32bit_int()
                return float(weight)

            return None

        except Exception as e:
            print(f"读取重量失败: {e}")
            return None
        finally:
            self.plc_communicator.close()

    def get_result(self):
        """
        返回检测结果 - 实现BaseDetector的抽象方法
        保持与原WeightDetector接口兼容
        """
        return self._results

    def get_detection_record(self):
        """
        获取详细的检测记录（新增方法）
        可用于获取服务层处理的完整记录
        """
        return self._last_record