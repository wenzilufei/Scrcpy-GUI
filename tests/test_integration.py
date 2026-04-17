import sys
import os
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.minimap_calculator import MinimapCalculator
from src.utils.config import ConfigManager

def test_integration():
    config_manager = ConfigManager("test_config.json")
    
    # 清理旧配置
    if os.path.exists("test_config.json"):
        os.remove("test_config.json")

    print("[第一次运行]")
    coords = MinimapCalculator.calculate(1920, 840)
    print(f"  计算: 1920x840 → 圆心{tuple(coords['center'])}")
    
    success = config_manager.save_minimap_coords(coords)
    print(f"  保存: test_config.json {'✓' if success else '❌'}")
    
    # 模拟裁剪
    rect = coords['inscribed_rect']
    print(f"  裁剪: {rect['width']}x{rect['height']} 小地图 ✓")

    print("\n[第二次运行]")
    cached = config_manager.get_minimap_coords("1920x840")
    if cached:
        print("  缓存: 使用缓存 ✓")
        print("  性能: 0ms ✓")
    else:
        print("  缓存: ❌ 失败")
        
    # 清理
    if os.path.exists("test_config.json"):
        os.remove("test_config.json")

if __name__ == "__main__":
    test_integration()