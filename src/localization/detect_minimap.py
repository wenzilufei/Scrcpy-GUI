import cv2
import numpy as np
import os

BASE_WIDTH = 1920
BASE_HEIGHT = 840


def calculate_scale_factor(image_width: int, image_height: int) -> float:
    """
    计算相对于基准分辨率的缩放因子

    Args:
        image_width: 当前图片宽度
        image_height: 当前图片高度

    Returns:
        缩放因子 (基准尺寸/当前尺寸)
    """
    scale_x = BASE_WIDTH / image_width
    scale_y = BASE_HEIGHT / image_height
    return (scale_x + scale_y) / 2


def calculate_content_score(img, center_x, center_y, radius) -> float:
    """
    计算圆形区域内是否像小地图（基于内容特征）

    Args:
        img: 原始图像
        center_x: 圆心X坐标
        center_y: 圆心Y坐标
        radius: 半径

    Returns:
        内容相似度得分 (0-100)
    """
    height, width = img.shape[:2]
    
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask, (center_x, center_y), radius, 255, -1)
    
    gray_region = cv2.cvtColor(cv2.bitwise_and(img, img, mask=mask), cv2.COLOR_BGR2GRAY)
    
    edges = cv2.Canny(gray_region, 50, 150)
    edge_density = np.sum(edges > 0) / (np.pi * radius * radius) * 100
    
    mean_val = cv2.mean(gray_region, mask=mask)[0]
    std_val = cv2.meanStdDev(gray_region, mask=mask)[1][0][0]
    
    hsv = cv2.cvtColor(cv2.bitwise_and(img, img, mask=mask), cv2.COLOR_BGR2HSV)
    saturation_mean = cv2.mean(hsv[:, :, 1], mask=mask)[0]
    
    score = 0
    if 80 < edge_density < 200:
        score += 30
    elif 50 < edge_density < 250:
        score += 20
    
    if 40 < mean_val < 180:
        score += 20
    
    if std_val > 30:
        score += 20
    
    if saturation_mean < 80:
        score += 15
    
    return min(score, 100)


def detect_minimap_adaptive(image_path: str) -> dict:
    """
    自适应缩放的小地图检测 - 支持不同分辨率图片

    Args:
        image_path: 图片路径

    Returns:
        包含小地图位置信息的字典
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"error": "无法读取图片"}

    height, width = img.shape[:2]
    
    scale_factor = calculate_scale_factor(width, height)
    
    base_params = {
        "dp": 1.2,
        "minDist": 100,
        "param1": 50,
        "param2": 40,
        "minRadius": 90,
        "maxRadius": 160
    }
    
    scaled_params = {
        "dp": base_params["dp"],
        "minDist": max(int(base_params["minDist"] / scale_factor), 50),
        "param1": base_params["param1"],
        "param2": base_params["param2"],
        "minRadius": max(int(base_params["minRadius"] / scale_factor), 50),
        "maxRadius": min(int(base_params["maxRadius"] / scale_factor), 200)
    }
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=scaled_params["dp"],
        minDist=scaled_params["minDist"],
        param1=scaled_params["param1"],
        param2=scaled_params["param2"],
        minRadius=scaled_params["minRadius"],
        maxRadius=scaled_params["maxRadius"]
    )
    
    result = {
        "image_size": {"width": width, "height": height},
        "base_size": {"width": BASE_WIDTH, "height": BASE_HEIGHT},
        "scale_factor": round(scale_factor, 3),
        "scaled_params": scaled_params,
        "circles_found": 0,
        "candidates": [],
        "minimap": None
    }
    
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        result["circles_found"] = len(circles)
        
        candidates = []
        
        for (x, y, r) in circles:
            x_ratio = x / width
            y_ratio = y / height
            
            region_threshold_x = 0.35
            region_threshold_y = 0.45
            
            if x_ratio < region_threshold_x and y_ratio < region_threshold_y:
                content_score = calculate_content_score(img, x, y, r)
                position_score = 100 - (x_ratio * 100 + y_ratio * 50)
                size_score = min(r / (scaled_params["maxRadius"] * 0.9) * 100, 100)
                
                final_score = (
                    content_score * 0.4 +
                    position_score * 0.3 +
                    size_score * 0.3
                )
                
                candidates.append({
                    "center_x": int(x),
                    "center_y": int(y),
                    "radius": int(r),
                    "content_score": content_score,
                    "position_score": position_score,
                    "size_score": size_score,
                    "final_score": final_score
                })
        
        candidates.sort(key=lambda c: c["final_score"], reverse=True)
        
        unique_candidates = []
        seen_centers = set()
        
        for cand in candidates:
            center_key = (cand["center_x"] // 20, cand["center_y"] // 20)
            
            if center_key not in seen_centers:
                seen_centers.add(center_key)
                unique_candidates.append(cand)
            elif len(unique_candidates) > 0:
                for existing in unique_candidates:
                    if (existing["center_x"] // 20, existing["center_y"] // 20) == center_key:
                        if cand["final_score"] > existing["final_score"]:
                            unique_candidates.remove(existing)
                            unique_candidates.append(cand)
                        break
        
        result["candidates"] = unique_candidates[:5] if unique_candidates else []
        
        if unique_candidates and unique_candidates[0]["final_score"] > 40:
            best = unique_candidates[0]
            
            result["minimap"] = {
                "center_x": best["center_x"],
                "center_y": best["center_y"],
                "radius": best["radius"],
                "left": best["center_x"] - best["radius"],
                "top": best["center_y"] - best["radius"],
                "right": best["center_x"] + best["radius"],
                "bottom": best["center_y"] + best["radius"],
                "width": 2 * best["radius"],
                "height": 2 * best["radius"],
                "confidence": round(best["final_score"], 1)
            }
    
    return result


def calculate_inscribed_rectangle(radius: int) -> dict:
    """
    计算圆内最大内接矩形的四个顶点坐标

    Args:
        radius: 圆的半径

    Returns:
        内接矩形的四个顶点坐标
    """
    side = int(radius * np.sqrt(2))
    half_side = side // 2
    
    return {
        "width": side,
        "height": side,
        "top_left": (-half_side, -half_side),
        "top_right": (half_side, -half_side),
        "bottom_right": (half_side, half_side),
        "bottom_left": (-half_side, half_side)
    }


if __name__ == "__main__":
    screenshots_dir = r"C:\Users\Administrator\Desktop\Scrcpy\screenshots"
    test_images = [
        "screenshot_20260416_103933.png",
        "screenshot_20260416_123024.png",
        "screenshot_20260416_123124.png"
    ]
    
    print("=" * 90)
    print("🎯 自适应缩放小地图检测系统 v3.0")
    print(f"   基准分辨率：{BASE_WIDTH} × {BASE_HEIGHT}")
    print("=" * 90)
    
    all_success = True
    
    for img_name in test_images:
        img_path = os.path.join(screenshots_dir, img_name)
        
        print(f"\n{'='*90}")
        print(f"📸 测试图片：{img_name}")
        print(f"{'='*90}")
        
        result = detect_minimap_adaptive(img_path)
        
        if "error" in result:
            print(f"   ❌ {result['error']}")
            all_success = False
            continue
        
        print(f"   📐 图片尺寸：{result['image_size']['width']} × {result['image_size']['height']}")
        print(f"   🔄 缩放因子：{result['scale_factor']} (相对基准 {BASE_WIDTH}×{BASE_HEIGHT})")
        print(f"   ⚙️ 自适应参数：")
        print(f"      minDist={result['scaled_params']['minDist']}, "
              f"minR={result['scaled_params']['minRadius']}, "
              f"maxR={result['scaled_params']['maxRadius']}")
        print(f"   🔍 检测到圆数：{result['circles_found']}")
        print(f"   🎯 有效候选数：{len(result['candidates'])}")
        
        if result["candidates"]:
            print(f"\n   🏆 Top 候选：")
            for i, cand in enumerate(result["candidates"][:3], 1):
                print(f"      #{i} ({cand['center_x']},{cand['center_y']}) r={cand['radius']} "
                      f"| 分:{cand['final_score']:.1f}")
        
        if result["minimap"]:
            m = result["minimap"]
            print(f"\n   ✅ 成功检测！置信度：{m['confidence']}%")
            print(f"   📍 圆心：({m['center_x']}, {m['center_y']}) | 半径：{m['radius']}px")
            print(f"   📐 边界框：({m['left']}, {m['top']}) → ({m['right']}, {m['bottom']})")
            
            inscribed = calculate_inscribed_rectangle(m['radius'])
            abs_rect = {
                "top_left": (m['center_x'] + inscribed['top_left'][0], 
                            m['center_y'] + inscribed['top_left'][1]),
                "top_right": (m['center_x'] + inscribed['top_right'][0], 
                             m['center_y'] + inscribed['top_right'][1]),
                "bottom_right": (m['center_x'] + inscribed['bottom_right'][0], 
                                m['center_y'] + inscribed['bottom_right'][1]),
                "bottom_left": (m['center_x'] + inscribed['bottom_left'][0], 
                               m['center_y'] + inscribed['bottom_left'][1])
            }
            
            print(f"\n   🔲 圆内最大内接矩形：")
            print(f"      尺寸：{inscribed['width']} × {inscribed['height']} px")
            print(f"      四个顶点（绝对坐标）：")
            print(f"         左上：{abs_rect['top_left']}")
            print(f"         右上：{abs_rect['top_right']}")
            print(f"         右下：{abs_rect['bottom_right']}")
            print(f"         左下：{abs_rect['bottom_left']}")
            
            img = cv2.imread(img_path)
            cv2.circle(img, (m['center_x'], m['center_y']), m['radius'], (0, 255, 0), 3)
            cv2.rectangle(img, (m['left'], m['top']), (m['right'], m['bottom']), (255, 0, 0), 2)
            
            pts = np.array([
                abs_rect['top_left'],
                abs_rect['top_right'],
                abs_rect['bottom_right'],
                abs_rect['bottom_left']
            ], np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(img, [pts], True, (0, 255, 255), 2)
            
            label = f"MINIMAP {m['confidence']}%"
            cv2.putText(img, label, (m['left'], m['top'] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            output_name = f"adaptive_{img_name}"
            output_path = os.path.join(screenshots_dir, output_name)
            cv2.imwrite(output_path, img)
            print(f"   💾 已保存：{output_name}")
        else:
            print(f"\n   ❌ 未检测到小地图")
            all_success = False
    
    print("\n" + "=" * 90)
    if all_success:
        print("✅ 所有图片检测成功！自适应算法有效！")
    else:
        print("⚠️ 部分失败，需继续优化")
    print("=" * 90)
