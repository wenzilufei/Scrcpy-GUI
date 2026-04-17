"""
最终优化版 NCC 匹配器 - 平衡速度与精度的最佳方案

核心策略：
1. 超快速粗定位（25%降采样）
2. 智能自适应 ROI
3. 单尺度精确匹配
4. 预期：<15ms 且精度无损
"""

import cv2
import numpy as np
import time


class UltimateFastNCC:
    """
    终极速 NCC 匹配器 - 自适应版本
    
    核心改进：
    - 智能自适应降采样（根据小地图大小动态调整）
    - 大小地图(>120px) → 25%降采样（极速）
    - 中等小地图(80-120px) → 50%降采样（平衡）
    - 小小地图(<80px) → 不降采样（保精度）
    
    目标：所有分辨率都能准确定位
    """

    def __init__(self,
                 roi_base_radius: int = 350,
                 confidence_threshold: float = 0.75):
        """初始化终极匹配器"""
        self.roi_base_radius = roi_base_radius
        self.confidence_threshold = confidence_threshold
        
        self._bigmap_gray = None
        self._prepared = False

    def _get_adaptive_scale(self, minimap_size: tuple) -> float:
        """
        根据小地图大小自适应选择降采样率
        
        Args:
            minimap_size: (宽, 高)
            
        Returns:
            降采样比例 (0-1)
        """
        min_dim = min(minimap_size)
        
        if min_dim >= 120:
            return 0.25  # 大图：激进降采样，追求速度
        elif min_dim >= 80:
            return 0.50  # 中等：平衡速度和精度
        else:
            return 1.0   # 小图：不降采样，保证精度

    def prepare_bigmap(self, bigmap_img: np.ndarray):
        """预处理大地图"""
        if len(bigmap_img.shape) == 3:
            self._bigmap_gray = cv2.cvtColor(bigmap_img, cv2.COLOR_BGR2GRAY)
        else:
            self._bigmap_gray = bigmap_img.copy()
        
        self._prepared = True

    def match(self, minimap_img: np.ndarray) -> dict:
        """执行自适应快速匹配"""
        start_total = time.time()
        
        if not self._prepared:
            return {"success": False, "error": "大地图未初始化", "time_ms": 0}
        
        if len(minimap_img.shape) == 3:
            minimap_gray = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2GRAY)
        else:
            minimap_gray = minimap_img.copy()

        # ========== 自适应降采样策略 ==========
        adaptive_scale = self._get_adaptive_scale((minimap_gray.shape[1], minimap_gray.shape[0]))
        
        t_coarse = time.time()
        
        if adaptive_scale < 1.0:
            coarse_bigmap = cv2.resize(
                self._bigmap_gray, None,
                fx=adaptive_scale, fy=adaptive_scale,
                interpolation=cv2.INTER_AREA
            )
            coarse_minimap = cv2.resize(
                minimap_gray, None,
                fx=adaptive_scale, fy=adaptive_scale,
                interpolation=cv2.INTER_AREA
            )
            
            result_coarse = cv2.matchTemplate(
                coarse_bigmap, coarse_minimap,
                cv2.TM_SQDIFF_NORMED
            )
            min_val_coarse, _, min_loc_coarse, _ = cv2.minMaxLoc(result_coarse)
            
            center_x = int((min_loc_coarse[0] + coarse_minimap.shape[1] // 2) / adaptive_scale)
            center_y = int((min_loc_coarse[1] + coarse_minimap.shape[0] // 2) / adaptive_scale)
        else:
            result_coarse = cv2.matchTemplate(
                self._bigmap_gray, minimap_gray,
                cv2.TM_SQDIFF_NORMED
            )
            min_val_coarse, _, min_loc_coarse, _ = cv2.minMaxLoc(result_coarse)
            
            center_x = min_loc_coarse[0] + minimap_gray.shape[1] // 2
            center_y = min_loc_coarse[1] + minimap_gray.shape[0] // 2
        
        coarse_confidence = 1 - min_val_coarse
        coarse_time = (time.time() - t_coarse) * 1000

        # ========== 第二层：智能ROI精修 ==========
        t_fine = time.time()
        
        if coarse_confidence > 0.85:
            roi_radius = int(self.roi_base_radius * 0.8)
        elif coarse_confidence > 0.70:
            roi_radius = self.roi_base_radius
        else:
            roi_radius = int(self.roi_base_radius * 1.3)

        h_big, w_big = self._bigmap_gray.shape[:2]
        x1 = max(0, center_x - roi_radius)
        y1 = max(0, center_y - roi_radius)
        x2 = min(w_big, center_x + roi_radius)
        y2 = min(h_big, center_y + roi_radius)
        
        roi = self._bigmap_gray[y1:y2, x1:x2]
        
        result_fine = cv2.matchTemplate(roi, minimap_gray, cv2.TM_SQDIFF_NORMED)
        min_val_fine, _, min_loc_fine, _ = cv2.minMaxLoc(result_fine)
        
        fine_time = (time.time() - t_fine) * 1000
        
        final_x = x1 + min_loc_fine[0] + minimap_gray.shape[1] // 2
        final_y = y1 + min_loc_fine[1] + minimap_gray.shape[0] // 2
        confidence = (1 - min_val_fine) * 100
        
        total_time = (time.time() - start_total) * 1000
        
        return {
            "center": (final_x, final_y),
            "confidence": round(confidence, 1),
            "coarse_confidence": round(coarse_confidence * 100, 1),
            "coarse_time_ms": round(coarse_time, 1),
            "fine_time_ms": round(fine_time, 1),
            "total_time_ms": round(total_time, 1),
            "roi_radius": roi_radius,
            "adaptive_scale": adaptive_scale,
            "success": True,
            "method": "UltimateFastNCC-Adaptive"
        }


def extract_minimap_region(screenshot_path: str) -> dict:
    """从截图中提取小地图区域"""
    from .detect_minimap import detect_minimap_adaptive, calculate_inscribed_rectangle
    
    img = cv2.imread(screenshot_path)
    if img is None:
        return {"error": "无法读取截图"}
    
    result = detect_minimap_adaptive(screenshot_path)
    
    if "error" in result or not result.get("minimap"):
        return {"error": "未检测到小地图", "detail": result}

    m = result["minimap"]
    inscribed = calculate_inscribed_rectangle(m['radius'])

    abs_rect = {
        "top_left": (m['center_x'] + inscribed['top_left'][0],
                     m['center_y'] + inscribed['top_left'][1]),
        "bottom_right": (m['center_x'] + inscribed['bottom_right'][0],
                         m['center_y'] + inscribed['bottom_right'][1])
    }

    x1, y1 = abs_rect['top_left']
    x2, y2 = abs_rect['bottom_right']

    return {
        "minimap_image": img[y1:y2, x1:x2].copy(),
        "position": {
            "abs_rect": abs_rect,
            "inscribed_size": (inscribed['width'], inscribed['height']),
            "circle_center": (m['center_x'], m['center_y']),
            "circle_radius": m['radius']
        }
    }


if __name__ == "__main__":
    import os
    
    base_dir = r"C:\Users\Administrator\Desktop\Scrcpy"
    screenshot_path = os.path.join(base_dir, "screenshots", "screenshot_20260416_103933.png")
    bigmap_path = os.path.join(base_dir, "daditu", "0.png")

    print("=" * 90)
    print("🚀 终极速 NCC 测试 - 平衡速度与精度")
    print("=" * 90)

    print("\n📸 加载图片...")
    extract_result = extract_minimap_region(screenshot_path)
    
    if "error" in extract_result:
        print(f"❌ {extract_result['error']}")
        exit(1)

    minimap_img = extract_result["minimap_image"]
    big_map = cv2.imread(bigmap_path)

    print(f"   ✅ 小地图尺寸：{minimap_img.shape[1]} × {minimap_img.shape[0]}")
    print(f"   ✅ 大地图尺寸：{big_map.shape[1]} × {big_map.shape[0]}")

    print("\n🔧 初始化终极匹配器...")
    matcher = UltimateFastNCC(
        coarse_scale=0.25,
        roi_base_radius=350,
        confidence_threshold=0.75
    )
    matcher.prepare_bigmap(big_map)
    print("   ✅ 初始化完成")

    iterations = 10
    print(f"\n{'='*90}")
    print(f"📊 性能测试 ({iterations} 轮)")
    print(f"{'='*90}")

    results = []
    
    for i in range(iterations):
        result = matcher.match(minimap_img)
        results.append(result)
        
        total = result.get('total_time_ms', 0)
        coarse = result.get('coarse_time_ms', 0)
        fine = result.get('fine_time_ms', 0)
        conf = result.get('confidence', 'N/A')
        center = result.get('center', 'N/A')
        roi = result.get('roi_radius', 'N/A')
        
        print(f"第 {i+1:>2}/{iterations} 轮 | "
              f"总计:{total:>5.1f}ms (粗:{coarse:>4.1f} + 精:{fine:>5.1f}) | "
              f"置信度:{conf:>5}% | {center} | ROI:{roi}")

    # 统计分析
    times = [r['total_time_ms'] for r in results]
    coarse_times = [r['coarse_time_ms'] for r in results]
    fine_times = [r['fine_time_ms'] for r in results]
    confidences = [r['confidence'] for r in results]
    
    avg_total = sum(times) / len(times)
    avg_coarse = sum(coarse_times) / len(coarse_times)
    avg_fine = sum(fine_times) / len(fine_times)
    avg_conf = sum(confidences) / len(confidences)
    
    min_time = min(times)
    max_time = max(times)
    
    print(f"\n{'='*90}")
    print("📈 性能统计")
    print(f"{'='*90}")
    
    print(f"""
┌─────────────────────────────────────────────────────────────┐
│ 🎯 终极速 NCC 性能报告                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ⏱️  时间分析：                                             │
│      ├─ 平均总耗时：{avg_total:>6.2f} ms                               │
│      │   ├─ 粗定位：{avg_coarse:>6.2f} ms ({avg_coarse/avg_total*100:>5.1f}%)               │
│      │   └─ 精修：{avg_fine:>6.2f} ms ({avg_fine/avg_total*100:>5.1f}%)                   │
│      ├─ 最快：{min_time:>6.2f} ms                                         │
│      └─ 最慢：{max_time:>6.2f} ms                                         │
│                                                             │
│   🎯 精度指标：                                               │
│      └─ 平均置信度：{avg_conf:.1f}%                                    │
│                                                             │
│   🚀 性能评估：                                               │
│      └─ 预估 FPS：{1000/avg_total:.1f} 帧/秒                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
""")

    # 对比基准
    baseline_ms = 22.4  # 基准FastNCC的平均耗时
    speedup = baseline_ms / avg_total if avg_total > 0 else 0
    
    print(f"📊 与基准对比：")
    print(f"   基准 FastNCC：{baseline_ms:.1f} ms")
    print(f"   终极速 NCC ：{avg_total:.1f} ms")
    print(f"   提速效果：{speedup:.2f}x {'🚀' if speedup > 1.2 else '⚡' if speedup > 1.0 else '🐌'}")
    
    if avg_total < 15:
        print("\n🏆🏆🏆 极致极速！完美满足实时需求！")
    elif avg_total < 20:
        print("\n⚡⚡ 非常快速！完全满足实时应用！")
    elif avg_total < 30:
        print("\n✅ 快速！基本满足实时需求！")
    else:
        print("\n🐌 还可以继续优化...")

    # 验证坐标一致性
    centers = [r['center'] for r in results]
    unique_centers = set(centers)
    
    print(f"\n📍 坐标稳定性：")
    print(f"   所有轮次坐标：{unique_centers}")
    
    if len(unique_centers) == 1:
        print(f"   ✅ 完全稳定！（所有轮次坐标一致）")
    else:
        print(f"   ⚠️ 存在波动（{len(unique_centers)}个不同坐标）")
