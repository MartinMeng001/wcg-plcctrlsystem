"""
Flask应用创建和配置 (更新版本)
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
            "origins": ["http://localhost:3000", "http://localhost:8080"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # 注册API蓝图
    from .weight_api import weight_bp
    from .sugar_api import sugar_bp
    from .config_api import config_bp  # 新增: config.xml API蓝图

    app.register_blueprint(weight_bp, url_prefix='/api')
    app.register_blueprint(sugar_bp, url_prefix='/api')
    app.register_blueprint(config_bp, url_prefix='/api')  # 新增

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

    # 系统概览端点
    @app.route('/api/system/overview')
    def system_overview():
        """获取系统整体状态概览"""
        try:
            from .weight_api import get_weight_service
            from .sugar_api import get_sugar_service, get_detection_manager
            from .config_api import get_data_manager  # 新增

            # 获取各服务状态
            weight_service = get_weight_service()
            sugar_service = get_sugar_service()
            detection_manager = get_detection_manager()
            data_manager = get_data_manager()  # 新增

            weight_status = weight_service.get_status()
            sugar_status = sugar_service.get_status()

            # 获取实时检测数据
            all_results = detection_manager.get_all_results()

            return {
                'success': True,
                'data': {
                    'weight_detection': {
                        'status': weight_status.get('status'),
                        'recent_records': weight_status.get('recent_records', [])[:5]
                    },
                    'sugar_detection': {
                        'status': sugar_status.get('status'),
                        'latest_reading': sugar_status.get('latest_reading')
                    },
                    'config': {  # 新增: 配置状态
                        'current_template_id': data_manager.cur_template_id,
                        'weight_offset': data_manager.weight_offset,
                        'water_offset': data_manager.water_offset,
                        'config_file': data_manager.config_manager.file_path
                    },
                    'realtime_data': all_results,
                    'timestamp': datetime.now().isoformat()
                }
            }

        except Exception as e:
            # current_app.logger.error(f"获取系统概览失败: {e}")
            return {
                'success': False,
                'message': f'获取系统概览失败: {str(e)}',
                'data': None
            }, 500

    return app