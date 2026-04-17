"""
视频显示组件
"""

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


class VideoDisplayLabel(QLabel):
    """视频显示组件"""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 480)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
                border: 3px solid #00d4ff;
                border-radius: 10px;
                color: #00d4ff;
                font-size: 16px;
            }
        """)
        self.setText("📱 Scrcpy 低延迟推流\n\n延迟 <100ms | H.264 硬件编码\n\n点击「开始推流」")

        # 保存当前帧用于截图
        self.current_frame = None

    def update_frame(self, frame):
        """更新视频帧"""
        # 保存当前帧
        self.current_frame = frame.copy()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        rgb_contiguous = np.ascontiguousarray(rgb)
        qt_img = QImage(rgb_contiguous.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        
        # 获取当前控件的可用大小（确保不为0）
        widget_size = self.size()
        if widget_size.width() > 0 and widget_size.height() > 0:
            scaled_pixmap = pixmap.scaled(widget_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
        else:
            self.setPixmap(pixmap)

    def capture_screenshot(self):
        """
        截取当前画面并保存

        Returns:
            tuple: (success: bool, message: str, filepath: str or None)
        """
        if self.current_frame is None:
            return False, "当前无视频帧，无法截图", None

        try:
            # 创建截图目录
            screenshot_dir = Path("screenshots")
            screenshot_dir.mkdir(exist_ok=True)

            # 生成文件名（带时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = screenshot_dir / filename

            # 保存截图（使用 imencode 支持中文路径）
            success, encoded = cv2.imencode('.png', self.current_frame)
            if success:
                with open(str(filepath), 'wb') as f:
                    f.write(encoded.tobytes())
            else:
                return False, "截图编码失败", None

            return True, f"截图已保存: {filename}", str(filepath)

        except Exception as e:
            return False, f"截图失败: {str(e)}", None
