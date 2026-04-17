"""
设备监控模块
负责定时检测设备连接状态
"""

import subprocess
from PySide6.QtCore import QObject, QTimer, Signal


class DeviceMonitor(QObject):
    """设备监控器"""

    # 信号
    device_connected = Signal(str)      # 设备已连接，参数：设备ID
    device_disconnected = Signal()      # 设备已断开
    check_error = Signal(str)           # 检测错误，参数：错误信息

    def __init__(self, adb_path, check_interval=2000):
        """
        初始化设备监控器

        Args:
            adb_path: ADB 可执行文件路径
            check_interval: 检测间隔（毫秒），默认 2000ms
        """
        super().__init__()
        self.adb_path = adb_path
        self.check_interval = check_interval
        self.is_connected = False
        self.device_id = None

        # 创建定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_device)

    def start(self):
        """开始监控"""
        if self.adb_path:
            self.timer.start(self.check_interval)
            # 立即检测一次
            self._check_device()

    def stop(self):
        """停止监控"""
        self.timer.stop()

    def _check_device(self):
        """检测设备连接状态"""
        if not self.adb_path:
            return

        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            output = result.stdout.decode('utf-8', errors='ignore')
            lines = output.strip().split('\n')

            # 检查是否有设备连接（排除标题行）
            device_connected = False
            device_id = None

            for line in lines[1:]:  # 跳过第一行标题
                if line.strip() and '\tdevice' in line:
                    device_connected = True
                    device_id = line.split('\t')[0]
                    break

            # 状态变化时发出信号
            if device_connected != self.is_connected:
                self.is_connected = device_connected

                if device_connected:
                    self.device_id = device_id
                    self.device_connected.emit(device_id)
                else:
                    self.device_id = None
                    self.device_disconnected.emit()

        except Exception as e:
            self.check_error.emit(str(e))

    def get_status(self):
        """
        获取当前设备状态

        Returns:
            tuple: (是否连接, 设备ID)
        """
        return (self.is_connected, self.device_id)
