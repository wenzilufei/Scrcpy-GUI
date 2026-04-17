"""工具模块"""
from .config import ConfigManager
from .adb import find_tools
from .logger import setup_logger, logger

try:
    from .device_monitor import DeviceMonitor
except ModuleNotFoundError:
    DeviceMonitor = None

try:
    from .stream_manager import StreamManager
except ModuleNotFoundError:
    StreamManager = None

__all__ = ['ConfigManager', 'find_tools', 'DeviceMonitor', 'StreamManager', 'setup_logger', 'logger']
