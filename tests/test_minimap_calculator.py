import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.minimap_calculator import MinimapCalculator

def test_minimap_calculator():
    print("分辨率 1920x840:")
    result1 = MinimapCalculator.calculate(1920, 840)
    print(f"  圆心: {result1['center']} ✓")
    print(f"  半径: {result1['radius']}px ✓")
    print(f"  内接矩形: {result1['inscribed_rect']['top_left']} → {result1['inscribed_rect']['bottom_right']} ✓")

    print("\n分辨率 1080x472:")
    result2 = MinimapCalculator.calculate(1080, 472)
    print(f"  圆心: {result2['center']} ✓")
    print(f"  半径: {result2['radius']}px ✓")
    print(f"  内接矩形: {result2['inscribed_rect']['top_left']} → {result2['inscribed_rect']['bottom_right']} ✓")

if __name__ == "__main__":
    test_minimap_calculator()