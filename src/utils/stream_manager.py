"""
推流管理模块
负责管理推流状态和自动重连
"""

from PySide6.QtCore import QObject, Signal


class StreamManager(QObject):
    """推流管理器"""

    # 信号
    reconnect_started = Signal(int, int)  # 开始重连，参数：(当前次数, 最大次数)
    reconnect_success = Signal()          # 重连成功
    reconnect_failed = Signal()           # 重连失败（达到最大次数）

    def __init__(self, max_reconnect_attempts=3):
        """
        初始化推流管理器

        Args:
            max_reconnect_attempts: 最大重连次数，默认 3 次
        """
        super().__init__()
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_attempts = 0
        self.is_streaming = False
        self.should_reconnect = False  # 是否应该自动重连

    def start_streaming(self):
        """开始推流"""
        self.is_streaming = True
        self.reconnect_attempts = 0
        self.should_reconnect = True

    def stop_streaming(self):
        """停止推流"""
        self.is_streaming = False
        self.reconnect_attempts = 0
        self.should_reconnect = False

    def on_device_reconnected(self):
        """
        设备重连时调用
        返回是否应该尝试重连
        """
        if not self.should_reconnect:
            return False

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.reconnect_failed.emit()
            return False

        self.reconnect_attempts += 1
        self.reconnect_started.emit(self.reconnect_attempts, self.max_reconnect_attempts)
        return True

    def on_reconnect_success(self):
        """重连成功时调用"""
        self.reconnect_attempts = 0
        self.reconnect_success.emit()

    def get_status(self):
        """
        获取当前推流状态

        Returns:
            tuple: (是否推流中, 重连次数, 最大重连次数)
        """
        return (self.is_streaming, self.reconnect_attempts, self.max_reconnect_attempts)
