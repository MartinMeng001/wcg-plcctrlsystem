# api/event_api.py
"""
事件监听系统的Web API接口
提供事件查询、统计和管理的RESTful API
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date, timedelta
import logging
from typing import Dict, Any, List, Optional

from services.events import (
    EventService, EventType, SortingType, CommunicationStatus,
    get_event_service
)

# 创建蓝图
event_bp = Blueprint('events', __name__)

# 全局服务实例
_event_service = None


def init_event_service(service: EventService):
    """初始化事件服务实例"""
    global _event_service
    _event_service = service


def get_event_service_instance():
    """获取事件服务实例"""
    if _event_service is None:
        raise RuntimeError("Event service not initialized")
    return _event_service


# ===============================
# 事件查询接口
# ===============================

@event_bp.route('/events/sorting', methods=['GET'])
def get_sorting_events():
    """
    查询分拣事件记录

    Query Parameters:
        start_time: 开始时间 (ISO格式)
        end_time: 结束时间 (ISO格式)
        event_types: 事件类型列表 (逗号分隔)
        limit: 记录数量限制 (默认100)
    """
    try:
        # 解析查询参数
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        event_types_str = request.args.get('event_types')
        limit = request.args.get('limit', 100, type=int)

        # 限制查询数量
        limit = min(max(1, limit), 1000)

        # 解析时间参数
        start_time = None
        end_time = None

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '开始时间格式错误，请使用ISO格式',
                    'data': None
                }), 400

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '结束时间格式错误，请使用ISO格式',
                    'data': None
                }), 400

        # 解析事件类型
        event_types = None
        if event_types_str:
            try:
                event_type_names = event_types_str.split(',')
                event_types = [EventType(name.strip()) for name in event_type_names]
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'message': f'事件类型参数错误: {str(e)}',
                    'data': None
                }), 400

        # 查询数据
        event_service = get_event_service_instance()

        # 由于API是同步的，我们需要在这里运行异步方法
        import asyncio
        try:
            records = asyncio.get_event_loop().run_until_complete(
                event_service.get_sorting_events_async(start_time, end_time, event_types, limit)
            )
        except RuntimeError:
            # 如果没有事件循环，创建一个新的
            records = asyncio.run(
                event_service.get_sorting_events_async(start_time, end_time, event_types, limit)
            )

        # 转换为前端友好的格式
        events_data = []
        for record in records:
            events_data.append({
                'id': record.id,
                'event_id': record.event_id,
                'event_type': record.event_type,
                'sorting_type': record.sorting_type,
                'channels': record.channels,
                'count': record.count,
                'weight': record.weight,
                'grade': record.grade,
                'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                'source_data': record.source_data
            })

        return jsonify({
            'success': True,
            'message': f'获取到{len(events_data)}条分拣事件记录',
            'data': {
                'events': events_data,
                'total': len(events_data),
                'query_params': {
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'event_types': event_types_str,
                    'limit': limit
                }
            }
        })

    except Exception as e:
        current_app.logger.error(f"查询分拣事件失败: {e}")
        return jsonify({
            'success': False,
            'message': f'查询分拣事件失败: {str(e)}',
            'data': None
        }), 500


@event_bp.route('/events/communication', methods=['GET'])
def get_communication_events():
    """
    查询通讯状态变更事件

    Query Parameters:
        device_name: 设备名称 (PLC, Sugar_Detector)
        start_time: 开始时间 (ISO格式)
        end_time: 结束时间 (ISO格式)
        limit: 记录数量限制 (默认100)
    """
    try:
        device_name = request.args.get('device_name')
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        limit = request.args.get('limit', 100, type=int)

        limit = min(max(1, limit), 1000)

        # 解析时间参数
        start_time = None
        end_time = None

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '开始时间格式错误',
                    'data': None
                }), 400

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '结束时间格式错误',
                    'data': None
                }), 400

        # 查询数据
        event_service = get_event_service_instance()

        import asyncio
        try:
            records = asyncio.get_event_loop().run_until_complete(
                event_service.get_communication_events_async(device_name, start_time, end_time, limit)
            )
        except RuntimeError:
            records = asyncio.run(
                event_service.get_communication_events_async(device_name, start_time, end_time, limit)
            )

        # 转换为前端友好的格式
        events_data = []
        for record in records:
            events_data.append({
                'id': record.id,
                'event_id': record.event_id,
                'device_name': record.device_name,
                'old_status': record.old_status,
                'new_status': record.new_status,
                'error_message': record.error_message,
                'connection_info': record.connection_info,
                'timestamp': record.timestamp.isoformat() if record.timestamp else None
            })

        return jsonify({
            'success': True,
            'message': f'获取到{len(events_data)}条通讯事件记录',
            'data': {
                'events': events_data,
                'total': len(events_data)
            }
        })

    except Exception as e:
        current_app.logger.error(f"查询通讯事件失败: {e}")
        return jsonify({
            'success': False,
            'message': f'查询通讯事件失败: {str(e)}',
            'data': None
        }), 500


@event_bp.route('/events/pulse-frequency', methods=['GET'])
def get_pulse_frequency_events():
    """
    查询光电脉冲频率事件

    Query Parameters:
        start_time: 开始时间 (ISO格式)
        end_time: 结束时间 (ISO格式)
        limit: 记录数量限制 (默认100)
    """
    try:
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        limit = request.args.get('limit', 100, type=int)

        limit = min(max(1, limit), 1000)

        # 解析时间参数
        start_time = None
        end_time = None

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '开始时间格式错误',
                    'data': None
                }), 400

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '结束时间格式错误',
                    'data': None
                }), 400

        # 查询数据
        event_service = get_event_service_instance()

        import asyncio
        try:
            records = asyncio.get_event_loop().run_until_complete(
                event_service.get_pulse_frequency_events_async(start_time, end_time, limit)
            )
        except RuntimeError:
            records = asyncio.run(
                event_service.get_pulse_frequency_events_async(start_time, end_time, limit)
            )

        # 转换为前端友好的格式
        events_data = []
        for record in records:
            events_data.append({
                'id': record.id,
                'event_id': record.event_id,
                'frequency': record.frequency,
                'period': record.period,
                'pulse_count': record.pulse_count,
                'measurement_duration': record.measurement_duration,
                'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                'pulse_data': record.pulse_data
            })

        return jsonify({
            'success': True,
            'message': f'获取到{len(events_data)}条脉冲频率事件记录',
            'data': {
                'events': events_data,
                'total': len(events_data)
            }
        })

    except Exception as e:
        current_app.logger.error(f"查询脉冲频率事件失败: {e}")
        return jsonify({
            'success': False,
            'message': f'查询脉冲频率事件失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# 实时状态接口
# ===============================

@event_bp.route('/events/status', methods=['GET'])
def get_event_system_status():
    """
    获取事件系统状态
    """
    try:
        event_service = get_event_service_instance()

        # 获取服务统计
        statistics = event_service.get_service_statistics()

        # 获取当前通讯状态
        plc_status = event_service.get_current_communication_status("PLC")
        sugar_status = event_service.get_current_communication_status("Sugar_Detector")

        # 获取最近脉冲频率
        recent_pulse_data = event_service.get_recent_pulse_frequency(5)

        status_data = {
            'service_status': {
                'running': statistics['running'],
                'loop_running': statistics['loop_running'],
                'start_time': statistics['service']['start_time'].isoformat() if statistics['service'][
                    'start_time'] else None
            },
            'event_statistics': {
                'total_processed': statistics['service']['total_events_processed'],
                'sorting_events': statistics['service']['sorting_events_count'],
                'communication_events': statistics['service']['communication_events_count'],
                'pulse_frequency_events': statistics['service']['pulse_frequency_events_count']
            },
            'listener_statistics': {
                'queue_size': statistics['listener']['queue_size'],
                'failed_count': statistics['listener']['failed_count'],
                'queue_overflow_count': statistics['listener']['queue_overflow_count'],
                'avg_processing_time': statistics['listener']['avg_processing_time']
            },
            'current_communication_status': {
                'PLC': plc_status.value if plc_status else 'unknown',
                'Sugar_Detector': sugar_status.value if sugar_status else 'unknown'
            },
            'recent_pulse_frequency': recent_pulse_data
        }

        return jsonify({
            'success': True,
            'message': '获取事件系统状态成功',
            'data': status_data
        })

    except Exception as e:
        current_app.logger.error(f"获取事件系统状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取事件系统状态失败: {str(e)}',
            'data': None
        }), 500


@event_bp.route('/events/realtime', methods=['GET'])
def get_realtime_events():
    """
    获取实时事件快照
    包含最近的各类事件和当前状态
    """
    try:
        event_service = get_event_service_instance()

        # 获取最近的各类事件
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            recent_sorting = loop.run_until_complete(
                event_service.get_sorting_events_async(limit=5)
            )
            recent_communication = loop.run_until_complete(
                event_service.get_communication_events_async(limit=5)
            )
            recent_pulse = loop.run_until_complete(
                event_service.get_pulse_frequency_events_async(limit=5)
            )
        except RuntimeError:
            recent_sorting = asyncio.run(event_service.get_sorting_events_async(limit=5))
            recent_communication = asyncio.run(event_service.get_communication_events_async(limit=5))
            recent_pulse = asyncio.run(event_service.get_pulse_frequency_events_async(limit=5))

        # 转换数据格式
        realtime_data = {
            'timestamp': datetime.now().isoformat(),
            'recent_sorting_events': [
                {
                    'event_type': record.event_type,
                    'sorting_type': record.sorting_type,
                    'channels': record.channels,
                    'count': record.count,
                    'weight': record.weight,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None
                }
                for record in recent_sorting[:3]  # 只返回最新3条
            ],
            'recent_communication_events': [
                {
                    'device_name': record.device_name,
                    'old_status': record.old_status,
                    'new_status': record.new_status,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None
                }
                for record in recent_communication[:3]
            ],
            'recent_pulse_events': [
                {
                    'frequency': record.frequency,
                    'period': record.period,
                    'pulse_count': record.pulse_count,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None
                }
                for record in recent_pulse[:3]
            ],
            'current_status': {
                'plc_connected': event_service.get_current_communication_status("PLC") == CommunicationStatus.CONNECTED,
                'sugar_detector_connected': event_service.get_current_communication_status(
                    "Sugar_Detector") == CommunicationStatus.CONNECTED,
                'latest_frequency': recent_pulse[0].frequency if recent_pulse else None
            }
        }

        return jsonify({
            'success': True,
            'message': '获取实时事件数据成功',
            'data': realtime_data
        })

    except Exception as e:
        current_app.logger.error(f"获取实时事件数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取实时事件数据失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# 事件统计接口
# ===============================

@event_bp.route('/events/statistics', methods=['GET'])
def get_event_statistics():
    """
    获取事件统计数据

    Query Parameters:
        start_date: 开始日期 (YYYY-MM-DD格式)
        end_date: 结束日期 (YYYY-MM-DD格式)
        event_types: 事件类型列表 (逗号分隔)
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        event_types_str = request.args.get('event_types')

        # 解析日期参数
        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '开始日期格式错误，请使用YYYY-MM-DD格式',
                    'data': None
                }), 400
        else:
            # 默认查询最近7天
            start_date = (datetime.now() - timedelta(days=7)).date()

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '结束日期格式错误，请使用YYYY-MM-DD格式',
                    'data': None
                }), 400
        else:
            end_date = datetime.now().date()

        # 解析事件类型
        event_types = None
        if event_types_str:
            try:
                event_type_names = event_types_str.split(',')
                event_types = [EventType(name.strip()) for name in event_type_names]
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'message': f'事件类型参数错误: {str(e)}',
                    'data': None
                }), 400

        # 查询统计数据
        event_service = get_event_service_instance()

        import asyncio
        try:
            statistics = asyncio.get_event_loop().run_until_complete(
                event_service.data_store.get_event_statistics(start_date, end_date, event_types)
            )
        except RuntimeError:
            statistics = asyncio.run(
                event_service.data_store.get_event_statistics(start_date, end_date, event_types)
            )

        # 按类型分组统计数据
        stats_by_type = {}
        daily_stats = {}

        for stat in statistics:
            event_type = stat.event_type
            stat_date = stat.date.isoformat()

            # 按类型分组
            if event_type not in stats_by_type:
                stats_by_type[event_type] = {
                    'total_count': 0,
                    'success_count': 0,
                    'error_count': 0,
                    'avg_frequency': 0
                }

            stats_by_type[event_type]['total_count'] += stat.total_count
            stats_by_type[event_type]['success_count'] += stat.success_count
            stats_by_type[event_type]['error_count'] += stat.error_count

            if stat.avg_frequency:
                stats_by_type[event_type]['avg_frequency'] = stat.avg_frequency

            # 按日期分组
            if stat_date not in daily_stats:
                daily_stats[stat_date] = {}

            daily_stats[stat_date][event_type] = {
                'total_count': stat.total_count,
                'success_count': stat.success_count,
                'error_count': stat.error_count,
                'avg_frequency': stat.avg_frequency
            }

        return jsonify({
            'success': True,
            'message': '获取事件统计数据成功',
            'data': {
                'statistics_by_type': stats_by_type,
                'daily_statistics': daily_stats,
                'query_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
        })

    except Exception as e:
        current_app.logger.error(f"获取事件统计数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取事件统计数据失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# 事件管理接口
# ===============================

@event_bp.route('/events/cleanup', methods=['POST'])
def cleanup_old_events():
    """
    清理旧的事件记录

    Request Body:
        {
            "days_to_keep": 30
        }
    """
    try:
        data = request.get_json()
        if not data:
            days_to_keep = 30
        else:
            days_to_keep = data.get('days_to_keep', 30)

        # 验证参数
        if not isinstance(days_to_keep, int) or days_to_keep < 1:
            return jsonify({
                'success': False,
                'message': 'days_to_keep必须是大于0的整数',
                'data': None
            }), 400

        if days_to_keep > 365:
            return jsonify({
                'success': False,
                'message': 'days_to_keep不能超过365天',
                'data': None
            }), 400

        # 执行清理
        event_service = get_event_service_instance()

        import asyncio
        try:
            asyncio.get_event_loop().run_until_complete(
                event_service.cleanup_old_events_async(days_to_keep)
            )
        except RuntimeError:
            asyncio.run(event_service.cleanup_old_events_async(days_to_keep))

        return jsonify({
            'success': True,
            'message': f'成功清理{days_to_keep}天前的事件记录',
            'data': {
                'days_to_keep': days_to_keep,
                'cleanup_time': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"清理事件记录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清理事件记录失败: {str(e)}',
            'data': None
        }), 500


@event_bp.route('/events/database/info', methods=['GET'])
def get_database_info():
    """
    获取事件数据库信息
    """
    try:
        event_service = get_event_service_instance()

        import asyncio
        try:
            db_info = asyncio.get_event_loop().run_until_complete(
                event_service.data_store.get_database_size_info()
            )
        except RuntimeError:
            db_info = asyncio.run(event_service.data_store.get_database_size_info())

        return jsonify({
            'success': True,
            'message': '获取数据库信息成功',
            'data': db_info
        })

    except Exception as e:
        current_app.logger.error(f"获取数据库信息失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取数据库信息失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# 手动事件触发接口（用于测试）
# ===============================

@event_bp.route('/events/test/sorting', methods=['POST'])
def test_sorting_event():
    """
    手动触发分拣事件（用于测试）

    Request Body:
        {
            "type": "reject" | "qualified",
            "channel": 1-4 (for reject) | 1-3 (for qualified type),
            "count": 1,
            "weight": 85.5,
            "grade": 2
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求参数为空',
                'data': None
            }), 400

        event_type = data.get('type')
        channel = data.get('channel')
        count = data.get('count', 1)
        weight = data.get('weight')
        grade = data.get('grade')

        if not event_type or not channel:
            return jsonify({
                'success': False,
                'message': '缺少必要参数: type, channel',
                'data': None
            }), 400

        event_service = get_event_service_instance()

        if event_type == 'reject':
            if channel not in [1, 2, 3, 4]:
                return jsonify({
                    'success': False,
                    'message': '不合格品通道必须是1-4',
                    'data': None
                }), 400

            event_service.emit_sorting_reject_event(
                channel=channel,
                count=count,
                weight=weight,
                grade=grade,
                source_data={'test': True, 'api_trigger': True}
            )

        elif event_type == 'qualified':
            if channel not in [1, 2, 3]:
                return jsonify({
                    'success': False,
                    'message': '合格品类型必须是1-3',
                    'data': None
                }), 400

            event_service.emit_sorting_qualified_event(
                qualified_type=channel,
                count=count,
                weight=weight,
                grade=grade,
                source_data={'test': True, 'api_trigger': True}
            )

        else:
            return jsonify({
                'success': False,
                'message': 'type必须是reject或qualified',
                'data': None
            }), 400

        return jsonify({
            'success': True,
            'message': f'测试{event_type}事件已触发',
            'data': {
                'event_type': event_type,
                'channel': channel,
                'count': count
            }
        })

    except Exception as e:
        current_app.logger.error(f"触发测试分拣事件失败: {e}")
        return jsonify({
            'success': False,
            'message': f'触发测试分拣事件失败: {str(e)}',
            'data': None
        }), 500


@event_bp.route('/events/test/communication', methods=['POST'])
def test_communication_event():
    """
    手动触发通讯状态事件（用于测试）

    Request Body:
        {
            "device": "PLC" | "Sugar_Detector",
            "status": "connected" | "disconnected" | "error" | "timeout",
            "error_message": "optional error message"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求参数为空',
                'data': None
            }), 400

        device = data.get('device')
        status_str = data.get('status')
        error_message = data.get('error_message')

        if not device or not status_str:
            return jsonify({
                'success': False,
                'message': '缺少必要参数: device, status',
                'data': None
            }), 400

        # 验证设备名
        if device not in ['PLC', 'Sugar_Detector']:
            return jsonify({
                'success': False,
                'message': 'device必须是PLC或Sugar_Detector',
                'data': None
            }), 400

        # 验证状态
        try:
            status = CommunicationStatus(status_str)
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'status值无效',
                'data': None
            }), 400

        event_service = get_event_service_instance()

        if device == 'PLC':
            event_service.emit_plc_communication_status_event(
                new_status=status,
                error_message=error_message,
                connection_info={'test': True, 'api_trigger': True}
            )
        else:
            event_service.emit_sugar_communication_status_event(
                new_status=status,
                error_message=error_message,
                connection_info={'test': True, 'api_trigger': True}
            )

        return jsonify({
            'success': True,
            'message': f'测试{device}通讯状态事件已触发',
            'data': {
                'device': device,
                'status': status_str
            }
        })

    except Exception as e:
        current_app.logger.error(f"触发测试通讯事件失败: {e}")
        return jsonify({
            'success': False,
            'message': f'触发测试通讯事件失败: {str(e)}',
            'data': None
        }), 500


@event_bp.route('/events/test/pulse-frequency', methods=['POST'])
def test_pulse_frequency_event():
    """
    手动触发脉冲频率事件（用于测试）

    Request Body:
        {
            "frequency": 25.5,
            "pulse_count": 128,
            "measurement_duration": 5.0
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求参数为空',
                'data': None
            }), 400

        frequency = data.get('frequency')
        pulse_count = data.get('pulse_count', 100)
        measurement_duration = data.get('measurement_duration', 5.0)

        if frequency is None:
            return jsonify({
                'success': False,
                'message': '缺少必要参数: frequency',
                'data': None
            }), 400

        # 验证参数范围
        if not (0 < frequency <= 1000):
            return jsonify({
                'success': False,
                'message': 'frequency必须在0-1000之间',
                'data': None
            }), 400

        period = 1.0 / frequency if frequency > 0 else 0

        event_service = get_event_service_instance()
        event_service.emit_pulse_frequency_event(
            frequency=frequency,
            period=period,
            pulse_count=pulse_count,
            measurement_duration=measurement_duration
        )

        return jsonify({
            'success': True,
            'message': '测试脉冲频率事件已触发',
            'data': {
                'frequency': frequency,
                'period': period,
                'pulse_count': pulse_count,
                'measurement_duration': measurement_duration
            }
        })

    except Exception as e:
        current_app.logger.error(f"触发测试脉冲频率事件失败: {e}")
        return jsonify({
            'success': False,
            'message': f'触发测试脉冲频率事件失败: {str(e)}',
            'data': None
        }), 500