# core/plc_communicator.py (重构版)

from pymodbus.client.sync import ModbusTcpClient
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from pymodbus.constants import Endian
import time
import threading
from typing import List, Dict, Optional, Any


# from config import PLC_IP, PLC_PORT  # 从配置文件中获取地址


class PLCCommunicator:
    """
    负责与PLC进行Modbus TCP通信。
    封装了所有底层读写操作。
    """

    def __init__(self, host='192.168.0.2', port=502):
        self.host = host
        self.port = port
        self.client = None
        self._lock = threading.Lock()

        # 字节顺序转换
        self.CONTROL_REGISTER = 0
        self.STATUS_REGISTER = 300

        # 控制位映射（已应用字节顺序修正）
        self.CONTROL_BITS = {
            'remote_control': self._convert_doc_bit_to_actual_bit(0),
            'remote_start': self._convert_doc_bit_to_actual_bit(1),
            'remote_stop': self._convert_doc_bit_to_actual_bit(2),
            'remote_reset': self._convert_doc_bit_to_actual_bit(3),
            'remote_clear': self._convert_doc_bit_to_actual_bit(4),
        }

        # 状态位映射（已应用字节顺序修正）
        self.STATUS_BITS = {
            'system_ready': self._convert_doc_bit_to_actual_bit(0),
            'system_running': self._convert_doc_bit_to_actual_bit(1),
            'system_stopped': self._convert_doc_bit_to_actual_bit(2),
            'system_alarm': self._convert_doc_bit_to_actual_bit(3),
            'photo_mapping': self._convert_doc_bit_to_actual_bit(4),
        }

        # 定义协议中的地址映射，与原 plc_ctrl.py 保持一致
        self.HOLDING_REGISTER_ADDRESSES = {
            # 备用控制字
            'spare_control_1': 1,  # 40002在pymodbus中的地址（40002-40001=1）
            'spare_control_2': 2,  # 40003在pymodbus中的地址（40003-40001=2）

            'current_tray': 3,  # 40004在pymodbus中的地址（40004-40001=3）

            # 实时重量 (4个通道, DInt，每个占用2个寄存器)
            'realtime_weight_ch1': 4,  # 40005在pymodbus中的地址（40005-40001=4）
            'realtime_weight_ch2': 6,  # 40007在pymodbus中的地址（40007-40001=6）
            'realtime_weight_ch3': 8,  # 40009在pymodbus中的地址（40009-40001=8）
            'realtime_weight_ch4': 10,  # 40011在pymodbus中的地址（40011-40001=10）

            # 通道称重数据起始地址
            'channel_a_start': 12,  # 40013在pymodbus中的地址（40013-40001=12）
            'channel_b_start': 42,  # 40043在pymodbus中的地址（40043-40001=42）
            'channel_c_start': 72,  # 40073在pymodbus中的地址（40073-40001=72）
            'channel_d_start': 102,  # 40103在pymodbus中的地址（40103-40001=102）

            # 出口框相关
            'outlet_box_weight_set': 132,  # 40133在pymodbus中的地址（40133-40001=132）
            'outlet_box_actual_weight': 156,  # 40157在pymodbus中的地址（40157-40001=156）
            'outlet_valve_interval': 181,  # 40182在pymodbus中的地址（40182-40001=181）
            'grader_frequency_set': 193,  # 40194在pymodbus中的地址（40194-40001=193）

            # 统计数据
            'total_weight': 195,  # 40196在pymodbus中的地址（40196-40001=195）
            'total_count': 197,  # 40198在pymodbus中的地址（40198-40001=197）
        }

        print(f"PLC通信模块已初始化，目标: {host}:{port}")

    def _convert_doc_bit_to_actual_bit(self, doc_bit: int) -> int:
        """
        将文档中的位号转换为实际的位号
        字节顺序映射：
        文档位0-7 → 实际位8-15 (低字节变高字节)
        文档位8-15 → 实际位0-7 (高字节变低字节)
        """
        if doc_bit <= 7:
            # 低字节(0-7) → 高字节(8-15)
            return doc_bit + 8
        else:
            # 高字节(8-15) → 低字节(0-7)
            return doc_bit - 8

    def _get_client(self) -> ModbusTcpClient:
        """获取Modbus客户端实例"""
        if self.client is None or not self.client.is_socket_open():
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
            self.client = ModbusTcpClient(self.host, port=self.port)
        return self.client

    def connect(self):
        """尝试连接到PLC。"""
        with self._lock:
            try:
                client = self._get_client()
                return client.connect()
            except Exception as e:
                print(f"连接到PLC失败: {e}")
                return False

    def close(self):
        """关闭与PLC的连接。"""
        with self._lock:
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None

    def is_connected(self) -> bool:
        """检查是否已连接到PLC"""
        with self._lock:
            return self.client is not None and self.client.is_socket_open()

    # --- 底层读写操作 ---

    def _read_holding_registers(self, register_address: int, count: int) -> Optional[List[int]]:
        """读取保持寄存器"""
        with self._lock:
            client = self._get_client()
            if not client.is_socket_open() and not client.connect():
                return None

            response = client.read_holding_registers(register_address, count)
            if response.isError():
                return None
            return response.registers

    def _read_register_bit(self, register_address: int, bit_position: int) -> Optional[bool]:
        """从寄存器中读取指定位的值"""
        with self._lock:
            client = self._get_client()
            if not client.is_socket_open() and not client.connect():
                return None

            result = client.read_holding_registers(register_address, 1)
            if result.isError():
                return None

            register_value = result.registers[0]
            bit_value = bool(register_value & (1 << bit_position))
            return bit_value

    def _write_register_bit(self, register_address: int, bit_position: int, bit_value: bool) -> bool:
        """向寄存器中写入指定位的值"""
        with self._lock:
            client = self._get_client()
            if not client.is_socket_open() and not client.connect():
                return False

            # 先读取当前寄存器值
            result = client.read_holding_registers(register_address, 1)
            if result.isError():
                return False

            register_value = result.registers[0]

            # 设置或清除指定位
            if bit_value:
                register_value |= (1 << bit_position)  # 设置位
            else:
                register_value &= ~(1 << bit_position)  # 清除位

            # 写回寄存器
            response = client.write_register(register_address, register_value)
            return not response.isError()

    def _pulse_register_bit(self, register_address: int, bit_position: int, duration: float = 0.1) -> bool:
        """发送一个脉冲信号 (True -> False) 到寄存器的指定位"""
        if self._write_register_bit(register_address, bit_position, True):
            time.sleep(duration)
            if self._write_register_bit(register_address, bit_position, False):
                return True
        return False

    def _write_word(self, register_address: int, value: int) -> bool:
        """写入一个Word (16位无符号整数) 值到Modbus保持寄存器"""
        with self._lock:
            client = self._get_client()
            if not client.is_socket_open() and not client.connect():
                return False

            response = client.write_register(register_address, value)
            return not response.isError()

    def _write_dint(self, register_address: int, value: int) -> bool:
        """写入一个DInt (32位有符号整数) 值到Modbus保持寄存器"""
        with self._lock:
            client = self._get_client()
            if not client.is_socket_open() and not client.connect():
                return False

            builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
            builder.add_32bit_int(value)
            registers = builder.build()

            response = client.write_registers(register_address, registers)
            return not response.isError()

    def _write_real(self, register_address: int, value: float) -> bool:
        """写入一个Real (32位浮点数) 值到Modbus保持寄存器"""
        with self._lock:
            client = self._get_client()
            if not client.is_socket_open() and not client.connect():
                return False

            builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
            builder.add_32bit_float(value)
            registers = builder.build()

            response = client.write_registers(register_address, registers)
            return not response.isError()

    # --- 业务层接口 ---

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {}
        registers = self._read_holding_registers(self.STATUS_REGISTER, 1)

        if registers:
            register_value = registers[0]
            for status_name, bit_pos in self.STATUS_BITS.items():
                status[status_name] = bool(register_value & (1 << bit_pos))
        else:
            for status_name in self.STATUS_BITS.keys():
                status[status_name] = None

        # 读取当前托盘号
        tray_registers = self._read_holding_registers(self.HOLDING_REGISTER_ADDRESSES['current_tray'], 1)
        current_tray = tray_registers[0] if tray_registers else None

        return {
            'system_status': status,
            'current_tray': current_tray,
            'timestamp': time.time()
        }

    def get_realtime_weights(self) -> Dict[str, Any]:
        """获取四个通道的实时重量"""
        weights = {}
        for i in range(1, 5):
            addr_key = f'realtime_weight_ch{i}'
            registers = self._read_holding_registers(self.HOLDING_REGISTER_ADDRESSES[addr_key], 2)
            if registers:
                decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
                weight = decoder.decode_32bit_int()
                weights[f'ch{i}'] = weight
            else:
                weights[f'ch{i}'] = None

        return {
            'realtime_weights': weights,
            'timestamp': time.time(),
            'unit': 'g'
        }

    def get_total_count(self) -> Optional[int]:
        """获取总计数值"""
        registers = self._read_holding_registers(self.HOLDING_REGISTER_ADDRESSES['total_count'], 2)
        if registers:
            decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Big)
            return decoder.decode_32bit_int()
        return None

    def get_channel_grades_data(self, channel: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定通道的所有10个分选数据

        Args:
            channel: 通道字母 'A', 'B', 'C', 'D'

        Returns:
            包含10个分选数据的列表，每个包含序号、重量、分选值和地址
        """
        channel = channel.upper()
        if channel not in ['A', 'B', 'C', 'D']:
            return None

        channel_start_key = f'channel_{channel.lower()}_start'
        start_address = self.HOLDING_REGISTER_ADDRESSES[channel_start_key]

        total_registers = 10 * 3  # 10组 × 3寄存器/组
        registers = self._read_holding_registers(start_address, total_registers)

        if not registers:
            return None

        channel_data = []
        for i in range(10):
            base_index = i * 3

            # 解析重量 (DInt, 2个寄存器)
            weight_registers = registers[base_index:base_index + 2]
            decoder = BinaryPayloadDecoder.fromRegisters(weight_registers, byteorder=Endian.Big, wordorder=Endian.Big)
            weight = decoder.decode_32bit_int()

            # 解析分选值 (Word, 1个寄存器)
            grade = registers[base_index + 2]

            channel_data.append({
                "sequence": i + 1,
                "weight": weight,
                "grade": grade,
                "address": start_address + base_index + 2  # 分选值的地址
            })

        return channel_data

    def _parse_grades_data(self, registers: List[int], grade_start_offset: int) -> List[Dict[str, Any]]:
        """
        将原始寄存器数据解析为分级数据列表。
        每个分级数据由3个寄存器组成:
        0: 序号 (UINT16)
        1: 分级 (UINT16)
        2: 重量 (FLOAT32, 两个寄存器)
        """
        if not registers or len(registers) < self.GRADE_REGISTERS_PER_CHANNEL:
            return []

        grades_data = []
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big)

        # 每3个寄存器代表一组分级数据
        for i in range(10):  # 假设有10组数据
            try:
                # 序列号
                sequence = decoder.decode_16bit_uint()
                # 分级
                grade = decoder.decode_16bit_uint()
                # 重量，占两个寄存器
                weight = decoder.decode_32bit_float()

                grades_data.append({
                    'sequence': sequence,
                    'grade': grade,
                    'weight': round(weight, 2)
                })
            except Exception as e:
                print(f"解析Modbus数据时出错: {e}")
                break
        return grades_data

    # def get_all_channels_grades_data(self) -> Dict[str, List[Dict[str, Any]]]:
    #     """获取所有4个通道的分选数据"""
    #     all_data = {}
    #     for channel in ['A', 'B', 'C', 'D']:
    #         all_data[f'channel_{channel}'] = self.get_channel_grades_data(channel)
    #     return all_data

    def get_all_channels_grades_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有4个通道的分选数据 - 优化版本，一次读取所有数据"""

        # 获取所有通道的起始地址
        channel_starts = {
            'A': self.HOLDING_REGISTER_ADDRESSES['channel_a_start'],  # 12
            'B': self.HOLDING_REGISTER_ADDRESSES['channel_b_start'],  # 42
            'C': self.HOLDING_REGISTER_ADDRESSES['channel_c_start'],  # 72
            'D': self.HOLDING_REGISTER_ADDRESSES['channel_d_start']  # 102
        }

        # 计算需要读取的总地址范围
        # 从最小地址开始，到最大地址结束
        min_address = min(channel_starts.values())  # 12
        max_address = max(channel_starts.values()) + 10 * 3  # 102 + 30 = 132
        total_registers = max_address - min_address  # 132 - 12 = 120个寄存器

        # 一次性读取所有寄存器
        all_registers = self._read_holding_registers(min_address, total_registers)

        if not all_registers:
            return {f'channel_{ch}': None for ch in ['A', 'B', 'C', 'D']}

        all_data = {}

        # 为每个通道解析数据
        for channel_letter, start_address in channel_starts.items():
            # 计算在all_registers中的偏移位置
            offset = start_address - min_address

            # 提取该通道的30个寄存器(10组 × 3寄存器/组)
            channel_registers = all_registers[offset:offset + 30]

            if len(channel_registers) < 30:
                # 如果数据不完整，该通道设为None
                all_data[f'channel_{channel_letter}'] = None
                continue

            # 解析该通道的10组数据
            channel_data = []
            for i in range(10):
                base_index = i * 3

                # 解析重量 (DInt, 2个寄存器)
                weight_registers = channel_registers[base_index:base_index + 2]
                decoder = BinaryPayloadDecoder.fromRegisters(
                    weight_registers,
                    byteorder=Endian.Big,
                    wordorder=Endian.Big
                )
                weight = decoder.decode_32bit_int()

                # 解析分选值 (Word, 1个寄存器)
                grade = channel_registers[base_index + 2]

                channel_data.append({
                    "sequence": i + 1,
                    "weight": weight,
                    "grade": grade,
                    "address": start_address + base_index + 2  # 分选值的地址
                })

            all_data[f'channel_{channel_letter}'] = channel_data

        return all_data

    def set_channel_grade(self, channel_letter: str, sequence: int, grade: int) -> bool:
        """
        根据通道、序号和分选值，向PLC写入分选结果。
        这是来自 plc_ctrl.py 中 `/config/channel/<...>grade` 路由的核心逻辑。

        Args:
            channel_letter: 通道字母 'A', 'B', 'C', 'D'
            sequence: 分选序号 1-10
            grade: 分选等级值

        Returns:
            写入是否成功
        """
        channel_letter = channel_letter.upper()
        if channel_letter not in ['A', 'B', 'C', 'D'] or sequence < 1 or sequence > 10:
            print(f"参数错误: 通道={channel_letter}, 序号={sequence}")
            return False

        # 获取通道起始地址
        channel_start_key = f'channel_{channel_letter.lower()}_start'
        # 确保地址存在
        if channel_start_key not in self.HOLDING_REGISTER_ADDRESSES:
            print(f"通道 {channel_letter} 的地址未定义")
            return False

        start_address = self.HOLDING_REGISTER_ADDRESSES[channel_start_key]

        # 计算分选地址 (每组3个寄存器：重量2个+分选1个)
        grade_addr = start_address + (sequence - 1) * 3 + 2

        # 写入分选值
        return self._write_word(grade_addr, grade)

    # --- 控制接口 ---

    def remote_start(self) -> bool:
        """远程启动"""
        return self._pulse_register_bit(self.CONTROL_REGISTER, self.CONTROL_BITS['remote_start'])

    def remote_stop(self) -> bool:
        """远程停止"""
        return self._pulse_register_bit(self.CONTROL_REGISTER, self.CONTROL_BITS['remote_stop'])

    def remote_reset(self) -> bool:
        """远程报警复位"""
        return self._pulse_register_bit(self.CONTROL_REGISTER, self.CONTROL_BITS['remote_reset'])

    def remote_clear(self) -> bool:
        """远程数据清零"""
        return self._pulse_register_bit(self.CONTROL_REGISTER, self.CONTROL_BITS['remote_clear'])

    def set_remote_control(self, enable: bool) -> bool:
        """启用/禁用远程控制"""
        return self._write_register_bit(self.CONTROL_REGISTER, self.CONTROL_BITS['remote_control'], enable)

    # --- 健康检查 ---

    def health_check(self) -> Dict[str, Any]:
        """健康检查接口"""
        plc_connected = False

        try:
            if self.connect():
                # 尝试读取系统状态
                status = self._read_register_bit(self.STATUS_REGISTER, self.STATUS_BITS['system_ready'])
                plc_connected = status is not None
        except:
            pass

        return {
            "status": "healthy" if plc_connected else "unhealthy",
            "plc_connected": plc_connected,
            "timestamp": time.time(),
            "plc_ip": self.host,
            "plc_port": self.port
        }


# 使用示例
if __name__ == '__main__':
    # 创建PLC通信器
    plc = PLCCommunicator('192.168.0.2', 502)

    # 测试连接
    if plc.connect():
        print("✅ PLC连接成功")

        # 测试读取系统状态
        status = plc.get_system_status()
        print(f"系统状态: {status}")

        # 测试读取实时重量
        weights = plc.get_realtime_weights()
        print(f"实时重量: {weights}")

        # 测试读取通道A的分选数据
        channel_a_data = plc.get_channel_grades_data('A')
        if channel_a_data:
            print(f"通道A分选数据: {len(channel_a_data)}条")
            for item in channel_a_data[:3]:  # 只显示前3条
                print(f"  序号{item['sequence']}: 重量{item['weight']}g, 分选{item['grade']}")

        # 测试健康检查
        health = plc.health_check()
        print(f"健康状态: {health}")

        plc.close()
        print("✅ PLC连接已关闭")
    else:
        print("❌ PLC连接失败")