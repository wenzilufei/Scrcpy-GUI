"""
小地图定位模块

提供多种定位算法：
- detect_minimap: 基于霍夫圆检测的小地图位置识别
- orb_matcher: ORB 特征匹配器
- hybrid_locator: NCC + ORB 混合定位器
- ultimate_fast_ncc: 自适应快速 NCC 匹配器
"""

from .detect_minimap import detect_minimap_adaptive, calculate_inscribed_rectangle
from .orb_matcher import ORBMatcher
from .hybrid_locator import HybridLocator
from .ultimate_fast_ncc import UltimateFastNCC
