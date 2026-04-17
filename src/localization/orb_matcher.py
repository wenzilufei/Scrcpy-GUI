import cv2
import numpy as np
import time


class ORBMatcher:
    """
    ORB 特征匹配器 - 专为移动端优化的快速定位方案

    特点：
    - 速度极快（比NCC模板匹配快10倍+）
    - 支持旋转和尺度不变性
    - 内存占用低（适合手机端）
    - 精度高（RANSAC过滤误匹配）
    """

    def __init__(self, n_features: int = 1000):
        """
        初始化 ORB 匹配器

        Args:
            n_features: 提取的特征点数量（默认1000，提高以增强匹配能力）
        """
        self.orb = cv2.ORB_create(
            nfeatures=n_features,
            scaleFactor=1.2,
            nlevels=8,
            edgeThreshold=15,
            patchSize=31,
            fastThreshold=20
        )
        
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def extract_features(self, image: np.ndarray) -> tuple:
        """
        从图像中提取 ORB 特征点和描述子

        Args:
            image: 输入图像 (BGR格式)

        Returns:
            (keypoints, descriptors) 元组
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        keypoints, descriptors = self.orb.detectAndCompute(gray, None)
        
        return keypoints, descriptors

    def match_features(self, desc1: np.ndarray, desc2: np.ndarray,
                      ratio_thresh: float = 0.85,
                      min_matches: int = 10) -> list:
        """
        使用 BFMatcher 进行特征匹配，并应用 Lowe's ratio test

        Args:
            desc1: 第一组描述子（小地图）
            desc2: 第二组描述子（大地图）
            ratio_thresh: Lowe's ratio test 阈值（默认0.85，放宽以提高召回率）
            min_matches: 最少匹配点数

        Returns:
            优质匹配点列表
        """
        if desc1 is None or desc2 is None:
            return []
        
        if len(desc1) < min_matches or len(desc2) < min_matches:
            return []

        matches = self.bf.knnMatch(desc1, desc2, k=2)

        good_matches = []

        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                
                if m.distance < ratio_thresh * n.distance:
                    good_matches.append(m)

        return good_matches

    def ransac_filter(self, kp1: list, kp2: list,
                      matches: list,
                      reproj_thresh: float = 10.0,
                      min_inliers: int = 4) -> dict:
        """
        使用 RANSAC 过滤误匹配，计算单应性矩阵

        Args:
            kp1: 小地图的关键点
            kp2: 大地图的关键点
            matches: 匹配点对
            reproj_thresh: 重投影误差阈值（像素，放宽到10）
            min_inliers: 最少内点数量（降低到4）

        Returns:
            包含单应性矩阵和匹配信息的字典
        """
        if len(matches) < min_inliers:
            return {
                "success": False,
                "reason": f"匹配点不足 ({len(matches)} < {min_inliers})"
            }

        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        homography, mask = cv2.findHomography(
            src_pts, dst_pts,
            cv2.RANSAC,
            ransacReprojThreshold=reproj_thresh,
            maxIters=2000,
            confidence=0.995
        )

        if homography is None:
            return {
                "success": False,
                "reason": "无法计算单应性矩阵"
            }

        inliers = mask.ravel().sum()

        if inliers < min_inliers:
            return {
                "success": False,
                "reason": f"内点不足 ({int(inliers)} < {min_inliers})"
            }

        inlier_matches = [m for m, is_inlier in zip(matches, mask.ravel()) if is_inlier]

        h, w = 100, 100  
        pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        dst_pts_transformed = cv2.perspectiveTransform(pts, homography)

        center_x = int(np.mean(dst_pts_transformed[:, 0, 0]))
        center_y = int(np.mean(dst_pts_transformed[:, 0, 1]))

        return {
            "success": True,
            "homography": homography,
            "inliers": int(inliers),
            "total_matches": len(matches),
            "inlier_ratio": round(inliers / len(matches) * 100, 1),
            "center": (center_x, center_y),
            "corners": dst_pts_transformed.reshape(-1, 2).tolist(),
            "inlier_matches": inlier_matches
        }

    def locate_minimap_on_bigmap(self, minimap_img: np.ndarray,
                                  bigmap_img: np.ndarray) -> dict:
        """
        完整的定位流程：提取特征 → 多尺度匹配 → RANSAC → 定位

        Args:
            minimap_img: 裁剪后的小地图图像
            bigmap_img: 大地图图像

        Returns:
            定位结果字典，包含坐标、置信度等信息
        """
        start_time = time.time()

        kp1, des1 = self.extract_features(minimap_img)
        t_extract_minimap = (time.time() - start_time) * 1000

        if des1 is None or len(kp1) < 10:
            return {
                "success": False,
                "reason": "小地图特征点不足",
                "timing": {"extract_minimap_ms": t_extract_minimap}
            }

        start_bigmap = time.time()
        kp2, des2 = self.extract_features(bigmap_img)
        t_extract_bigmap = (time.time() - start_bigmap) * 1000

        if des2 is None or len(kp2) < 10:
            return {
                "success": False,
                "reason": "大地图特征点不足",
                "timing": {
                    "extract_minimap_ms": t_extract_minimap,
                    "extract_bigmap_ms": t_extract_bigmap
                }
            }

        start_match = time.time()

        scales = [1.0, 1.5, 2.0, 2.5, 3.0]
        best_matches = []
        
        for scale in scales:
            if scale != 1.0:
                scaled_minimap = cv2.resize(minimap_img, None,
                                           fx=scale, fy=scale,
                                           interpolation=cv2.INTER_CUBIC)
                kp_scaled, des_scaled = self.extract_features(scaled_minimap)
                
                if des_scaled is not None and len(kp_scaled) >= 10:
                    matches = self.match_features(des_scaled, des2)
                    
                    if len(matches) > len(best_matches):
                        best_matches = matches
                        best_kp = kp_scaled
                        best_des = des_scaled
                        best_scale = scale
            else:
                matches = self.match_features(des1, des2)
                
                if len(matches) > len(best_matches):
                    best_matches = matches
                    best_kp = kp1
                    best_des = des1
                    best_scale = scale
        
        matches = best_matches
        kp1 = best_kp
        des1 = best_des
        
        t_match = (time.time() - start_match) * 1000

        if len(matches) < 10:
            return {
                "success": False,
                "reason": f"初始匹配点不足 ({len(matches)})",
                "keypoints": {
                    "minimap": len(kp1),
                    "bigmap": len(kp2),
                    "raw_matches": len(matches)
                },
                "timing": {
                    "extract_minimap_ms": t_extract_minimap,
                    "extract_bigmap_ms": t_extract_bigmap,
                    "match_ms": t_match
                }
            }

        start_ransac = time.time()
        ransac_result = self.ransac_filter(kp1, kp2, matches)
        t_ransac = (time.time() - start_ransac) * 1000

        total_time = time.time() - start_time

        result = {
            "success": ransac_result["success"],
            "timing": {
                "extract_minimap_ms": round(t_extract_minimap, 1),
                "extract_bigmap_ms": round(t_extract_bigmap, 1),
                "match_ms": round(t_match, 1),
                "ransac_ms": round(t_ransac, 1),
                "total_ms": round(total_time * 1000, 1)
            },
            "keypoints": {
                "minimap": len(kp1),
                "bigmap": len(kp2),
                "raw_matches": len(matches)
            }
        }

        if ransac_result["success"]:
            result.update({
                "center": ransac_result["center"],
                "confidence": ransac_result["inlier_ratio"],
                "inliers": ransac_result["inliers"],
                "homography": ransac_result["homography"],
                "corners": ransac_result["corners"]
            })
        else:
            result["error"] = ransac_result.get("reason", "RANSAC验证失败")
            result["ransac_detail"] = {
                "inliers": ransac_result.get("inliers", 0),
                "total_matches": ransac_result.get("total_matches", 0)
            }

        return result
