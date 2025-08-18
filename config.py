# config.py

# PLC 连接配置
PLC_HOST = '192.168.0.2'
PLC_PORT = 502  # 常见的Modbus TCP端口

# 通道映射：将检测结果映射到PLC的踢出通道
# 键为检测结果的组合，值为踢出的通道号
# 示例：'red_small' -> 1, 'green_large' -> 2, etc.
CHANNEL_MAP = {
    'red_small': 1,
    'red_large': 2,
    'green_small': 3,
    'green_large': 4,
}