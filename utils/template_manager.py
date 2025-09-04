# template_manager.py

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any

# 假设 config_manager 模块在同一目录下
from .config_manager import ConfigManager


class Template:
    """
    一个筛选模板类，用于根据 weight 和 water 值筛选通道。
    这个类现在直接从内存中的XML元素初始化。
    """

    def __init__(self, template_element: ET.Element):
        """
        初始化模板实例。

        Args:
            template_element (ET.Element): 从配置文件中解析得到的模板XML元素。
        """
        self.template_id = template_element.attrib.get('id')
        self._scores_enabled = False
        self._detectors = {}
        self._scores_config = []

        self._parse_template(template_element)

    def _parse_template(self, template_element: ET.Element):
        """解析模板的XML元素，并将其转换为内存数据。"""
        # 解析 <scores> 配置
        scores_element = template_element.find("scores")
        if scores_element is not None:
            self._scores_enabled = scores_element.attrib.get("enable") == "1"
            self._scores_config = [
                (e.attrib.get('out'), e.attrib.get('subout'), int(e.text))
                for e in scores_element.findall('score')
            ]

        # 解析 <detectors> 配置
        detectors_element = template_element.find("detectors")
        if detectors_element is not None:
            for detector_elem in detectors_element:
                detector_name = detector_elem.tag
                self._detectors[detector_name] = {
                    "wg": detector_elem.attrib.get("wg"),
                    "max": detector_elem.attrib.get("max"),
                    "badLevel": self._parse_levels(detector_elem.find("badLevel")),
                    "goodLevel": self._parse_levels(detector_elem.find("goodLevel")),
                }

    def _parse_levels(self, level_element: ET.Element) -> list[dict]:
        """解析 level 节点。"""
        if level_element is None:
            return []
        levels = []
        for level_elem in level_element.findall('level'):
            levels.append({
                "out": level_elem.attrib.get('out'),
                "subout": level_elem.attrib.get('subout'),
                "min": int(level_elem.find('min').text),
                "max": int(level_elem.find('max').text)
            })
        return levels

    def _check_bad_level(self, detector_name: str, value: int) -> int | None:
        """检查值是否符合 badLevel 规则。"""
        detector = self._detectors.get(detector_name)
        if not detector:
            return None
        for level in detector["badLevel"]:
            if int(level["min"]) <= value <= int(level["max"]):
                return int(level["out"])
        return None

    def _get_channel_from_level(self, level: dict) -> int:
        """根据当前时间（奇偶秒）返回 out 或 subout。"""
        current_second = datetime.now().second
        if current_second % 2 == 0:
            return int(level["out"])
        else:
            return int(level["subout"])

    def get_channel(self, weight_value: int, water_value: int) -> int | None:
        """
        根据传入的 weight 和 water 值筛选通道。
        """
        # 1. 筛选最高优先级：badLevel
        bad_channel = self._check_bad_level("weight", weight_value)
        if bad_channel is not None:
            print("weight 命中 badLevel 规则")
            return bad_channel

        bad_channel = self._check_bad_level("water", water_value)
        if bad_channel is not None:
            print("water 命中 badLevel 规则")
            return bad_channel

        # 2. 如果 scores 为 enable，则使用得分筛选法
        if self._scores_enabled:
            # 获取权重和最大值
            wg_weight_str = self._detectors.get("weight", {}).get("wg", "0")
            wg_water_str = self._detectors.get("water", {}).get("wg", "0")
            wg_weight = int(wg_weight_str) if wg_water_str else 0
            wg_water = int(wg_water_str) if wg_water_str else 0

            # 找到 goodLevel 的最大值作为分母
            weight_max_str = self._detectors.get("weight", {}).get("max", 0)
            weight_max = int(weight_max_str) if weight_max_str else 0
            water_max_str = self._detectors.get("water", {}).get("max", 0)
            water_max = int(water_max_str) if weight_max_str else 0

            # 计算分数
            score = (wg_weight * weight_value / weight_max) + (wg_water * water_value / water_max)

            # 根据分数确定 level，并返回对应的 out 或 subout
            for _, _, s_score in sorted(self._scores_config, key=lambda x: x[2], reverse=True):
                if score >= s_score:
                    # 找到对应的 out/subout
                    for out, subout, score_val in self._scores_config:
                        if score_val == s_score:
                            print(f"命中 score 规则，分数为 {score}，匹配值为 {s_score}")
                            return self._get_channel_from_level({"out": out, "subout": subout})


        # 3. 如果 scores 为 disable，则使用权重为100的检测器
        else:
            dominant_detector_name = None
            for name, detector in self._detectors.items():
                if detector.get("wg") == "100":
                    dominant_detector_name = name
                    break

            if dominant_detector_name:
                dominant_value = weight_value if dominant_detector_name == "weight" else water_value
                detector = self._detectors[dominant_detector_name]

                for level in detector["goodLevel"]:
                    if level["min"] <= dominant_value <= level["max"]:
                        print(f"命中 {dominant_detector_name} goodLevel 规则")
                        return self._get_channel_from_level(level)

        # 4. 如果所有规则都不匹配
        return None


class TemplateManager:
    """
    管理所有模板，并提供获取接口。
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._templates: Dict[str, Template] = {}
        self._load_all_templates()

    def _load_all_templates(self):
        """
        从配置文件中加载所有模板，并初始化为Template实例。
        """
        print("开始加载所有模板到内存...")
        templates_elements = self.config_manager.get_templates_elements()
        for template_id, element in templates_elements.items():
            self._templates[template_id] = Template(element)
        print(f"共加载 {len(self._templates)} 个模板。")

    def get_template(self, template_id: str) -> Template | None:
        """
        根据模板ID获取对应的模板实例。

        Args:
            template_id (str): 模板的唯一ID。

        Returns:
            Template | None: 如果找到模板，返回其实例；否则返回 None。
        """
        return self._templates.get(template_id)


# --- 示例用法 ---
if __name__ == "__main__":
    # 创建模拟配置文件
    xml_content = """<?xml version="1.0" encoding="utf-8" ?>
<system>
    <config>
        <curtemplateId>1</curtemplateId>
        <weightOffset>0</weightOffset>
        <waterOffset>4</waterOffset>
    </config>
    <templates>
        <template id="1" name="WaterFirst">
            <scores enable="1">
                <score out="8" subout="9">80</score>
                <score out="10" subout="11">60</score>
                <score out="12" subout="13">40</score>
            </scores>
            <detectors>
                <weight wg="50">
                    <badLevel>
                        <level out="1">
                            <min>0</min>
                            <max>500</max>
                        </level>
                    </badLevel>
                    <goodLevel>
                        <level out="9" subout="10">
                            <min>501</min>
                            <max>799</max>
                        </level>
                    </goodLevel>
                </weight>
                <water wg="50">
                    <badLevel>
                        <level out="2">
                            <min>-10</min>
                            <max>20</max>
                        </level>
                    </badLevel>
                    <goodLevel>
                        <level out="7" subout="8">
                            <min>21</min>
                            <max>59</max>
                        </level>
                    </goodLevel>
                </water>
            </detectors>
        </template>
        <template id="2" name="WeightOnly">
            <scores enable="0"/>
            <detectors>
                <weight wg="100">
                    <badLevel>
                        <level out="1">
                            <min>0</min>
                            <max>100</max>
                        </level>
                    </badLevel>
                    <goodLevel>
                        <level out="14" subout="15">
                            <min>101</min>
                            <max>200</max>
                        </level>
                    </goodLevel>
                </weight>
                <water wg="0">
                    <badLevel/>
                    <goodLevel/>
                </water>
            </detectors>
        </template>
    </templates>
</system>
"""
    file_name = "config_updated.xml"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(xml_content)

    # 步骤1: 加载配置文件
    config_tool = ConfigManager(file_name)
    if config_tool.load_config():

        # 步骤2: 初始化 TemplateManager，它会加载所有模板到内存
        template_manager = TemplateManager(config_tool)

        # 步骤3: 获取当前模板ID
        current_template_id = config_tool.get_config_value('config/curtemplateId')

        # 步骤4: 根据ID获取模板实例，并进行筛选
        print("\n--- 使用模板ID 1 进行筛选 ---")
        template1 = template_manager.get_template(current_template_id)
        if template1:
            # 假设 wg_weight=50, wg_water=50
            # weight_max = 799, water_max = 59
            # score = 50 * (600/799) + 50 * (40/59) = 37.5 + 33.89 = 71.39
            # 71.39 >= 60，小于80，应该匹配 score=60 的通道
            channel = template1.get_channel(weight_value=600, water_value=40)
            print(f"使用模板 '{current_template_id}' 筛选出的通道: {channel}")

        print("\n--- 使用模板ID 2 进行筛选（Scores Disable）---")
        template2 = template_manager.get_template("2")
        if template2:
            # 此时只看 weight，wg=100
            # 2. 如果 scores 为 disable，则必然有一项检测器wg设为100，根据该检测器level确定out和subout
            channel = template2.get_channel(weight_value=150, water_value=0)
            print(f"使用模板 '2' 筛选出的通道: {channel}")