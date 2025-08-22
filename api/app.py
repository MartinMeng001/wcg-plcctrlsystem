"""
Flask应用创建和配置
"""

from flask import Flask
from flask_cors import CORS
import logging
from datetime import datetime


def create_app(config=None):
    """创建Flask应用实例"""
    app = Flask(__name__)

    # 基础配置
    app.config.update({
        'JSON_AS_ASCII': False,  # 支持中文JSON
        'JSON_SORT_KEYS': False,  # 保持字典顺序
        'JSONIFY_PRETTYPRINT_REGULAR': True  # JSON格式化
    })

    # 应用用户配置
    if config:
        app.config.update(config)

    # 启用CORS支持前端跨域请求
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:8080"],  # 前端开发服务器
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # 注册API蓝图
    from .weight_api import weight_bp
    app.register_blueprint(weight_bp, url_prefix='/api')

    # 全局错误处理
    @app.errorhandler(404)
    def not_found(error):
        return {
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'timestamp': datetime.now().isoformat()
        }, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {
            'error': 'Internal Server Error',
            'message': 'An internal server error occurred',
            'timestamp': datetime.now().isoformat()
        }, 500

    # 健康检查端点
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        }

    return app