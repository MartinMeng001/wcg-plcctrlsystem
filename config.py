# config.py 添加的配置项

# 现有的PLC配置
PLC_HOST = '192.168.0.2'
PLC_PORT = 502

# 新增: 糖度检测器(内检仪)配置
SUGAR_DETECTOR_HOST = '192.168.0.20'  # 内检仪IP地址
SUGAR_DETECTOR_PORT = 502             # Modbus TCP端口
SUGAR_DETECTOR_ID = 1                 # Modbus设备ID
SUGAR_POLLING_INTERVAL = 0.1          # 轮询间隔(秒) - 协议要求不小于50ms

# 糖度分级配置（示例）
SUGAR_GRADE_RANGES = [
    {'min': 0.0, 'max': 8.0, 'grade': 1, 'description': '低糖'},
    {'min': 8.1, 'max': 12.0, 'grade': 2, 'description': '中糖'},
    {'min': 12.1, 'max': 16.0, 'grade': 3, 'description': '高糖'},
    {'min': 16.1, 'max': 25.0, 'grade': 4, 'description': '超高糖'},
]

# 酸度分级配置（示例）
ACID_GRADE_RANGES = [
    {'min': 0.0, 'max': 0.5, 'grade': 1, 'description': '低酸'},
    {'min': 0.51, 'max': 1.0, 'grade': 2, 'description': '中酸'},
    {'min': 1.01, 'max': 1.5, 'grade': 3, 'description': '高酸'},
]

# 通道映射（现有配置保持不变）
CHANNEL_MAP = {
    'A': 1,
    'B': 2,
    'C': 3,
    'D': 4
}