# __init__.py

from .DataManager import DataManager
from .config_manager import ConfigManager
from .template_manager import TemplateManager, Template

# 实例化 DataManager 类
# 注意：这里的 'config.xml' 需要根据你的实际文件路径进行修改
# data_manager = DataManager('config.xml')

# 或者，如果你希望延迟初始化，可以这么做：
_data_manager = None
def init_data_manager(file_name):
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager(file_name)
    return _data_manager

def get_data_manager():
    global _data_manager
    return _data_manager

# 导出所有相关类和函数
__all__ = [
    'DataManager',
    'ConfigManager',
    'TemplateManager',
    'Template',
    'init_data_manager',
    'get_data_manager'
]