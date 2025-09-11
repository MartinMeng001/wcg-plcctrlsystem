# detectors/sugar_detector.py

import time
import threading
import logging
from typing import Optional, Dict, Any
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from .base_detector import BaseDetector
from utils import get_data_manager

class SugarDetector(BaseDetector):
    """
    糖度检测器 - 基于内检仪通讯协议
    修改版：采用第一份代码的成功连接模式

    根据协议文档实现：
    - Modbus TCP通讯
    - 地址102: 检测控制位
    - 地址103: 参比控制位
    - 地址109: 异常位
    - 地址110: 流水号
    - 地址111-129: 检测结果位 (111对应糖度，112对应酸度)
    """

    # 协议地址定义
    DETECTION_CONTROL_REG = 102  # 检测控制位
    REFERENCE_CONTROL_REG = 103  # 参比控制位
    EXCEPTION_REG = 109  # 异常位
    SERIAL_NUMBER_REG = 110  # 流水号
    SUGAR_RESULT_REG = 111  # 糖度结果
    ACID_RESULT_REG = 112  # 酸度结果

    # 状态定义
    STATUS_COLLECTING = 1  # 采集中
    STATUS_SUCCESS = 2  # 采集成功
    STATUS_FAILED = 3  # 采集失败

    def __init__(self, host='192.168.0.20', port=502, modbus_id=1, polling_interval=0.05, channel_name=''):
        super().__init__('SugarDetector')
        self.host = host
        self.port = port
        self.modbus_id = modbus_id
        self._counter = 0
        self.channelName = channel_name
        self.polling_interval = max(0.05, polling_interval)  # 最小50ms，符合协议要求

        # 线程控制
        self._detection_thread = None
        self._stop_event = threading.Event()
        self._thread_lock = threading.Lock()

        # 数据缓存
        self._cached_results = {
            'sugar_content': None,  # 糖度值
            'acid_content': None,  # 酸度值
            'serial_number': None,  # 流水号
            'status': 'inactive',  # 状态: inactive, collecting, success, failed, error
            'last_update': None,  # 最后更新时间
            'exception_code': None  # 异常码
        }

        # 记录上次的流水号，用于判断新结果
        self._last_serial = None
        self._reference_completed = False  # 参比是否已完成

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # 清空现有处理器以避免重复
        self.logger.handlers = []
        # 添加控制台处理器
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def start_detection_with_counter(self, counter):
        self._counter = counter

    def start_detection(self):
        """
        开始检测 - 只运行一次，启动后台线程持续检测
        """
        with self._thread_lock:
            if self._detection_thread is not None and self._detection_thread.is_alive():
                self.logger.info(f"[{self.name}] - 检测线程已在运行")
                return

            self.logger.info(f"[{self.name}] - 启动糖度检测线程...")
            self._stop_event.clear()
            self._reference_completed = False
            self._last_serial = None

            self._detection_thread = threading.Thread(
                target=self._detection_loop,
                name=f"{self.name}Thread",
                daemon=True
            )
            self._detection_thread.start()

    def stop_detection(self):
        """
        停止检测线程
        """
        with self._thread_lock:
            if self._detection_thread is None:
                return

            self.logger.info(f"[{self.name}] - 停止糖度检测线程...")
            self._stop_event.set()

            # 等待线程结束
            if self._detection_thread.is_alive():
                self._detection_thread.join(timeout=2.0)

            self._detection_thread = None

    def _detection_loop(self):
        """
        检测主循环 - 在独立线程中运行
        采用第一份代码的成功模式：每次操作都新建连接
        """
        self.logger.info(f"[{self.name}] - 检测线程开始运行")

        # 首先测试连接
        if not self._test_connection():
            self.logger.error(f"[{self.name}] - 初始连接测试失败")
            self._update_cached_results(status='error')
            return

        # 执行参比采集（如果需要）
        if not self._reference_completed:
            if not self._perform_reference_collection():
                self.logger.error(f"[{self.name}] - 参比采集失败，但继续运行检测")
                # 不返回，继续尝试检测
            else:
                self._reference_completed = True

        # 启动检测过程（可选，某些设备可能自动检测）
        self._start_detection_process()

        # 主循环：持续轮询检测结果
        self.logger.info(f"[{self.name}] - 开始轮询检测结果，间隔{self.polling_interval * 1000}ms")

        while not self._stop_event.is_set():
            try:
                self._poll_detection_results()
                time.sleep(self.polling_interval)

            except Exception as e:
                self.logger.error(f"[{self.name}] - 检测循环异常: {e}")
                self._update_cached_results(status='error')
                time.sleep(1.0)  # 异常时延长等待时间

        self.logger.info(f"[{self.name}] - 检测线程结束")

    def _get_modbus_client(self):
        """
        获取一个新的Modbus客户端实例 - 采用第一份代码的模式
        """
        return ModbusTcpClient(self.host, port=self.port)

    def _test_connection(self) -> bool:
        """
        测试连接到检测仪 - 采用第一份代码的连接测试方式
        """
        client = self._get_modbus_client()
        try:
            if client.connect():
                self.logger.info(f"[{self.name}] - 成功连接到内部品质检测仪: {self.host}:{self.port}")
                return True
            else:
                self.logger.error(f"[{self.name}] - 连接失败: {self.host}:{self.port}")
                return False
        except Exception as e:
            self.logger.error(f"[{self.name}] - 连接异常: {e}")
            return False
        finally:
            client.close()

    def _read_register(self, client, address: int) -> Optional[int]:
        """
        读取单个寄存器 - 直接使用协议地址，不进行偏移转换
        """
        try:
            result = client.read_holding_registers(address, 1, unit=self.modbus_id)
            if result.isError():
                self.logger.debug(f"[{self.name}] - 读取地址{address}失败: {result}")
                return None
            return result.registers[0]
        except Exception as e:
            self.logger.debug(f"[{self.name}] - 读取地址{address}异常: {e}")
            return None

    def _convert_register_value(self, raw_value: int) -> float:
        """
        转换寄存器值为实际测量值
        处理16位有符号整数（最高位为符号位）然后除以100
        """
        if raw_value is None:
            return None

        # 将16位无符号整数转换为有符号整数
        if raw_value > 32767:  # 如果大于2^15-1，则为负数
            signed_value = raw_value - 65536  # 转换为负数 (raw_value - 2^16)
        else:
            signed_value = raw_value

        # 除以100得到实际值
        actual_value = signed_value / 100.0

        return actual_value

    def _write_register(self, client, address: int, value: int) -> bool:
        """
        写入单个寄存器 - 直接使用协议地址，不进行偏移转换
        """
        try:
            response = client.write_register(address, value, unit=self.modbus_id)
            if response.isError():
                self.logger.error(f"[{self.name}] - 写入地址{address}失败: {response}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"[{self.name}] - 写入地址{address}异常: {e}")
            return False

    def _perform_reference_collection(self) -> bool:
        """
        执行参比采集流程 - 采用第一份代码的连接模式
        """
        self.logger.info(f"[{self.name}] - 开始参比采集...")

        client = self._get_modbus_client()
        try:
            if not client.connect():
                self.logger.error(f"[{self.name}] - 参比采集连接失败")
                return False

            # 启动参比采集
            if not self._write_register(client, self.REFERENCE_CONTROL_REG, 1):
                self.logger.error(f"[{self.name}] - 启动参比采集失败")
                return False

        except Exception as e:
            self.logger.error(f"[{self.name}] - 参比采集启动异常: {e}")
            return False
        finally:
            client.close()

        # 轮询参比状态直到完成
        self.logger.info(f"[{self.name}] - 等待参比采集完成...")
        timeout = 30  # 30秒超时
        start_time = time.time()

        while (time.time() - start_time) < timeout and not self._stop_event.is_set():
            client = self._get_modbus_client()
            try:
                if not client.connect():
                    time.sleep(0.5)
                    continue

                status = self._read_register(client, self.REFERENCE_CONTROL_REG)
                if status is None:
                    time.sleep(0.5)
                    continue

                if status == self.STATUS_SUCCESS:
                    self.logger.info(f"[{self.name}] - 参比采集成功")
                    return True
                elif status == self.STATUS_FAILED:
                    self.logger.error(f"[{self.name}] - 参比采集失败")
                    return False
                elif status == self.STATUS_COLLECTING:
                    self.logger.debug(f"[{self.name}] - 参比采集中...")
                else:
                    self.logger.debug(f"[{self.name}] - 参比状态: {status}")

            except Exception as e:
                self.logger.debug(f"[{self.name}] - 参比状态检查异常: {e}")
            finally:
                client.close()

            time.sleep(0.5)

        self.logger.warning(f"[{self.name}] - 参比采集超时或被中断")
        return False

    def _start_detection_process(self) -> bool:
        """
        启动检测过程 - 可选步骤，某些设备可能自动检测
        """
        self.logger.info(f"[{self.name}] - 尝试启动检测过程...")

        client = self._get_modbus_client()
        try:
            if not client.connect():
                self.logger.warning(f"[{self.name}] - 启动检测连接失败，设备可能自动检测")
                return False

            # 写入检测控制位：1开始检测
            if not self._write_register(client, self.DETECTION_CONTROL_REG, 1):
                self.logger.warning(f"[{self.name}] - 启动检测失败，设备可能自动检测")
                return False

            self.logger.info(f"[{self.name}] - 检测过程已启动")
            return True

        except Exception as e:
            self.logger.warning(f"[{self.name}] - 启动检测异常: {e}，设备可能自动检测")
            return False
        finally:
            client.close()

    def _poll_detection_results(self):
        """
        轮询检测结果 - 采用第一份代码的成功模式
        """
        client = self._get_modbus_client()
        try:
            if not client.connect():
                self._update_cached_results(status='error')
                return

            # 检查异常
            exception_code = self._read_register(client, self.EXCEPTION_REG)
            if exception_code and exception_code != 0:
                self.logger.warning(f"[{self.name}] - 检测到异常，异常码: {exception_code}")

            # 读取检测控制位状态
            detection_status = self._read_register(client, self.DETECTION_CONTROL_REG)

            # 读取流水号
            serial_number = self._read_register(client, self.SERIAL_NUMBER_REG)

            # 检查是否有新的检测结果（通过流水号判断）
            if serial_number is not None and serial_number != self._last_serial:
                self.logger.debug(f"[{self.name}] - 检测到新的流水号: {serial_number} (上次: {self._last_serial})")

                # 尝试读取检测结果
                sugar_raw = self._read_register(client, self.SUGAR_RESULT_REG)
                acid_raw = self._read_register(client, self.ACID_RESULT_REG)

                if sugar_raw is not None and acid_raw is not None:
                    # 转换为实际值 (处理符号位然后除以100)
                    sugar_content = self._convert_register_value(sugar_raw)
                    acid_content = self._convert_register_value(acid_raw)

                    get_data_manager().set_value(self.channelName, 'water', sugar_content, self._counter)

                    self.logger.info(
                        f"[{self.name}] - 获得新检测结果: 糖度={sugar_content}, 酸度={acid_content}, 流水号={serial_number}")

                    self._update_cached_results(
                        sugar_content=sugar_content,
                        acid_content=acid_content,
                        serial_number=serial_number,
                        status='success',
                        exception_code=exception_code
                    )

                    self._last_serial = serial_number
                    return

            # 根据检测状态更新缓存
            if detection_status == self.STATUS_COLLECTING:
                self._update_cached_results(
                    serial_number=serial_number,
                    status='collecting',
                    exception_code=exception_code
                )
            elif detection_status == self.STATUS_FAILED:
                self._update_cached_results(
                    serial_number=serial_number,
                    status='failed',
                    exception_code=exception_code
                )
            elif detection_status == self.STATUS_SUCCESS or detection_status == 0:
                # 即使状态是成功，但如果流水号没变化，可能还是旧结果
                # 尝试读取当前结果
                sugar_raw = self._read_register(client, self.SUGAR_RESULT_REG)
                acid_raw = self._read_register(client, self.ACID_RESULT_REG)

                if sugar_raw is not None and acid_raw is not None:
                    sugar_content = self._convert_register_value(sugar_raw)
                    acid_content = self._convert_register_value(acid_raw)

                    # 即使流水号相同，也更新结果（但不打印日志）
                    self._update_cached_results(
                        sugar_content=sugar_content,
                        acid_content=acid_content,
                        serial_number=serial_number,
                        status='success',
                        exception_code=exception_code
                    )

        except Exception as e:
            self.logger.error(f"[{self.name}] - 轮询结果异常: {e}")
            self._update_cached_results(status='error')
        finally:
            client.close()

    def _update_cached_results(self, **kwargs):
        """
        更新缓存结果
        """
        with self._thread_lock:
            for key, value in kwargs.items():
                if key in self._cached_results:
                    self._cached_results[key] = value

            self._cached_results['last_update'] = time.time()

    # ========== 保留所有原有接口 ==========

    def get_result(self) -> Dict[str, Any]:
        """
        获取检测结果 - 实现BaseDetector的抽象方法
        """
        with self._thread_lock:
            return self._cached_results.copy()

    def get_sugar_content(self) -> Optional[float]:
        """
        获取糖度值
        """
        with self._thread_lock:
            return self._cached_results.get('sugar_content')

    def get_acid_content(self) -> Optional[float]:
        """
        获取酸度值
        """
        with self._thread_lock:
            return self._cached_results.get('acid_content')

    def get_status(self) -> str:
        """
        获取检测状态
        """
        with self._thread_lock:
            return self._cached_results.get('status', 'inactive')

    def is_detection_active(self) -> bool:
        """
        检查检测是否活跃
        """
        with self._thread_lock:
            return (self._detection_thread is not None and
                    self._detection_thread.is_alive() and
                    not self._stop_event.is_set())

    def dispose(self):
        """
        释放资源
        """
        self.logger.info(f"[{self.name}] - 释放资源...")
        self.stop_detection()


# 使用示例（保持与原代码相同的接口）
# if __name__ == "__main__":
#     # 配置日志
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#     )
#
#     # 创建糖度检测器
#     sugar_detector = SugarDetector(
#         host='192.168.0.20',  # 修改为正确的内检仪IP地址
#         port=502,  # Modbus TCP端口
#         modbus_id=1,  # 设备ID
#         polling_interval=0.05  # 50ms轮询间隔，符合协议要求
#     )
#
#     try:
#         print("启动糖度检测...")
#         sugar_detector.start_detection()
#
#         # 运行30秒，观察检测结果
#         for i in range(300):  # 30秒
#             results = sugar_detector.get_result()
#             print(f"第{i + 1}次查询:")
#             print(f"  状态: {results['status']}")
#             print(f"  糖度: {results['sugar_content']}")
#             print(f"  酸度: {results['acid_content']}")
#             print(f"  流水号: {results['serial_number']}")
#             print(f"  异常码: {results['exception_code']}")
#             print(f"  最后更新: {time.ctime(results['last_update']) if results['last_update'] else 'None'}")
#             print("-" * 50)
#
#             time.sleep(0.1)
#
#     except KeyboardInterrupt:
#         print("\n收到中断信号，正在停止...")
#     finally:
#         sugar_detector.dispose()
#         print("糖度检测器已停止")