"""
重量检测相关的Web API接口
提供配置管理和监控数据的RESTful API
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date
import logging
from typing import Dict, Any

# 创建蓝图
weight_bp = Blueprint('weight', __name__)

# 全局服务实例（在应用启动时初始化）
_weight_service = None

def init_weight_service(service):
    """初始化重量服务实例"""
    global _weight_service
    _weight_service = service

def get_weight_service():
    """获取重量服务实例"""
    if _weight_service is None:
        raise RuntimeError("Weight service not initialized")
    return _weight_service


# ===============================
# 配置管理接口
# ===============================

@weight_bp.route('/weight/config', methods=['GET'])
def get_weight_config():
    """
    获取当前重量配置

    Returns:
        200: 配置数据
        500: 服务错误
    """
    try:
        service = get_weight_service()
        config = service.get_current_config()

        if config is None:
            return jsonify({
                'success': False,
                'message': '未找到配置',
                'data': None
            }), 404

        # 转换为前端友好的格式
        config_data = {
            'version': config.version,
            'created_at': config.created_at.isoformat(),
            'updated_at': config.updated_at.isoformat(),
            'configs': [
                {
                    'grade_id': cfg.grade_id,
                    'weight_threshold': cfg.weight_threshold,
                    'kick_channel': cfg.kick_channel,
                    'enabled': cfg.enabled,
                    'description': cfg.description
                }
                for cfg in config.configs
            ]
        }

        return jsonify({
            'success': True,
            'message': '获取配置成功',
            'data': config_data
        })

    except Exception as e:
        current_app.logger.error(f"获取配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取配置失败: {str(e)}',
            'data': None
        }), 500


@weight_bp.route('/weight/config', methods=['POST'])
def update_weight_config():
    """
    更新重量配置

    Request Body:
        {
            "configs": [
                {
                    "grade_id": 1,
                    "weight_threshold": 50.0,
                    "kick_channel": 1,
                    "enabled": true,
                    "description": "轻量级"
                }
            ]
        }

    Returns:
        200: 更新成功
        400: 请求参数错误
        500: 服务错误
    """
    try:
        data = request.get_json()
        if not data or 'configs' not in data:
            return jsonify({
                'success': False,
                'message': '请求参数错误：缺少configs字段',
                'data': None
            }), 400

        # 导入模型类
        from services.weight.models import WeightGradeConfig, WeightConfigSet

        # 解析配置数据
        configs = []
        for cfg_data in data['configs']:
            try:
                config = WeightGradeConfig(
                    grade_id=cfg_data['grade_id'],
                    weight_threshold=float(cfg_data['weight_threshold']),
                    kick_channel=cfg_data['kick_channel'],
                    enabled=bool(cfg_data.get('enabled', True)),
                    description=cfg_data.get('description', '')
                )
                configs.append(config)
            except (KeyError, ValueError, TypeError) as e:
                return jsonify({
                    'success': False,
                    'message': f'配置项格式错误: {str(e)}',
                    'data': None
                }), 400

        # 创建配置集合
        config_set = WeightConfigSet(configs=configs)

        # 更新配置
        service = get_weight_service()
        success, message = service.update_config(config_set)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'data': {'version': config_set.version}
            })
        else:
            return jsonify({
                'success': False,
                'message': message,
                'data': None
            }), 400

    except Exception as e:
        current_app.logger.error(f"更新配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新配置失败: {str(e)}',
            'data': None
        }), 500


@weight_bp.route('/weight/config/validate', methods=['POST'])
def validate_weight_config():
    """
    验证重量配置（不保存）

    Request Body: 同update_weight_config

    Returns:
        200: 验证结果
    """
    try:
        data = request.get_json()
        if not data or 'configs' not in data:
            return jsonify({
                'success': False,
                'message': '请求参数错误：缺少configs字段',
                'data': None
            }), 400

        from services.weight.models import WeightGradeConfig, WeightConfigSet

        # 解析并验证配置
        configs = []
        for cfg_data in data['configs']:
            try:
                config = WeightGradeConfig(
                    grade_id=cfg_data['grade_id'],
                    weight_threshold=float(cfg_data['weight_threshold']),
                    kick_channel=cfg_data['kick_channel'],
                    enabled=bool(cfg_data.get('enabled', True)),
                    description=cfg_data.get('description', '')
                )
                configs.append(config)
            except (KeyError, ValueError, TypeError) as e:
                return jsonify({
                    'success': False,
                    'message': f'配置项格式错误: {str(e)}',
                    'data': None
                })

        config_set = WeightConfigSet(configs=configs)
        is_valid, message = config_set.validate()

        return jsonify({
            'success': is_valid,
            'message': message,
            'data': {'valid': is_valid}
        })

    except Exception as e:
        current_app.logger.error(f"验证配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'验证配置失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# 监控数据接口
# ===============================

@weight_bp.route('/weight/records', methods=['GET'])
def get_weight_records():
    """
    获取重量检测记录

    Query Parameters:
        limit: 记录数量限制 (默认100)

    Returns:
        200: 记录列表
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        limit = min(max(1, limit), 1000)  # 限制范围1-1000

        service = get_weight_service()
        records = service.get_recent_records(limit)

        # 转换为前端友好的格式
        records_data = [
            {
                'id': record.id,
                'timestamp': record.timestamp.isoformat(),
                'weight': record.weight,
                'determined_grade': record.determined_grade,
                'kick_channel': record.kick_channel,
                'detection_success': record.detection_success
            }
            for record in records
        ]

        return jsonify({
            'success': True,
            'message': f'获取到{len(records_data)}条记录',
            'data': {
                'records': records_data,
                'total': len(records_data)
            }
        })

    except Exception as e:
        current_app.logger.error(f"获取记录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取记录失败: {str(e)}',
            'data': None
        }), 500


@weight_bp.route('/weight/statistics', methods=['GET'])
def get_weight_statistics():
    """
    获取重量检测统计数据

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

        service = get_weight_service()
        statistics = service.get_daily_statistics(target_date)

        # 转换为前端友好的格式
        stats_data = {
            'date': target_date.isoformat(),
            'statistics': [
                {
                    'grade_id': stat.grade_id,
                    'total_count': stat.total_count,
                    'weight_sum': stat.weight_sum,
                    'weight_avg': round(stat.weight_avg, 2)
                }
                for stat in statistics
            ],
            'summary': {
                'total_count': sum(stat.total_count for stat in statistics),
                'total_weight': sum(stat.weight_sum for stat in statistics)
            }
        }

        return jsonify({
            'success': True,
            'message': f'获取{target_date}统计数据成功',
            'data': stats_data
        })

    except Exception as e:
        current_app.logger.error(f"获取统计数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取统计数据失败: {str(e)}',
            'data': None
        }), 500


@weight_bp.route('/weight/status', methods=['GET'])
def get_weight_status():
    """
    获取重量检测服务状态

    Returns:
        200: 服务状态
    """
    try:
        service = get_weight_service()
        status = service.get_status()

        return jsonify({
            'success': True,
            'message': '获取状态成功',
            'data': status
        })

    except Exception as e:
        current_app.logger.error(f"获取状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取状态失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# 实时数据接口（可选：WebSocket支持）
# ===============================

@weight_bp.route('/weight/realtime', methods=['GET'])
def get_realtime_data():
    """
    获取实时数据快照
    包含最新的检测记录和性能指标

    Returns:
        200: 实时数据
    """
    try:
        service = get_weight_service()

        # 获取最近的记录
        recent_records = service.get_recent_records(10)

        # 获取今日统计
        today_stats = service.get_daily_statistics()

        # 获取服务状态
        status = service.get_status()

        realtime_data = {
            'timestamp': datetime.now().isoformat(),
            'latest_records': [
                {
                    'timestamp': record.timestamp.isoformat(),
                    'weight': record.weight,
                    'grade': record.determined_grade,
                    'channel': record.kick_channel
                }
                for record in recent_records[:5]  # 只返回最新5条
            ],
            'today_summary': {
                'total_count': sum(stat.total_count for stat in today_stats),
                'by_grade': {
                    str(stat.grade_id): {
                        'count': stat.total_count,
                        'avg_weight': round(stat.weight_avg, 2)
                    }
                    for stat in today_stats
                }
            },
            'service_status': {
                'status': status.get('status'),
                'recent_records_count': status.get('recent_records_count', 0)
            }
        }

        return jsonify({
            'success': True,
            'message': '获取实时数据成功',
            'data': realtime_data
        })

    except Exception as e:
        current_app.logger.error(f"获取实时数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取实时数据失败: {str(e)}',
            'data': None
        }), 500