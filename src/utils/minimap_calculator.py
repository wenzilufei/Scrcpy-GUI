"""
小地图坐标计算工具
基于基准参数按比例计算任意分辨率下的小地图位置
"""

import math
from typing import Dict


# 基准参数（已验证：1920x840 分辨率下的小地图位置）
BASE_WIDTH = 1920
BASE_HEIGHT = 840
BASE_CENTER_X = 244
BASE_CENTER_Y = 166
BASE_RADIUS = 113


class MinimapCalculator:
    """小地图坐标计算器"""

    @staticmethod
    def calculate(image_width: int, image_height: int) -> Dict:
        """
        根据截图分辨率计算小地图位置

        Args:
            image_width: 截图宽度
            image_height: 截图高度

        Returns:
            包含小地图位置信息的字典:
            {
                "resolution_key": "1920x840",
                "center": [150, 150],
                "radius": 120,
                "inscribed_rect": {
                    "top_left": [65, 65],
                    "bottom_right": [235, 235],
                    "width": 170,
                    "height": 170
                }
            }
        """
        # 计算相对比例
        x_ratio = BASE_CENTER_X / BASE_WIDTH
        y_ratio = BASE_CENTER_Y / BASE_HEIGHT
        radius_ratio = BASE_RADIUS / BASE_WIDTH

        # 应用到当前分辨率
        center_x = int(image_width * x_ratio)
        center_y = int(image_height * y_ratio)
        radius = int(image_width * radius_ratio)

        # 计算内接矩形（MSS 采集区域）
        rect_side = int(radius * math.sqrt(2))
        half_side = rect_side // 2

        return {
            "resolution_key": f"{image_width}x{image_height}",
            "center": [center_x, center_y],
            "radius": radius,
            "inscribed_rect": {
                "top_left": [center_x - half_side, center_y - half_side],
                "bottom_right": [center_x + half_side, center_y + half_side],
                "width": rect_side,
                "height": rect_side
            }
        }

    @staticmethod
    def get_base_params() -> Dict:
        """
        获取基准参数

        Returns:
            基准参数字典
        """
        return {
            "width": BASE_WIDTH,
            "height": BASE_HEIGHT,
            "center_x": BASE_CENTER_X,
            "center_y": BASE_CENTER_Y,
            "radius": BASE_RADIUS
        }
