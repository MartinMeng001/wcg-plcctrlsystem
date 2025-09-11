"""
config.xml配置文件相关的Web API接口
提供XML配置文件的读取、更新和管理功能
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
import os

# 创建蓝图
config_bp = Blueprint('config', __name__)

# 全局配置管理器实例
_data_manager = None


def init_data_manager(data_manager):
    """初始化数据管理器实例"""
    global _data_manager
    _data_manager = data_manager


def get_data_manager():
    """获取数据管理器实例"""
    if _data_manager is None:
        raise RuntimeError("Data manager not initialized")
    return _data_manager

# ===============================
# 内部辅助函数 (请将这些函数添加到文件顶部，在路由之前)
# ===============================
def _parse_channel_element(channel_elem: ET.Element) -> Dict[str, Any]:
    """解析XML中的channel元素"""
    channel_data = {
        'id': channel_elem.attrib.get('id'),
        'name': channel_elem.attrib.get('name', ''),
        'curtemplateId': '',
        'detectors': []
    }

    curtemplate_id_elem = channel_elem.find('curtemplateId')
    if curtemplate_id_elem is not None:
        channel_data['curtemplateId'] = curtemplate_id_elem.text

    for detector_elem in channel_elem.findall('detector'):
        detector_data = {
            'type': detector_elem.find('type').text if detector_elem.find('type') is not None else '',
            'modbusTcp': {
                'ip': detector_elem.find('modbusTcp').find('ip').text,
                'port': int(detector_elem.find('modbusTcp').find('port').text)
            }
        }
        channel_data['detectors'].append(detector_data)

    return channel_data


# ===============================
# XML配置文件管理接口
# ===============================

@config_bp.route('/config/xml', methods=['GET'])
def get_xml_config():
    """
    获取当前XML配置文件内容

    Returns:
        200: 配置数据
        500: 服务错误
    """
    try:
        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        # 获取基础配置
        base_config = {
            'current_template_id': data_manager.cur_template_id,
            'weight_offset': data_manager.weight_offset,
            'water_offset': data_manager.water_offset
        }

        # 获取所有模板信息
        templates = []
        templates_elements = config_manager.get_templates_elements()

        for template_id, template_elem in templates_elements.items():
            template_info = {
                'id': template_id,
                'name': template_elem.attrib.get('name', ''),
                'scores': _parse_scores_config(template_elem),
                'detectors': _parse_detectors_config(template_elem)
            }
            templates.append(template_info)

        return jsonify({
            'success': True,
            'message': '获取XML配置成功',
            'data': {
                'config': base_config,
                'templates': templates,
                'file_path': config_manager.file_path,
                'timestamp': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"获取XML配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取XML配置失败: {str(e)}',
            'data': None
        }), 500


@config_bp.route('/config/xml/base', methods=['POST'])
def update_base_config():
    """
    更新基础配置(当前模板ID、偏移量等)

    Request Body:
        {
            "current_template_id": "1",
            "weight_offset": 0,
            "water_offset": 4
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求参数错误：请求体为空',
                'data': None
            }), 400

        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        # 更新配置值
        config_element = config_manager.root.find('config')
        if config_element is None:
            # 如果config节点不存在，创建一个
            config_element = ET.SubElement(config_manager.root, 'config')

        # 更新各个配置项
        if 'current_template_id' in data:
            _update_or_create_element(config_element, 'curtemplateId', str(data['current_template_id']))
            data_manager.cur_template_id = str(data['current_template_id'])

        if 'weight_offset' in data:
            _update_or_create_element(config_element, 'weightOffset', str(data['weight_offset']))
            data_manager.weight_offset = int(data['weight_offset'])

        if 'water_offset' in data:
            _update_or_create_element(config_element, 'waterOffset', str(data['water_offset']))
            data_manager.water_offset = int(data['water_offset'])

        # 保存到文件
        config_manager.tree.write(config_manager.file_path, encoding='utf-8', xml_declaration=True)

        return jsonify({
            'success': True,
            'message': '基础配置更新成功',
            'data': {
                'current_template_id': data_manager.cur_template_id,
                'weight_offset': data_manager.weight_offset,
                'water_offset': data_manager.water_offset
            }
        })

    except Exception as e:
        current_app.logger.error(f"更新基础配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新基础配置失败: {str(e)}',
            'data': None
        }), 500


@config_bp.route('/config/xml/templates', methods=['GET'])
def get_templates():
    """
    获取所有模板信息

    Returns:
        200: 模板列表
        500: 服务错误
    """
    try:
        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        templates = []
        templates_elements = config_manager.get_templates_elements()

        for template_id, template_elem in templates_elements.items():
            template_info = {
                'id': template_id,
                'name': template_elem.attrib.get('name', ''),
                'scores': _parse_scores_config(template_elem),
                'detectors': _parse_detectors_config(template_elem)
            }
            templates.append(template_info)

        return jsonify({
            'success': True,
            'message': '获取模板列表成功',
            'data': {
                'templates': templates,
                'current_template_id': data_manager.cur_template_id
            }
        })

    except Exception as e:
        current_app.logger.error(f"获取模板列表失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取模板列表失败: {str(e)}',
            'data': None
        }), 500


@config_bp.route('/config/xml/templates/<template_id>', methods=['POST'])
def update_template(template_id):
    """
    更新指定模板配置

    Request Body:
        {
            "name": "模板名称",
            "scores": {
                "enabled": true,
                "score_rules": [
                    {"out": "8", "subout": "9", "score": 80}
                ]
            },
            "detectors": {
                "weight": {
                    "wg": "50",
                    "max": "799",
                    "bad_levels": [...],
                    "good_levels": [...]
                }
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求参数错误：请求体为空',
                'data': None
            }), 400

        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        # 查找或创建模板元素
        templates_element = config_manager.root.find('templates')
        if templates_element is None:
            templates_element = ET.SubElement(config_manager.root, 'templates')

        # 查找现有模板或创建新模板
        template_element = None
        for template in templates_element.findall('template'):
            if template.attrib.get('id') == template_id:
                template_element = template
                break

        if template_element is None:
            template_element = ET.SubElement(templates_element, 'template')
            template_element.set('id', template_id)

        # 更新模板属性
        if 'name' in data:
            template_element.set('name', data['name'])

        # 更新scores配置
        if 'scores' in data:
            _update_scores_config(template_element, data['scores'])

        # 更新detectors配置
        if 'detectors' in data:
            _update_detectors_config(template_element, data['detectors'])

        # 保存到文件
        config_manager.tree.write(config_manager.file_path, encoding='utf-8', xml_declaration=True)

        # 重新加载模板管理器
        # data_manager.template_manager = TemplateManager(config_manager)

        return jsonify({
            'success': True,
            'message': f'模板 {template_id} 更新成功',
            'data': {
                'template_id': template_id,
                'updated_at': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"更新模板失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新模板失败: {str(e)}',
            'data': None
        }), 500


# 在你的 config_api.py 文件中

@config_bp.route('/config/xml/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    """
    删除指定模板

    Args:
        template_id: 要删除的模板的ID

    Returns:
        200: 成功删除
        404: 模板不存在
        500: 服务错误
    """
    try:
        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        templates_element = config_manager.root.find('templates')
        if templates_element is None:
            return jsonify({
                'success': False,
                'message': 'templates节点不存在',
                'data': None
            }), 404

        template_element = None
        for template in templates_element.findall('template'):
            if template.attrib.get('id') == template_id:
                template_element = template
                break

        if template_element is None:
            return jsonify({
                'success': False,
                'message': f'模板 {template_id} 不存在',
                'data': None
            }), 404

        # 找到并移除模板元素
        templates_element.remove(template_element)

        # 保存到文件
        config_manager.tree.write(config_manager.file_path, encoding='utf-8', xml_declaration=True)

        return jsonify({
            'success': True,
            'message': f'模板 {template_id} 删除成功',
            'data': {
                'template_id': template_id
            }
        })

    except Exception as e:
        current_app.logger.error(f"删除模板失败: {e}")
        return jsonify({
            'success': False,
            'message': f'删除模板失败: {str(e)}',
            'data': None
        }), 500

@config_bp.route('/config/xml/reload', methods=['POST'])
def reload_config():
    """
    重新加载配置文件

    Returns:
        200: 重新加载成功
        500: 服务错误
    """
    try:
        data_manager = get_data_manager()

        # 重新加载配置文件
        success = data_manager.config_manager.load_config()
        if not success:
            return jsonify({
                'success': False,
                'message': '重新加载配置文件失败',
                'data': None
            }), 500

        # 重新初始化所有配置
        data_manager._load_all_configs()

        return jsonify({
            'success': True,
            'message': '配置文件重新加载成功',
            'data': {
                'current_template_id': data_manager.cur_template_id,
                'weight_offset': data_manager.weight_offset,
                'water_offset': data_manager.water_offset,
                'reloaded_at': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"重新加载配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'重新加载配置失败: {str(e)}',
            'data': None
        }), 500


@config_bp.route('/config/xml/backup', methods=['POST'])
def backup_config():
    """
    备份当前配置文件

    Returns:
        200: 备份成功
        500: 服务错误
    """
    try:
        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{config_manager.file_path}.backup_{timestamp}"

        # 创建备份
        config_manager.tree.write(backup_path, encoding='utf-8', xml_declaration=True)

        return jsonify({
            'success': True,
            'message': '配置文件备份成功',
            'data': {
                'backup_path': backup_path,
                'backup_time': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"备份配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'备份配置失败: {str(e)}',
            'data': None
        }), 500


# ===============================
# Channels (通道)管理接口
# ===============================

@config_bp.route('/config/xml/channels', methods=['GET'])
def get_channels():
    """
    获取所有通道的列表和配置

    Returns:
        200: 通道列表数据
        404: 配置文件未加载或channels节点不存在
    """
    try:
        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        channels_element = config_manager.root.find('channels')
        if channels_element is None:
            return jsonify({
                'success': True,
                'message': 'channels节点不存在，返回空列表',
                'data': []
            })

        channels_list = []
        for channel_elem in channels_element.findall('channel'):
            channel_data = _parse_channel_element(channel_elem)
            channels_list.append(channel_data)

        return jsonify({
            'success': True,
            'message': '成功获取通道列表',
            'data': channels_list
        })

    except Exception as e:
        current_app.logger.error(f"获取通道列表失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取通道列表失败: {str(e)}',
            'data': None
        }), 500


@config_bp.route('/config/xml/channels/<channel_id>', methods=['POST'])
def update_channel(channel_id):
    """
    更新或创建指定通道的配置

    Request Body:
        {
            "name": "通道名称",
            "curtemplateId": "模板ID",
            "detectors": [
                {
                    "type": "weight",
                    "modbusTcp": { "ip": "192.168.0.2", "port": 502 }
                },
                ...
            ]
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求参数错误：请求体为空',
                'data': None
            }), 400

        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        channels_element = config_manager.root.find('channels')
        if channels_element is None:
            channels_element = ET.SubElement(config_manager.root, 'channels')

        channel_element = None
        for channel in channels_element.findall('channel'):
            if channel.attrib.get('id') == channel_id:
                channel_element = channel
                break

        # 如果通道不存在，则创建新通道
        if channel_element is None:
            channel_element = ET.SubElement(channels_element, 'channel')
            channel_element.set('id', channel_id)

        # 更新通道属性
        if 'name' in data:
            channel_element.set('name', data['name'])
        if 'curtemplateId' in data:
            channel_element.find('curtemplateId').text = data['curtemplateId']

        # 更新 detectors 配置
        if 'detectors' in data and isinstance(data['detectors'], list):
            _update_detectors_config_for_channel(channel_element, data['detectors'])

        config_manager.tree.write(config_manager.file_path, encoding='utf-8', xml_declaration=True)

        return jsonify({
            'success': True,
            'message': f'通道 {channel_id} 更新成功',
            'data': {
                'channel_id': channel_id,
                'updated_at': datetime.now().isoformat()
            }
        })

    except Exception as e:
        current_app.logger.error(f"更新通道失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新通道失败: {str(e)}',
            'data': None
        }), 500


@config_bp.route('/config/xml/channels/<channel_id>', methods=['DELETE'])
def delete_channel(channel_id):
    """
    删除指定通道
    """
    try:
        data_manager = get_data_manager()
        config_manager = data_manager.config_manager

        if config_manager.root is None:
            return jsonify({
                'success': False,
                'message': '配置文件未加载',
                'data': None
            }), 404

        channels_element = config_manager.root.find('channels')
        if channels_element is None:
            return jsonify({
                'success': False,
                'message': 'channels节点不存在',
                'data': None
            }), 404

        channel_to_remove = None
        for channel in channels_element.findall('channel'):
            if channel.attrib.get('id') == channel_id:
                channel_to_remove = channel
                break

        if channel_to_remove is None:
            return jsonify({
                'success': False,
                'message': f'通道 {channel_id} 不存在',
                'data': None
            }), 404

        channels_element.remove(channel_to_remove)
        config_manager.tree.write(config_manager.file_path, encoding='utf-8', xml_declaration=True)

        return jsonify({
            'success': True,
            'message': f'通道 {channel_id} 删除成功',
            'data': {'channel_id': channel_id}
        })

    except Exception as e:
        current_app.logger.error(f"删除通道失败: {e}")
        return jsonify({
            'success': False,
            'message': f'删除通道失败: {str(e)}',
            'data': None
        }), 500


def _update_detectors_config_for_channel(channel_elem: ET.Element, detectors_data: List[Dict[str, Any]]):
    """根据JSON数据更新XML中的detectors配置"""
    # 移除现有所有detectors，然后重新创建
    for detector_elem in channel_elem.findall('detector'):
        channel_elem.remove(detector_elem)

    for detector_data in detectors_data:
        detector_elem = ET.SubElement(channel_elem, 'detector')

        type_elem = ET.SubElement(detector_elem, 'type')
        type_elem.text = detector_data['type']

        modbus_elem = ET.SubElement(detector_elem, 'modbusTcp')

        ip_elem = ET.SubElement(modbus_elem, 'ip')
        ip_elem.text = detector_data['modbusTcp']['ip']

        port_elem = ET.SubElement(modbus_elem, 'port')
        port_elem.text = str(detector_data['modbusTcp']['port'])

# ===============================
# 辅助函数
# ===============================

def _parse_scores_config(template_elem: ET.Element) -> Dict[str, Any]:
    """解析scores配置"""
    scores_element = template_elem.find("scores")
    if scores_element is None:
        return {'enabled': False, 'score_rules': []}

    enabled = scores_element.attrib.get("enable") == "1"
    score_rules = []

    for score_elem in scores_element.findall('score'):
        score_rules.append({
            'out': score_elem.attrib.get('out'),
            'subout': score_elem.attrib.get('subout'),
            'score': int(score_elem.text) if score_elem.text else 0
        })

    return {
        'enabled': enabled,
        'score_rules': score_rules
    }


def _parse_detectors_config(template_elem: ET.Element) -> Dict[str, Any]:
    """解析detectors配置"""
    detectors_element = template_elem.find("detectors")
    if detectors_element is None:
        return {}

    detectors = {}
    for detector_elem in detectors_element:
        detector_name = detector_elem.tag
        detectors[detector_name] = {
            'wg': detector_elem.attrib.get('wg'),
            'max': detector_elem.attrib.get('max'),
            'bad_levels': _parse_levels(detector_elem.find("badLevel")),
            'good_levels': _parse_levels(detector_elem.find("goodLevel"))
        }

    return detectors


def _parse_levels(level_element: ET.Element) -> List[Dict[str, Any]]:
    """解析level节点"""
    if level_element is None:
        return []

    levels = []
    for level_elem in level_element.findall('level'):
        level_data = {
            'out': level_elem.attrib.get('out'),
            'subout': level_elem.attrib.get('subout')
        }

        min_elem = level_elem.find('min')
        max_elem = level_elem.find('max')

        if min_elem is not None and min_elem.text:
            level_data['min'] = float(min_elem.text)
        if max_elem is not None and max_elem.text:
            level_data['max'] = float(max_elem.text)

        levels.append(level_data)

    return levels


def _update_or_create_element(parent: ET.Element, tag: str, text: str):
    """更新或创建XML元素"""
    element = parent.find(tag)
    if element is None:
        element = ET.SubElement(parent, tag)
    element.text = text


def _update_scores_config(template_elem: ET.Element, scores_data: Dict[str, Any]):
    """更新scores配置"""
    # 移除现有的scores元素
    scores_element = template_elem.find('scores')
    if scores_element is not None:
        template_elem.remove(scores_element)

    # 创建新的scores元素
    scores_element = ET.SubElement(template_elem, 'scores')
    scores_element.set('enable', '1' if scores_data.get('enabled', False) else '0')

    # 添加score规则
    for rule in scores_data.get('score_rules', []):
        score_elem = ET.SubElement(scores_element, 'score')
        if rule.get('out'):
            score_elem.set('out', str(rule['out']))
        if rule.get('subout'):
            score_elem.set('subout', str(rule['subout']))
        score_elem.text = str(rule.get('score', 0))


def _update_detectors_config(template_elem: ET.Element, detectors_data: Dict[str, Any]):
    """更新detectors配置"""
    # 移除现有的detectors元素
    detectors_element = template_elem.find('detectors')
    if detectors_element is not None:
        template_elem.remove(detectors_element)

    # 创建新的detectors元素
    detectors_element = ET.SubElement(template_elem, 'detectors')

    # 添加各个检测器
    for detector_name, detector_config in detectors_data.items():
        detector_elem = ET.SubElement(detectors_element, detector_name)

        # 设置属性
        if detector_config.get('wg'):
            detector_elem.set('wg', str(detector_config['wg']))
        if detector_config.get('max'):
            detector_elem.set('max', str(detector_config['max']))

        # 添加badLevel和goodLevel
        _create_levels_element(detector_elem, 'badLevel', detector_config.get('bad_levels', []))
        _create_levels_element(detector_elem, 'goodLevel', detector_config.get('good_levels', []))


def _create_levels_element(parent: ET.Element, level_type: str, levels_data: List[Dict[str, Any]]):
    """创建levels元素"""
    levels_element = ET.SubElement(parent, level_type)

    for level_data in levels_data:
        level_elem = ET.SubElement(levels_element, 'level')

        # 设置属性
        if level_data.get('out'):
            level_elem.set('out', str(level_data['out']))
        if level_data.get('subout'):
            level_elem.set('subout', str(level_data['subout']))

        # 添加min/max子元素
        if 'min' in level_data:
            min_elem = ET.SubElement(level_elem, 'min')
            min_elem.text = str(level_data['min'])
        if 'max' in level_data:
            max_elem = ET.SubElement(level_elem, 'max')
            max_elem.text = str(level_data['max'])


@config_bp.route('/config/xml/validate', methods=['POST'])
def validate_xml_config():
    """
    验证XML配置格式

    Request Body:
        {
            "xml_content": "<s><config>...</config></s>"
        }
    """
    try:
        data = request.get_json()
        if not data or 'xml_content' not in data:
            return jsonify({
                'success': False,
                'message': '请求参数错误：缺少xml_content字段',
                'data': None
            }), 400

        xml_content = data['xml_content']

        # 尝试解析XML
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return jsonify({
                'success': False,
                'message': f'XML格式错误: {str(e)}',
                'data': None
            }), 400

        # 基础结构验证
        config_elem = root.find('config')
        templates_elem = root.find('templates')

        validation_results = {
            'valid': True,
            'issues': []
        }

        if config_elem is None:
            validation_results['issues'].append('缺少config节点')
        if templates_elem is None:
            validation_results['issues'].append('缺少templates节点')

        # 模板验证
        if templates_elem is not None:
            template_ids = []
            for template in templates_elem.findall('template'):
                template_id = template.attrib.get('id')
                if not template_id:
                    validation_results['issues'].append('发现没有id属性的template')
                elif template_id in template_ids:
                    validation_results['issues'].append(f'重复的模板ID: {template_id}')
                else:
                    template_ids.append(template_id)

        if validation_results['issues']:
            validation_results['valid'] = False

        return jsonify({
            'success': True,
            'message': 'XML配置验证完成',
            'data': validation_results
        })

    except Exception as e:
        current_app.logger.error(f"验证XML配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'验证XML配置失败: {str(e)}',
            'data': None
        }), 500