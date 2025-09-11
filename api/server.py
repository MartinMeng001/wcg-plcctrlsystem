"""
独立的Web API服务器 (更新版本)
"""

import logging
from threading import Thread
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_api_server(host='127.0.0.1', port=5000, debug=False):
    """创建API服务器"""
    from .app import create_app
    from .weight_api import init_weight_service
    from .sugar_api import init_sugar_service, init_detection_manager
    from .config_api import init_data_manager  # 新增

    # 创建Flask应用
    app = create_app({
        'DEBUG': debug
    })

    # 初始化服务
    try:
        from services import create_weight_service, create_sugar_service
        from utils import init_data_manager as create_data_manager  # 新增

        # 初始化重量服务
        weight_service = create_weight_service()
        init_weight_service(weight_service)
        app.logger.info("重量服务初始化成功")

        # 初始化糖度服务
        sugar_service = create_sugar_service()
        init_sugar_service(sugar_service)
        app.logger.info("糖度服务初始化成功")

        # 新增: 初始化数据管理器
        data_manager = create_data_manager("config.xml")
        init_data_manager(data_manager)
        app.logger.info("配置管理器初始化成功")

    except Exception as e:
        app.logger.error(f"服务初始化失败: {e}")
        return None

    return app, host, port

def run_api_server(app, host, port):
    """运行API服务器"""
    app.run(host=host, port=port, threaded=True)

def start_api_server_thread(host='127.0.0.1', port=5000, debug=False, detection_manager=None, data_manager=None):
    """在独立线程中启动API服务器"""
    result = create_api_server(host, port, debug)
    if result is None:
        print("API服务器创建失败")
        return None

    app, host, port = result

    # 注入检测管理器
    if detection_manager is not None:
        from .sugar_api import init_detection_manager
        init_detection_manager(detection_manager)
        print("DetectionManager已注入到API服务")

    # 新增: 注入数据管理器
    if data_manager is not None:
        from .config_api import init_data_manager
        init_data_manager(data_manager)
        print("DataManager已注入到API服务")

    # 在独立线程中运行
    server_thread = Thread(
        target=run_api_server,
        args=(app, host, port),
        daemon=True,
        name="WeightAPIServer"
    )

    server_thread.start()
    print(f"Weight & Sugar API服务器已启动: http://{host}:{port}")
    return server_thread