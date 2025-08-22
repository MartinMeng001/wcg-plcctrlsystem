"""
独立的Web API服务器
可以与主检测程序分离运行
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

    # 创建Flask应用
    app = create_app({
        'DEBUG': debug
    })

    # 初始化服务
    try:
        from services import create_weight_service
        weight_service = create_weight_service()
        init_weight_service(weight_service)
        app.logger.info("重量服务初始化成功")
    except Exception as e:
        app.logger.error(f"重量服务初始化失败: {e}")
        return None

    return app, host, port


def run_api_server(app, host, port):
    """运行API服务器"""
    app.run(host=host, port=port, threaded=True)


def start_api_server_thread(host='127.0.0.1', port=5000, debug=False):
    """在独立线程中启动API服务器"""
    result = create_api_server(host, port, debug)
    if result is None:
        print("API服务器创建失败")
        return None

    app, host, port = result

    # 在独立线程中运行
    server_thread = Thread(
        target=run_api_server,
        args=(app, host, port),
        daemon=True,
        name="WeightAPIServer"
    )

    server_thread.start()
    print(f"Weight API服务器已启动: http://{host}:{port}")
    return server_thread


if __name__ == "__main__":
    # 直接运行API服务器
    import argparse

    parser = argparse.ArgumentParser(description='Weight Detection API Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host address')
    parser.add_argument('--port', type=int, default=5000, help='Port number')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    result = create_api_server(args.host, args.port, args.debug)
    if result:
        app, host, port = result
        print(f"启动Weight API服务器: http://{host}:{port}")
        app.run(host=host, port=port, threaded=True)
    else:
        print("服务器启动失败")