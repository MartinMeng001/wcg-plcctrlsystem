# api/sugar_api.py
"""
糖度检测相关的Web API接口
提供糖度检测数据的RESTful API
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date
import logging
from typing import Dict, Any

# 创建蓝图
sugar_bp = Blueprint('sugar', __name__)

# 全局服务实例（在应用启动时初始化）
_sugar_service = None
_detection_manager = None


def init_sugar_service(service):
    """初始化糖度服务实例"""
    global _sugar_service
    _sugar_service = service


def init_detection_manager(manager):
    """初始化检测管理器实例"""
    global _detection_manager
    _detection_manager = manager


def get_sugar_service():
    """获取糖度服务实例"""
    if _sugar_service is None:
        raise RuntimeError("Sugar service not initialized")
    return _sugar_service


def get_detection_manager():
    """获取检测管理器实例"""
    if _detection_manager is None:
        raise RuntimeError("Detection manager not initialized")
    return _detection_manager


# ===============================
# 实时数据接口
# ===============================

@sugar_bp.route('/sugar/realtime', methods=['GET'])
def get_realtime_sugar_data():
    """
    获取实时糖度检测数据

    Returns:
        200: 实时数据
        500: 服务错误
    """
    try:
        detection_manager = get_detection_manager()

        # 通过DetectionManager统一获取所有检测结果
        all_results = detection_manager.get_all_results()
        sugar_results = all_results.get('SugarDetector', {})

        return jsonify({
            'success': True,
            'message': '获取实时糖度数据成功',
            'data': {
                'sugar_content': sugar_results.get('sugar_content'),
                'acid_content': sugar_results.get('acid_content'),
                'status': sugar_results.get('status'),
                'serial_number': sugar_results.get('serial_number'),
                'exception_code': sugar_results.get('exception_code'),
                'last_update': sugar_results.get('last_update'),
                'timestamp': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"获取实时糖度数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取实时糖度数据失败: {str(e)}',
            'data': None
        }), 500


@sugar_bp.route('/sugar/records', methods=['GET'])
def get_sugar_records():
    """
    获取糖度检测记录

    Query Parameters:
        limit: 记录数量限制 (默认100)

    Returns:
        200: 检测记录列表
        400: 参数错误
        500: 服务错误
    """
    try:
        # 获取查询参数
        limit = request.args.get('limit', 100, type=int)

        if limit <= 0 or limit > 1000:
            return jsonify({
                'success': False,
                'message': 'limit参数必须在1-1000之间',
                'data': None
            }), 400

        service = get_sugar_service()
        records = service.get_recent_records(limit)

        # 转换为前端友好的格式
        records_data = [
            {
                'id': record.id,
                'timestamp': record.timestamp.isoformat(),
                'sugar_content': record.sugar_content,
                'acid_content': record.acid_content,
                'serial_number': record.serial_number,
                'exception_code': record.exception_code,
                'detection_success': record.detection_success
            }
            for record in records
        ]

        return jsonify({
            'success': True,
            'message': f'获取到{len(records_data)}条糖度检测记录',
            'data': {
                'records': records_data,
                'total': len(records_data)
            }
        })

    except Exception as e:
        current_app.logger.error(f"获取糖度记录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取糖度记录失败: {str(e)}',
            'data': None
        }), 500


@sugar_bp.route('/sugar/statistics', methods=['GET'])
def get_sugar_statistics():
    """
    获取糖度检测统计数据

    Query Parameters:
        date: 日期 (YYYY-MM-DD格式，默认今天)

    Returns:
        200: 统计数据
    """
    try:
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '日期格式错误，请使用YYYY-MM-DD格式',
                    'data': None
                }), 400
        else:
            target_date = date.today()

        service = get_sugar_service()
        statistics = service.get_daily_statistics(target_date)

        # 转换为前端友好的格式
        stats_data = {
            'date': target_date.isoformat(),
            'total_count': statistics.total_count,
            'success_count': statistics.success_count,
            'failed_count': statistics.failed_count,
            'success_rate': round(statistics.success_count / statistics.total_count * 100,
                                  2) if statistics.total_count > 0 else 0,
            'sugar_avg': round(statistics.sugar_avg, 2),
            'acid_avg': round(statistics.acid_avg, 2),
            'acid_count': statistics.acid_count
        }

        return jsonify({
            'success': True,
            'message': f'获取{target_date}糖度统计数据成功',
            'data': stats_data
        })

    except Exception as e:
        current_app.logger.error(f"获取糖度统计数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取糖度统计数据失败: {str(e)}',
            'data': None
        }), 500


@sugar_bp.route('/sugar/status', methods=['GET'])
def get_sugar_status():
    """
    获取糖度检测服务状态

    Returns:
        200: 状态信息
        500: 服务错误
    """
    try:
        service = get_sugar_service()
        detection_manager = get_detection_manager()

        # 获取服务状态
        service_status = service.get_status()

        # 获取实时检测状态
        all_results = detection_manager.get_all_results()
        sugar_results = all_results.get('SugarDetector', {})

        status_data = {
            'service_status': service_status['status'],
            'recent_records_count': service_status['recent_records_count'],
            'last_detection_time': service_status['last_detection_time'],
            'realtime_status': sugar_results.get('status', 'unknown'),
            'current_sugar': sugar_results.get('sugar_content'),
            'current_acid': sugar_results.get('acid_content'),
            'current_serial': sugar_results.get('serial_number'),
            'last_update': sugar_results.get('last_update')
        }

        return jsonify({
            'success': True,
            'message': '获取糖度检测状态成功',
            'data': status_data
        })

    except Exception as e:
        current_app.logger.error(f"获取糖度检测状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取糖度检测状态失败: {str(e)}',
            'data': None
        }), 500


@sugar_bp.route('/sugar/detector/control', methods=['POST'])
def control_sugar_detector():
    """
    控制糖度检测器启动/停止

    Request Body:
        {
            "action": "start" | "stop"
        }

    Returns:
        200: 操作成功
        400: 参数错误
        500: 服务错误
    """
    try:
        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({
                'success': False,
                'message': '缺少action参数',
                'data': None
            }), 400

        action = data['action'].lower()
        if action not in ['start', 'stop']:
            return jsonify({
                'success': False,
                'message': 'action参数必须是start或stop',
                'data': None
            }), 400

        detection_manager = get_detection_manager()

        # 找到糖度检测器
        sugar_detector = None
        for detector in detection_manager.detectors:
            if detector.name == 'SugarDetector':
                sugar_detector = detector
                break

        if not sugar_detector:
            return jsonify({
                'success': False,
                'message': '未找到糖度检测器',
                'data': None
            }), 500

        if action == 'start':
            if not sugar_detector.is_detection_active():
                sugar_detector.start_detection()
                message = '糖度检测器启动成功'
            else:
                message = '糖度检测器已在运行'
        else:  # stop
            if sugar_detector.is_detection_active():
                sugar_detector.stop_detection()
                message = '糖度检测器停止成功'
            else:
                message = '糖度检测器已停止'

        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'action': action,
                'detector_active': sugar_detector.is_detection_active()
            }
        })

    except Exception as e:
        current_app.logger.error(f"控制糖度检测器失败: {e}")
        return jsonify({
            'success': False,
            'message': f'控制糖度检测器失败: {str(e)}',
            'data': None
        }), 500


# 手动保存糖度检测记录的接口（用于测试或手动数据录入）
@sugar_bp.route('/sugar/records', methods=['POST'])
def save_sugar_record():
    """
    手动保存糖度检测记录

    Request Body:
        {
            "sugar_content": 12.5,
            "acid_content": 0.8,
            "serial_number": 12345,
            "exception_code": null
        }

    Returns:
        200: 保存成功
        400: 参数错误
        500: 服务错误
    """
    try:
        data = request.get_json()
        if not data or 'sugar_content' not in data:
            return jsonify({
                'success': False,
                'message': '缺少sugar_content参数',
                'data': None
            }), 400

        sugar_content = data.get('sugar_content')
        acid_content = data.get('acid_content')
        serial_number = data.get('serial_number')
        exception_code = data.get('exception_code')

        if not isinstance(sugar_content, (int, float)) or sugar_content < 0:
            return jsonify({
                'success': False,
                'message': '糖度值必须是非负数',
                'data': None
            }), 400

        service = get_sugar_service()
        record = service.process_detection(
            sugar_content=sugar_content,
            acid_content=acid_content,
            serial_number=serial_number,
            exception_code=exception_code
        )

        return jsonify({
            'success': True,
            'message': '糖度检测记录保存成功',
            'data': {
                'record_id': record.id,
                'timestamp': record.timestamp.isoformat(),
                'detection_success': record.detection_success
            }
        })

    except Exception as e:
        current_app.logger.error(f"保存糖度记录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'保存糖度记录失败: {str(e)}',
            'data': None
        }), 500