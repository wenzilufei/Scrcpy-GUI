"""
定位线程
"""
import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker, QWaitCondition

from .hybrid_locator import HybridLocator


class LocalizationThread(QThread):
    """
    后台定位线程，用于运行 HybridLocator 以免阻塞主 UI
    """
    located = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.locator = HybridLocator()
        self._running = False
        self._minimap_img = None
        self._bigmap_img = None
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._min_interval_s = 0.2
        self._last_locate_ts = 0.0

    def start_localization(self, bigmap_path: str):
        """
        开始定位
        
        Args:
            bigmap_path: 大地图图片路径
        """
        if self.isRunning():
            self.stop_localization()

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
        self._cond.wakeOne()
        self.wait()

    def update_minimap(self, minimap_img: np.ndarray):
        """
        更新最新的小地图图像（由主线程调用）
        
        Args:
            minimap_img: 小地图图像
        """
        with QMutexLocker(self._mutex):
            self._minimap_img = minimap_img.copy() if minimap_img is not None else None
            self._cond.wakeOne()

    def run(self):
        """
        线程主循环
        """
        while self._running:
            with QMutexLocker(self._mutex):
                if self._minimap_img is None:
                    self._cond.wait(self._mutex, 500)

                if not self._running:
                    return

                minimap = self._minimap_img
                self._minimap_img = None

            if minimap is None or self._bigmap_img is None:
                continue

            now = time.monotonic()
            if now - self._last_locate_ts < self._min_interval_s:
                continue
            self._last_locate_ts = now

            result = self.locator.locate(minimap, self._bigmap_img)
            if self._running:
                self.located.emit(result)
