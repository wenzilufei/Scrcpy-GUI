"""
定位线程
"""
import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from .hybrid_locator import HybridLocator

class LocalizationThread(QThread):
    """
    后台定位线程，用于运行 HybridLocator 以免阻塞主 UI
    """
    # 发生定位结果时发出的信号
    located = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.locator = HybridLocator()
        self._running = False
        self._minimap_img = None
        self._bigmap_img = None
        self._mutex = QMutex()

    def start_localization(self, bigmap_path: str):
        """
        开始定位
        
        Args:
            bigmap_path: 大地图图片路径
        """
        # 预加载大地图图片
        self._bigmap_img = cv2.imread(bigmap_path)
        if self._bigmap_img is None:
            self.located.emit({"final": {"success": False, "error": "无法加载大地图"}})
            return
            
        self._running = True
        self.start()

    def stop_localization(self):
        """
        停止定位
        """
        self._running = False
        self.wait()

    def update_minimap(self, minimap_img: np.ndarray):
        """
        更新最新的小地图图像（由主线程调用）
        
        Args:
            minimap_img: 小地图图像
        """
        with QMutexLocker(self._mutex):
            self._minimap_img = minimap_img.copy() if minimap_img is not None else None

    def run(self):
        """
        线程主循环
        """
        while self._running:
            # 获取最新小地图
            with QMutexLocker(self._mutex):
                minimap = self._minimap_img.copy() if self._minimap_img is not None else None
                
            if minimap is not None and self._bigmap_img is not None:
                # 运行混合定位算法（大约 150ms）
                result = self.locator.locate(minimap, self._bigmap_img)
                
                if self._running:
                    self.located.emit(result)
                    
            # 稍微休眠，避免占用 100% CPU，最高约 20 fps，但实际受 locate 耗时限制
            time.sleep(0.05)
