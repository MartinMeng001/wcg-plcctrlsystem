"""
Web API模块入口
提供RESTful API接口供前端调用
"""

#from .weight_api import create_weight_api
from .app import create_app
from .server import start_api_server_thread, create_api_server

__all__ = [
    #'create_weight_api',
    'create_app',
    'start_api_server_thread',
    'create_api_server'
]