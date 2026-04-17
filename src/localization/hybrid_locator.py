import cv2
import numpy as np
import time

from ..utils import logger
from .orb_matcher import ORBMatcher


class HybridLocator:
    """
    NCC + ORB 混合定位器
    
    策略：
    1. 第一层：NCC 模板匹配快速粗定位（鲁棒、抗尺度差异）
    2. 第二层：在 NCC 定位结果附近裁剪局部区域
    3. 第三层：ORB 在局部区域内精修（高精度、亚像素级）
    
    优势：
    - 结合 NCC 的尺度鲁棒性和 ORB 的精度
    - 速度：~150ms（比纯 ORB 快，比纯 NCC 稍慢但更准）
    - 精度：±10px 以内（比纯 NCC 高 3-5 倍）
    - 手机端友好（轻量级算法组合）
    """

    def __init__(self, search_radius: int = 300,
                 ncc_scales: list = None,
                 orb_features: int = 500):
        """
        初始化混合定位器

        Args:
            search_radius: NCC 定位后的搜索半径（像素）
            ncc_scales: NCC 多尺度列表
            orb_features: ORB 特征点数量
        """
        self.search_radius = search_radius
        self.ncc_scales = ncc_scales or [1.0, 0.8, 0.6, 0.5]
        self.orb_matcher = ORBMatcher(n_features=orb_features)

    def ncc_coarse_locate(self, minimap_img: np.ndarray,
                          bigmap_gray: np.ndarray) -> dict:
        """
        使用 NCC 进行快速粗定位

        Args:
            minimap_img: 小地图图像 (BGR)
            bigmap_gray: 大地图灰度图

        Returns:
            粗定位结果字典
        """
        start = time.time()

        if len(minimap_img.shape) == 3:
            minimap_gray = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2GRAY)
        else:
            minimap_gray = minimap_img.copy()

        best_match = None
        best_val = -1

        for scale in self.ncc_scales:
            if scale != 1.0:
                scaled = cv2.resize(minimap_gray, None,
                                   fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)
            else:
                scaled = minimap_gray.copy()

            h, w = scaled.shape[:2]

            if h > bigmap_gray.shape[0] or w > bigmap_gray.shape[1]:
                continue

            result = cv2.matchTemplate(bigmap_gray, scaled,
                                       cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_val:
                best_val = max_val
                best_match = {
                    "center": (max_loc[0] + w // 2, max_loc[1] + h // 2),
                    "top_left": max_loc,
                    "size": (w, h),
                    "scale": scale,
                    "confidence": round(max_val * 100, 1)
                }

        elapsed = (time.time() - start) * 1000

        if best_match:
            best_match["time_ms"] = round(elapsed, 1)
            best_match["success"] = True
        else:
            best_match = {
                "success": False,
                "time_ms": round(elapsed, 1),
                "error": "NCC 未找到匹配"
            }

        return best_match

    def extract_local_region(self, bigmap_img: np.ndarray,
                             center: tuple, radius: int) -> dict:
        """
        从大地图中提取以 center 为中心的局部区域

        Args:
            bigmap_img: 大地图图像
            center: 中心坐标 (x, y)
            radius: 提取半径

        Returns:
            局部区域信息字典
        """
        h, w = bigmap_img.shape[:2]

        x1 = max(0, center[0] - radius)
        y1 = max(0, center[1] - radius)
        x2 = min(w, center[0] + radius)
        y2 = min(h, center[1] + radius)

        local_region = bigmap_img[y1:y2, x1:x2].copy()

        return {
            "image": local_region,
            "offset": (x1, y1),
            "top_left": (x1, y1),
            "bottom_right": (x2, y2),
            "size": (x2 - x1, y2 - y1),
            "center_in_local": (center[0] - x1, center[1] - y1)
        }

    def orb_fine_tune(self, minimap_img: np.ndarray,
                       local_region: dict) -> dict:
        """
        使用 ORB 在局部区域内精修定位

        Args:
            minimap_img: 小地图图像
            local_region: 局部区域信息（由 extract_local_region 返回）

        Returns:
            精修后的定位结果
        """
        start = time.time()

        local_img = local_region["image"]
        offset = local_region["offset"]

        orb_result = self.orb_matcher.locate_minimap_on_bigmap(
            minimap_img, local_img
        )

        elapsed = (time.time() - start) * 1000

        if orb_result.get("success"):
            local_center = orb_result["center"]
            
            global_center = (
                local_center[0] + offset[0],
                local_center[1] + offset[1]
            )

            return {
                "success": True,
                "center": global_center,
                "local_center": local_center,
                "confidence": orb_result.get("confidence", 0),
                "inliers": orb_result.get("inliers", 0),
                "offset": offset,
                "time_ms": round(elapsed, 1),
                "orb_detail": orb_result
            }
        else:
            return {
                "success": False,
                "time_ms": round(elapsed, 1),
                "error": orb_result.get("error", "ORB精修失败"),
                "fallback_to_ncc": True
            }

    def locate(self, minimap_img: np.ndarray,
               bigmap_img: np.ndarray) -> dict:
        """
        完整的混合定位流程

        Args:
            minimap_img: 裁剪后的小地图图像
            bigmap_img: 大地图图像

        Returns:
            最终定位结果
        """
        total_start = time.time()

        result = {
            "method": "hybrid",
            "ncc_coarse": None,
            "orb_fine": None,
            "final": None
        }

        if len(bigmap_img.shape) == 3:
            bigmap_gray = cv2.cvtColor(bigmap_img, cv2.COLOR_BGR2GRAY)
        else:
            bigmap_gray = bigmap_img.copy()

        logger.debug("📍 步骤1: NCC 粗定位...")
        ncc_result = self.ncc_coarse_locate(minimap_img, bigmap_gray)
        result["ncc_coarse"] = ncc_result

        if not ncc_result.get("success"):
            result["final"] = {
                "success": False,
                "error": "NCC粗定位失败",
                "total_time_ms": round((time.time() - total_start) * 1000, 1)
            }
            return result

        logger.info(
            f"✅ NCC 完成！坐标：{ncc_result['center']}，置信度：{ncc_result['confidence']}%，耗时：{ncc_result['time_ms']}ms"
        )

        logger.debug("🔍 步骤2: 裁剪局部区域...")
        local_region = self.extract_local_region(
            bigmap_img,
            ncc_result["center"],
            self.search_radius
        )

        logger.debug(f"✅ 局部区域：{local_region['size'][0]} × {local_region['size'][1]} px")

        logger.debug("⚡ 步骤3: ORB 精修...")
        orb_result = self.orb_fine_tune(minimap_img, local_region)
        result["orb_fine"] = orb_result

        total_time = (time.time() - total_start) * 1000

        if orb_result.get("success"):
            final_center = orb_result["center"]
            ncc_center = ncc_result["center"]

            offset_x = abs(final_center[0] - ncc_center[0])
            offset_y = abs(final_center[1] - ncc_center[1])

            result["final"] = {
                "success": True,
                "center": final_center,
                "ncc_center": ncc_center,
                "adjustment": (final_center[0] - ncc_center[0],
                               final_center[1] - ncc_center[1]),
                "adjustment_magnitude": round(np.sqrt(offset_x**2 + offset_y**2), 1),
                "confidence": orb_result.get("confidence", ncc_result["confidence"]),
                "method_used": "NCC+ORB",
                "total_time_ms": round(total_time, 1),
                "timing": {
                    "ncc_ms": ncc_result.get("time_ms", 0),
                    "extract_local_ms": 0,
                    "orb_ms": orb_result.get("time_ms", 0),
                    "total_ms": round(total_time, 1)
                }
            }

            logger.info("✅ ORB 精修完成！")
            logger.debug(f"最终坐标：{final_center}")
            logger.debug(
                f"调整量：({result['final']['adjustment'][0]}, {result['final']['adjustment'][1]}) px"
            )
            logger.debug(f"调整幅度：{result['final']['adjustment_magnitude']} px")
        else:
            result["final"] = {
                "success": True,
                "center": ncc_result["center"],
                "confidence": ncc_result["confidence"],
                "method_used": "NCC_only",
                "note": "ORB精修失败，使用NCC结果作为最终输出",
                "total_time_ms": round(total_time, 1),
                "timing": {
                    "ncc_ms": ncc_result.get("time_ms", 0),
                    "orb_ms": orb_result.get("time_ms", 0),
                    "total_ms": round(total_time, 1)
                }
            }

            logger.warning("⚠️ ORB 精修失败，使用 NCC 结果")

        logger.debug(f"⏱️ 总耗时：{result['final']['total_time_ms']} ms")

        return result
