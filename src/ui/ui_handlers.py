"""
UI 事件处理模块
负责主窗口的所有事件处理逻辑
"""

import cv2
import numpy as np
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from ..utils.adb import run_adb_command


class UIHandlers:
    """UI 事件处理器"""

    STATUS_GREEN = "color: #4CAF50; font-size: 20px; padding: 0 10px;"
    STATUS_GRAY = "color: #888; font-size: 20px; padding: 0 10px;"
    STATUS_ORANGE = "color: #FFA500; font-size: 20px; padding: 0 10px;"
    STATUS_RED = "color: #f44336; font-size: 20px; padding: 0 10px;"

    def __init__(self, main_window):
        self.main_window = main_window

    def _show_message_box(self, icon, title, text):
        """
        显示消息框（修复深色主题下显示不清的问题）

        Args:
            icon: 消息图标类型 (Warning, Critical, Information)
            title: 标题
            text: 内容
        """
        msg_box = QMessageBox(self.main_window)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)

        # 设置浅色主题样式，确保文字清晰可见
        msg_box.setStyleSheet("""
            QMessageBox {
                background: #f0f0f0;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
                padding: 5px;
            }
            QPushButton {
                background: #00d4ff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background: #00b8e6;
            }
            QPushButton:pressed {
                background: #0099cc;
            }
        """)

        msg_box.exec()

    def setup_connections(self):
        """设置信号连接"""
        # 设备监控器信号
        self.main_window.device_monitor.device_connected.connect(self._on_device_connected)
        self.main_window.device_monitor.device_disconnected.connect(self._on_device_disconnected)
        self.main_window.device_monitor.check_error.connect(self._on_check_error)

        # 推流管理器信号
        self.main_window.stream_manager.reconnect_started.connect(self._on_reconnect_started)
        self.main_window.stream_manager.reconnect_success.connect(self._on_reconnect_success)
        self.main_window.stream_manager.reconnect_failed.connect(self._on_reconnect_failed)

    def _on_device_connected(self, device_id):
        """设备已连接"""
        # 更新状态栏显示设备名称
        self.main_window.device_label.setText(f"设备: {device_id}")

        # 获取手机实际分辨率
        self._get_phone_resolution()

        # 如果正在推流，指示灯变绿色
        if self.main_window.stream_manager.is_streaming:
            self.main_window.status_indicator.setStyleSheet(self.STATUS_GREEN)
            self.main_window._log("✓ 设备已连接")

            if self.main_window.stream_manager.should_reconnect:
                if self.main_window.stream_manager.on_device_reconnected():
                    self._on_start()
        else:
            self.main_window.status_indicator.setStyleSheet(self.STATUS_GRAY)
            self.main_window._log(f"✓ 检测到设备: {device_id}")

    def _on_device_disconnected(self):
        """设备已断开"""
        self.main_window.device_label.setText("设备: 未连接")
        self.main_window.status_indicator.setStyleSheet(self.STATUS_GRAY)

        # 如果正在推流，停止推流
        if self.main_window.stream_manager.is_streaming:
            self.main_window._log("⚠ 设备已断开")
            if self.main_window.stream_thread and self.main_window.stream_thread.isRunning():
                self.main_window._log("推流已中断，等待设备重连...")
                should_reconnect = self.main_window.stream_manager.should_reconnect
                self._on_stop()
                self.main_window.stream_manager.should_reconnect = should_reconnect
        else:
            self.main_window._log("⚠ 设备已断开")

    def _on_check_error(self, error_msg):
        """检测错误"""
        self.main_window._log(f"检测设备失败: {error_msg}")

    def _get_phone_resolution(self):
        """获取手机实际分辨率"""
        if not self.main_window.paths["adb"]:
            return

        try:
            success, output = run_adb_command(
                self.main_window.paths["adb"], ["shell", "wm", "size"], timeout=2
            )

            if not success or "Physical size:" not in output:
                return

            resolution_str = output.split("Physical size:")[1].strip()
            width, height = resolution_str.split('x')

            phone_width = int(width)
            phone_height = int(height)

            self.main_window.phone_resolution = {
                'width': max(phone_width, phone_height),
                'height': min(phone_width, phone_height),
                'portrait': (phone_width, phone_height),
                'landscape': (max(phone_width, phone_height), min(phone_width, phone_height))
            }

            self._update_resolution_options()

            self.main_window._log(f"手机分辨率: {phone_width}x{phone_height} (竖屏) / {self.main_window.phone_resolution['landscape'][0]}x{self.main_window.phone_resolution['landscape'][1]} (横屏)")

        except Exception as e:
            self.main_window._log(f"获取手机分辨率失败: {str(e)}")

    def _update_resolution_options(self):
        """更新分辨率下拉选项"""
        if not self.main_window.phone_resolution:
            return

        phone_width = self.main_window.phone_resolution['width']

        # 设置三挡分辨率
        options = []

        # 1080p 挡
        options.append("1080")

        # 1920p 挡（如果手机支持）
        if phone_width >= 1920:
            options.append("1920")

        # 手机最大分辨率挡
        if phone_width > 1920:
            options.append(str(phone_width))

        # 更新下拉选项
        self.main_window.resolution.clear()
        self.main_window.resolution.addItems(options)

        # 获取配置文件中保存的分辨率
        config = self.main_window.config_manager.load()
        saved_resolution = config.get('resolution', '')

        # 优先使用保存的分辨率（如果在选项中）
        if saved_resolution in options:
            self.main_window.resolution.setCurrentText(saved_resolution)
            self.main_window._log(f"分辨率选项已更新: {', '.join(options)} (已恢复: {saved_resolution})")
        # 否则使用默认值
        elif "1920" in options:
            self.main_window.resolution.setCurrentText("1920")
            self.main_window._log(f"分辨率选项已更新: {', '.join(options)} (默认: 1920)")
        else:
            self.main_window.resolution.setCurrentText("1080")
            self.main_window._log(f"分辨率选项已更新: {', '.join(options)} (默认: 1080)")

    def _on_reconnect_started(self, attempt, max_attempts):
        """开始重连"""
        self.main_window._log(f"检测到设备重连，尝试恢复推流 ({attempt}/{max_attempts})")

    def _on_reconnect_success(self):
        """重连成功"""
        self.main_window._log("✓ 推流已恢复")

    def _on_reconnect_failed(self):
        """重连失败"""
        self.main_window._log("✗ 达到最大重连次数，停止自动重连")

    def _on_start(self):
        """开始推流"""
        if not self.main_window.paths["adb"] or not self.main_window.paths["scrcpy_server"]:
            self._show_message_box(QMessageBox.Icon.Warning, "警告", "未找到 ADB 或 scrcpy-server！")
            return

        # 检查设备是否已连接
        is_connected, device_id = self.main_window.device_monitor.get_status()
        if not is_connected:
            self._show_message_box(QMessageBox.Icon.Warning, "警告", "设备未连接！\n请确保：\n1. USB 已连接\n2. USB 调试已开启\n3. 已授权调试")
            return

        self.main_window._log(f"启动: {self.main_window.resolution.currentText()}p, {self.main_window.bitrate.currentText()}, {self.main_window.fps.currentText()}fps")

        # 更新状态栏
        self.main_window.device_label.setText("设备: 连接中...")
        self.main_window.status_indicator.setStyleSheet(self.STATUS_ORANGE)

        from ..core.streamer import ScrcpySocketThread
        self.main_window.stream_thread = ScrcpySocketThread(
            self.main_window.paths["adb"],
            self.main_window.paths["scrcpy_server"],
            self.main_window.bitrate.currentText(),
            int(self.main_window.fps.currentText()),
            int(self.main_window.resolution.currentText()),
            self.main_window.codec.currentText()
        )

        self.main_window.stream_thread.frame_ready.connect(self._on_frame_received)
        self.main_window.stream_thread.error_occurred.connect(self._on_error)
        self.main_window.stream_thread.status_changed.connect(self._on_status)
        self.main_window.stream_thread.start()

        # 禁用推流参数控件
        self.main_window.resolution.setEnabled(False)
        self.main_window.bitrate.setEnabled(False)
        self.main_window.fps.setEnabled(False)
        self.main_window.codec.setEnabled(False)

        self.main_window.start_btn.setEnabled(False)
        self.main_window.stop_btn.setEnabled(True)
        self.main_window.screenshot_btn.setEnabled(True)  # 推流时启用截图
        self.main_window._log("✓ 推流已启动")

        # 标记推流开始
        self.main_window.stream_manager.start_streaming()

    def _on_stop(self):
        """停止推流"""
        if self.main_window.stream_thread and self.main_window.stream_thread.isRunning():
            self.main_window.stream_thread.stop()
            self.main_window.stream_thread.wait(5000)
            self.main_window.stream_thread = None

        # 重置小地图相关标志
        self.main_window.first_frame_received = False

        # 清空小地图显示
        self.main_window.minimap_display.setText("等待推流...")
        self.main_window.minimap_display.clear()

        # 更新状态栏 - 使用设备监控器的当前状态
        is_connected, device_id = self.main_window.device_monitor.get_status()
        if is_connected:
            self.main_window.device_label.setText(f"设备: {device_id}")
            self.main_window.status_indicator.setStyleSheet(self.STATUS_GREEN)
        else:
            self.main_window.device_label.setText("设备: 未连接")
            self.main_window.status_indicator.setStyleSheet(self.STATUS_GRAY)

        # 恢复推流参数控件
        self.main_window.resolution.setEnabled(True)
        self.main_window.bitrate.setEnabled(True)
        self.main_window.fps.setEnabled(True)
        self.main_window.codec.setEnabled(True)

        self.main_window.start_btn.setEnabled(True)
        self.main_window.stop_btn.setEnabled(False)
        self.main_window.screenshot_btn.setEnabled(False)  # 停止推流时禁用截图
        self.main_window._log("推流已停止")

        # 标记推流停止
        self.main_window.stream_manager.stop_streaming()

    def _on_error(self, msg):
        """错误处理"""
        self._show_message_box(QMessageBox.Icon.Critical, "错误", msg)
        self.main_window._log(f"✗ {msg}")
        self._on_stop()

    def _on_status(self, msg):
        """状态更新"""
        self.main_window._log(msg)
        self.main_window.status_bar.showMessage(msg, 3000)

        # 更新设备名称
        if "设备:" in msg and ("Redmi" in msg or "Android" in msg or "Xiaomi" in msg):
            if "Redmi" in msg:
                device_name = msg.split("设备:")[-1].strip()
                self.main_window.device_label.setText(f"设备: {device_name}")
            elif "Android" in msg:
                self.main_window.device_label.setText("设备: Android 设备")

        # 更新连接状态指示灯
        if "✓ 视频流连接已建立" in msg or "开始解码" in msg:
            self.main_window.status_indicator.setStyleSheet(self.STATUS_GREEN)
            if self.main_window.stream_manager.should_reconnect:
                self.main_window.stream_manager.on_reconnect_success()
        elif "✗" in msg or "失败" in msg or "错误" in msg:
            self.main_window.status_indicator.setStyleSheet(self.STATUS_RED)

    def _on_screenshot(self):
        """截图处理"""
        success, message, filepath = self.main_window.video.capture_screenshot()

        if success:
            self.main_window._log(f"✓ {message}")
            # 显示成功提示（使用状态栏）
            self.main_window.status_bar.showMessage(message, 5000)
        else:
            self.main_window._log(f"✗ {message}")
            self._show_message_box(QMessageBox.Icon.Warning, "截图失败", message)

    def _on_load_bigmap(self):
        """
        导入大地图处理
        
        加载指定路径的大地图图片并显示（支持缩放）
        """
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtCore import QTimer
        from pathlib import Path

        default_path = str(Path(__file__).parent.parent.parent / "daditu")

        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "选择大地图图片",
            default_path,
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)"
        )

        if not file_path:
            return

        try:
            # 使用 BigMapView 加载图片
            success = self.main_window.bigmap_view.load_image(file_path)

            if not success:
                self.main_window._log("✗ 无法加载图片文件")
                self._show_message_box(
                    QMessageBox.Icon.Warning,
                    "加载失败",
                    f"无法读取图片文件：{file_path}"
                )
                return

            # 保存大地图路径到配置
            self._save_bigmap_path(file_path)

            # 延迟调用 zoom_fit()，确保视图完成布局后再适应窗口
            QTimer.singleShot(100, self._delayed_zoom_fit)

            # 获取图片信息
            width = int(self.main_window.bigmap_view.scene.width())
            height = int(self.main_window.bigmap_view.scene.height())

            self.main_window._log(f"✓ 大地图已加载: {width}x{height}")
            self.main_window.status_bar.showMessage(f"大地图已加载: {width}x{height}", 3000)

        except Exception as e:
            self.main_window._log(f"✗ 加载大地图失败: {str(e)}")
            self._show_message_box(
                QMessageBox.Icon.Warning,
                "加载失败",
                f"加载大地图时出错：{str(e)}"
            )
    
    def _delayed_zoom_fit(self):
        """延迟执行缩放适应"""
        self.main_window.bigmap_view.zoom_fit()
        
        # 更新缩放比例显示
        zoom_percent = int(self.main_window.bigmap_view.zoom_factor * 100)
        self.main_window.zoom_label.setText(f"{zoom_percent}%")

    def _save_bigmap_path(self, file_path):
        """
        保存大地图路径到配置

        Args:
            file_path: 大地图文件路径
        """
        config = self.main_window.config_manager.load()
        config['bigmap_path'] = file_path
        self.main_window.config_manager.save(config)

    def _auto_load_bigmap(self):
        """
        自动加载上次的大地图

        Returns:
            bool: 是否成功加载
        """
        config = self.main_window.config_manager.load()
        bigmap_path = config.get('bigmap_path')

        if not bigmap_path:
            return False

        from pathlib import Path

        # 检查文件是否存在
        if not Path(bigmap_path).exists():
            self.main_window._log(f"⚠ 大地图文件不存在: {bigmap_path}")
            return False

        try:
            # 使用 BigMapView 加载图片
            success = self.main_window.bigmap_view.load_image(bigmap_path)

            if not success:
                return False

            # 获取图片信息
            width = self.main_window.bigmap_view.scene.width()
            height = self.main_window.bigmap_view.scene.height()

            self.main_window._log(f"✓ 自动加载大地图: {width}x{height}")
            return True

        except Exception as e:
            self.main_window._log(f"⚠ 自动加载大地图失败: {str(e)}")
            return False

    def _on_frame_received(self, frame):
        """
        帧接收处理
        第一帧时计算小地图坐标，然后转发给主画面显示
        """
        # 第一帧：计算小地图坐标（一次性，性能影响可忽略）
        if not self.main_window.first_frame_received:
            self._calculate_minimap_coords(frame)
            self.main_window.first_frame_received = True

        # 主画面显示（不受影响）
        self.main_window.video.update_frame(frame)

        # 小地图显示（默认显示）
        if self.main_window.minimap_coords:
            minimap = self._extract_minimap(frame)
            if minimap is not None:
                self.main_window.minimap_display.update_frame(minimap)

    def _calculate_minimap_coords(self, frame):
        """
        计算小地图坐标并缓存到配置文件

        Args:
            frame: 当前视频帧
        """
        from ..utils.minimap_calculator import MinimapCalculator

        height, width = frame.shape[:2]
        resolution_key = f"{width}x{height}"

        # 先检查配置文件缓存
        cached_coords = self.main_window.config_manager.get_minimap_coords(resolution_key)

        if cached_coords:
            self.main_window.minimap_coords = cached_coords
            self.main_window._log(f"使用缓存的小地图坐标: {resolution_key}")
        else:
            # 计算新坐标
            self.main_window.minimap_coords = MinimapCalculator.calculate(width, height)

            # 保存到配置文件
            self.main_window.config_manager.save_minimap_coords(self.main_window.minimap_coords)
            self.main_window._log(f"计算并保存小地图坐标: {resolution_key}")
            self.main_window._log(f"  圆心: {self.main_window.minimap_coords['center']}, 半径: {self.main_window.minimap_coords['radius']}px")

    def _extract_minimap(self, frame):
        """
        从帧中裁剪小地图区域

        Args:
            frame: 视频帧（BGR格式）

        Returns:
            小地图图像或 None
        """
        if not self.main_window.minimap_coords:
            return None

        rect = self.main_window.minimap_coords['inscribed_rect']
        x1, y1 = rect['top_left']
        x2, y2 = rect['bottom_right']

        # 裁剪小地图区域（NumPy切片，性能极高）
        minimap = frame[y1:y2, x1:x2]
        return minimap

    def get_minimap_from_frame(self, frame=None):
        """
        从帧中提取小地图（公共方法，按需调用）

        Args:
            frame: 可选，不传则使用当前帧

        Returns:
            小地图图像或 None
        """
        if not self.main_window.minimap_coords:
            self.main_window._log("警告: 小地图坐标未计算，无法提取")
            return None

        if frame is None:
            frame = self.main_window.video.current_frame

        if frame is None:
            self.main_window._log("警告: 当前无视频帧，无法提取小地图")
            return None

        return self._extract_minimap(frame)
