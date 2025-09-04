# config_manager.py

import xml.etree.ElementTree as ET
from typing import Any, Tuple, Dict, List


class ConfigManager:
    """
    一个用于读写 XML 配置文件的工具类。
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None

    def load_config(self) -> bool:
        """加载 XML 配置文件。"""
        try:
            self.tree = ET.parse(self.file_path)
            self.root = self.tree.getroot()
            print(f"配置文件 {self.file_path} 加载成功。")
            return True
        except FileNotFoundError:
            print(f"错误: 配置文件 {self.file_path} 未找到。")
            return False
        except ET.ParseError:
            print(f"错误: 解析配置文件 {self.file_path} 失败。文件格式不正确。")
            return False

    def get_templates_elements(self) -> Dict[str, ET.Element]:
        """
        获取所有模板的XML元素，以模板ID为键存储在字典中。

        Returns:
            Dict[str, ET.Element]: 包含所有模板元素的字典。
        """
        if self.root is None:
            print("错误: 配置文件尚未加载。")
            return {}

        templates_dict = {}
        templates_element = self.root.find('templates')
        if templates_element is not None:
            for template_elem in templates_element.findall('template'):
                template_id = template_elem.attrib.get('id')
                if template_id:
                    templates_dict[template_id] = template_elem
        return templates_dict

    def get_config_value(self, element_path: str) -> str | None:
        """根据 XML 路径获取配置值。"""
        if self.root is None:
            return None
        element = self.root.find(element_path)
        if element is not None and element.text is not None:
            return element.text
        return None