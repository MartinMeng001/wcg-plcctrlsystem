# data_manager.py

from typing import Any, Tuple

# 假设以下模块已存在于你的项目中
from .config_manager import ConfigManager
from .aligned_queue import AlignedQueue
from .template_manager import TemplateManager, Template


class DataManager:
    """
    一个用于管理配置、数据和模板筛选的中央数据管理类。
    """

    def __init__(self, config_file_path: str):
        """
        初始化数据管理器。

        Args:
            config_file_path (str): XML 配置文件的路径。
        """
        self.config_manager = ConfigManager(config_file_path)
        self.template_manager = None

        self.cur_template_id = None
        self.weight_offset = 0
        self.water_offset = 0

        self.weight_queue = {}
        self.water_queue = {}

        self._load_all_configs()

    def _load_all_configs(self):
        """
        从配置文件中加载所有配置和模板。
        """
        if self.config_manager.load_config():
            # 1. 从配置文件中获取当前模板ID和所有offset
            self.cur_template_id = self.config_manager.get_config_value('config/curtemplateId')

            weight_offset_str = self.config_manager.get_config_value('config/weightOffset')
            self.weight_offset = int(weight_offset_str) if weight_offset_str else 0

            water_offset_str = self.config_manager.get_config_value('config/waterOffset')
            self.water_offset = int(water_offset_str) if water_offset_str else 0

            print(f"配置文件参数加载成功：当前模板ID={self.cur_template_id}, "
                  f"weight_offset={self.weight_offset}, water_offset={self.water_offset}")

            # 2. 如果offset大于0，创建AlignedQueue队列
            # if self.weight_offset > 0:
            #     self.weight_queue = AlignedQueue(max_length=self.weight_offset + 10)
            # if self.water_offset > 0:
            #     self.water_queue = AlignedQueue(max_length=self.water_offset + 10)

            # 3. 初始化模板管理器
            self.template_manager = TemplateManager(self.config_manager)

    def set_value(self, line_id: str, value_name: str, value: Any, position: int) -> int | None:
        """
        设置 weight 或 water 的值。

        Args:
            value_name (str): 'weight' 或 'water'。
            value (Any): 要设置的值。
            position (int): 数据的位置。

        Returns:
            int | None: 如果成功筛选，返回通道号；否则返回 None。
        """
        if value_name == 'weight':
            offset = self.weight_offset
            if line_id not in self.weight_queue:
                self.weight_queue[line_id] = AlignedQueue(max_length=offset + 10)
            queue = self.weight_queue[line_id]
        elif value_name == 'water':
            offset = self.water_offset
            if line_id not in self.water_queue:
                self.water_queue[line_id] = AlignedQueue(max_length=offset + 10)
            queue = self.water_queue[line_id]
        else:
            print(f"错误：不支持的数据类型 '{value_name}'。")
            return None

        # 4. 当offset大于0时，将值存入AlignedQueue
        if offset > 0:
            if queue is None:
                print(f"错误：'{value_name}' 的队列未初始化。")
                return None

            queue.put(data=value, position=position)
            print(f"'{value_name}' 值 {value} 已存入队列，位置 {position}。")
            return None  # 队列操作，不返回通道号

        # 5. 当offset等于0时，进行筛选
        elif offset == 0:
            print(f"'{value_name}' 值 {value} 进行筛选，位置 {position}，模板 {self.cur_template_id}")
            # 获取当前模板
            current_template = self.template_manager.get_template(self.cur_template_id)
            if not current_template:
                print(f"错误：未找到ID为 '{self.cur_template_id}' 的模板。")
                return None

            # 获取另一个值
            if value_name == 'weight':
                water_value = self._get_offset_value(line_id, 'water', position)
                if water_value is None:
                    print(f"错误：未找到water_value position:{position}")
                    water_value = -100
                    # return None
                return current_template.get_channel(weight_value=int(value), water_value=int(water_value))

            elif value_name == 'water':
                weight_value = self._get_offset_value(line_id, 'weight', position)
                if weight_value is None: return None
                return current_template.get_channel(weight_value=int(weight_value), water_value=int(value))

    def _get_offset_value(self, line_id: str, value_name: str, current_position: int) -> Any | None:
        """
        获取队列中对应位置的值。
        """
        if value_name == 'weight':
            queue = self.weight_queue.get(line_id)
            offset = self.weight_offset
        else:  # 'water'
            queue = self.water_queue.get(line_id)
            offset = self.water_offset

        # 2. 如果队列不存在，直接返回 None
        if not queue:
            return None

        # 计算对齐位置
        alignment_position = current_position - offset

        # 从队列中获取对齐的值
        retrieved_item = queue.get_aligned(alignment_position)
        if retrieved_item:
            retrieved_value, _ = retrieved_item
            return retrieved_value
        else:
            # print(f"错误：未能在位置 {current_position} 找到与 '{value_name}' 对应的对齐数据。")
            return None

    def reload_config(self):
        """
        手动重新加载配置，并根据版本号决定是否更新。
        """
        if self._load_all_configs():
            print("配置更新成功。")
        else:
            print("配置已是最新版本。")

# --- 示例用法 ---
# if __name__ == "__main__":
#     # 创建一个模拟的配置文件，以供测试
#     xml_content = """<?xml version="1.0" encoding="utf-8" ?>
# <system>
#     <config>
#         <curtemplateId>1</curtemplateId>
#         <weightOffset>0</weightOffset>
#         <waterOffset>4</waterOffset>
#     </config>
#     <templates>
#         <template id="1" name="WaterFirst">
#             <scores enable="1">
#                 <score out="8" subout="9">80</score>
#                 <score out="10" subout="11">60</score>
#                 <score out="12" subout="13">40</score>
#             </scores>
#             <detectors>
#                 <weight wg="50">
#                     <badLevel>
#                         <level out="1">
#                             <min>0</min>
#                             <max>500</max>
#                         </level>
#                     </badLevel>
#                     <goodLevel>
#                         <level out="9" subout="10">
#                             <min>501</min>
#                             <max>799</max>
#                         </level>
#                     </goodLevel>
#                 </weight>
#                 <water wg="50">
#                     <badLevel>
#                         <level out="2">
#                             <min>-10</min>
#                             <max>20</max>
#                         </level>
#                     </badLevel>
#                     <goodLevel>
#                         <level out="7" subout="8">
#                             <min>21</min>
#                             <max>59</max>
#                         </level>
#                     </goodLevel>
#                 </water>
#             </detectors>
#         </template>
#     </templates>
# </system>
# """
#     file_name = "config.xml"
#     with open(file_name, "w", encoding="utf-8") as f:
#         f.write(xml_content)
#
#     # 实例化 DataManager
#     data_manager = DataManager(file_name)
#
#     print("\n--- 模拟数据处理流程 ---")
#
#     # 1. water 的 offset > 0，所以它的值会先存入队列
#     print("\n--- 步骤1: 传入water值 ---")
#     data_manager.set_value('water', value=40, position=104)
#     data_manager.set_value('water', value=45, position=105)
#     data_manager.set_value('water', value=50, position=106)
#     data_manager.set_value('water', value=55, position=107)
#
#     # 2. weight 的 offset = 0，传入时会触发筛选
#     print("\n--- 步骤2: 传入weight值，触发筛选 ---")
#     # 此时，weight 的位置为 107，其对应的 water 应该在位置 107 - 4 = 103
#     # 但是我们传入的 water 位置是 104，所以会跳过
#     # 接下来，weight 在位置 108，其对应的 water 在 104
#     channel = data_manager.set_value('weight', value=650, position=108)
#     if channel is not None:
#         print(f"\n筛选成功！得到的通道号为: {channel}")
#     else:
#         print("\n筛选失败。")