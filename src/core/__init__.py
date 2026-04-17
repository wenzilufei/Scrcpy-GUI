"""核心模块"""
try:
    from .streamer import ScrcpySocketThread
except ModuleNotFoundError:
    ScrcpySocketThread = None

__all__ = ['ScrcpySocketThread']
