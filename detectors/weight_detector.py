# detectors/weight_detector.py

from .base_detector import BaseDetector
from core.plc_communicator import PLCCommunicator, HOLDING_REGISTER_ADDRESSES
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian


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