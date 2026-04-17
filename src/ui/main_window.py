"""
Scrcpy 主窗口界面
"""

from datetime import datetime
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import QTimer

from ..core.streamer import ScrcpySocketThread
from ..utils import DeviceMonitor, StreamManager, logger, find_tools, ConfigManager
from .video_display import VideoDisplayLabel
from .ui_setup import setup_ui
from .ui_handlers import UIHandlers


class ScrcpyGUI(QMainWindow):
    """Scrcpy 主窗口"""

    def __init__(self):
        super().__init__()
        self.stream_thread = None
        self.paths = find_tools()
        self.config_manager = ConfigManager()

        # 初始化设备监控器和推流管理器
        self.device_monitor = DeviceMonitor(self.paths["adb"])
        self.stream_manager = StreamManager(max_reconnect_attempts=3)

        # 存储手机实际分辨率
        self.phone_resolution = None

        # 配置保存防抖定时器
        self.config_save_timer = QTimer()
        self.config_save_timer.setSingleShot(True)
        self.config_save_timer.timeout.connect(self._do_save_config)

        # 小地图坐标相关
        self.minimap_coords = None  # 当前分辨率的小地图坐标
        self.first_frame_received = False  # 是否已接收第一帧

        # 初始化 UI 处理器
        self.ui_handlers = UIHandlers(self)

        # 设置 UI
        setup_ui(self)

        # 加载配置
        self._load_config()

        # 设置信号连接
        self.ui_handlers.setup_connections()

        # 启动设备监控
        self.device_monitor.start()

    def _load_config(self):
        """加载保存的配置"""
        config = self.config_manager.load()
        if config:
            # 恢复参数选择
            if 'resolution' in config:
                self.resolution.setCurrentText(config['resolution'])
            if 'bitrate' in config:
                self.bitrate.setCurrentText(config['bitrate'])
            if 'fps' in config:
                self.fps.setCurrentText(config['fps'])
            if 'codec' in config:
                self.codec.setCurrentText(config['codec'])

            # 恢复窗口大小和位置
            if 'window_width' in config and 'window_height' in config:
                self.resize(config['window_width'], config['window_height'])
            if 'window_x' in config and 'window_y' in config:
                self.move(config['window_x'], config['window_y'])

            # 自动加载大地图（延迟执行，等待 UI 完全初始化）
            QTimer.singleShot(150, self._auto_load_bigmap)

            # 恢复大地图缩放比例
            if 'bigmap_zoom' in config:
                # 延迟应用缩放（等待大地图加载完成）
                QTimer.singleShot(200, lambda: self._restore_bigmap_zoom(config['bigmap_zoom']))

            self._log("✓ 已加载上次配置")

    def _schedule_save_config(self):
        """调度配置保存（防抖）"""
        self.config_save_timer.start(1000)  # 1秒后保存

    def _do_save_config(self):
        """实际保存配置"""
        # 先加载现有配置，保留其他字段（如 bigmap_path, minimap_cache）
        config = self.config_manager.load()

        # 更新当前配置
        config['resolution'] = self.resolution.currentText()
        config['bitrate'] = self.bitrate.currentText()
        config['fps'] = self.fps.currentText()
        config['codec'] = self.codec.currentText()
        config['window_width'] = self.width()
        config['window_height'] = self.height()
        config['window_x'] = self.x()
        config['window_y'] = self.y()
        config['bigmap_zoom'] = self.bigmap_view.zoom_factor if hasattr(self, 'bigmap_view') else 1.0

        if self.config_manager.save(config):
            self._log("✓ 配置已保存")

    def _log(self, msg, level='info'):
        """
        添加日志到界面

        Args:
            msg: 日志消息
            level: 日志级别 (debug, info, warning, error)
        """
        # 添加到界面日志
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log.append(f"[{timestamp}] {msg}")

        # 同时输出到 logger
        if level == 'debug':
            logger.debug(msg)
        elif level == 'warning':
            logger.warning(msg)
        elif level == 'error':
            logger.error(msg)
        else:
            logger.info(msg)

    # 事件处理方法委托给 ui_handlers
    def _on_device_connected(self, device_id):
        self.ui_handlers._on_device_connected(device_id)

    def _on_device_disconnected(self):
        self.ui_handlers._on_device_disconnected()

    def _on_check_error(self, error_msg):
        self.ui_handlers._on_check_error(error_msg)

    def _on_reconnect_started(self, attempt, max_attempts):
        self.ui_handlers._on_reconnect_started(attempt, max_attempts)

    def _on_reconnect_success(self):
        self.ui_handlers._on_reconnect_success()

    def _on_reconnect_failed(self):
        self.ui_handlers._on_reconnect_failed()

    def _on_start(self):
        self.ui_handlers._on_start()

    def _on_stop(self):
        self.ui_handlers._on_stop()

    def _on_error(self, msg):
        self.ui_handlers._on_error(msg)

    def _on_status(self, msg):
        self.ui_handlers._on_status(msg)

    def _on_screenshot(self):
        self.ui_handlers._on_screenshot()

    def _on_load_bigmap(self):
        self.ui_handlers._on_load_bigmap()

    def _on_frame_received(self, frame):
        self.ui_handlers._on_frame_received(frame)

    def _calculate_minimap_coords(self, frame):
        self.ui_handlers._calculate_minimap_coords(frame)

    def _extract_minimap(self, frame):
        return self.ui_handlers._extract_minimap(frame)

    def get_minimap_from_frame(self, frame=None):
        return self.ui_handlers.get_minimap_from_frame(frame)

    def _auto_load_bigmap(self):
        """自动加载上次的大地图"""
        self.ui_handlers._auto_load_bigmap()

    def _restore_bigmap_zoom(self, zoom_factor):
        """恢复大地图缩放比例"""
        if hasattr(self, 'bigmap_view') and self.bigmap_view.pixmap_item:
            self.bigmap_view.zoom_factor = zoom_factor
            self.bigmap_view.apply_zoom()

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 立即保存配置
        self._do_save_config()

        if self.stream_thread and self.stream_thread.isRunning():
            self.stream_thread.stop()
            self.stream_thread.wait(5000)

        event.accept()

    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 触发防抖保存
        self._schedule_save_config()

    def moveEvent(self, event):
        """窗口位置改变事件"""
        super().moveEvent(event)
        # 触发防抖保存
        self._schedule_save_config()
