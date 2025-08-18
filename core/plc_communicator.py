# core/plc_communicator.py (重构版)

from pymodbus.client.sync import ModbusTcpClient
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from pymodbus.constants import Endian
import time
#from config import PLC_IP, PLC_PORT  # 从配置文件中获取地址

# 定义协议中的地址映射，与 plc_ctrl.py 保持一致
HOLDING_REGISTER_ADDRESSES = {
    # ... 从 plc_ctrl.py 复制过来
    'realtime_weight_ch1': 10,
    # ... 其他地址
}


class PLCCommunicator:
    """
    负责与PLC进行Modbus TCP通信。
    封装了所有底层读写操作。
    """

    def __init__(self, host, port):
        self.client = ModbusTcpClient(host, port)
        print(f"PLC通信模块已初始化，目标: {host}:{port}")

    def connect(self):
        """尝试连接到PLC。"""
        try:
            return self.client.connect()
        except Exception as e:
            print(f"连接到PLC失败: {e}")
            return False

    def close(self):
        """关闭与PLC的连接。"""
        self.client.close()

    def _write_word(self, register_address, value):
        """写入一个Word (16位无符号整数) 值到Modbus保持寄存器"""
        response = self.client.write_register(register_address, value)
        return not response.isError()

    # 将 plc_ctrl.py 中的其他 _write_... 方法也移到这里
    # ... _write_dint, _write_real, _write_coil 等

    # 核心方法：执行结果
    def set_channel_grade(self, channel_letter, sequence, grade):
        """
        根据通道、序号和分选值，向PLC写入分选结果。
        这是来自 plc_ctrl.py 中 `/config/channel/<...>grade` 路由的核心逻辑。
        """
        # 获取通道起始地址
        channel_start_key = f'channel_{channel_letter.lower()}_start'
        # 确保地址存在
        if channel_start_key not in HOLDING_REGISTER_ADDRESSES:
            print(f"通道 {channel_letter} 的地址未定义")
            return False

        start_address = HOLDING_REGISTER_ADDRESSES[channel_start_key]

        # 计算分选地址
        grade_addr = start_address + (sequence - 1) * 6 + 4

        # 写入分选值
        return self._write_word(grade_addr, grade)

    def _read_holding_registers(self, register_address, count):
        """读取保持寄存器"""
        response = self.client.read_holding_registers(register_address, count)
        if response.isError():
            return None
        return response.registers

    # 你可以继续将其他读取方法也封装到这里
    # ... _read_coils 等