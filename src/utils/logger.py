"""
日志配置模块
提供统一的日志管理
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


# 日志级别图标映射（模块级常量）
LEVEL_ICONS = {
    logging.DEBUG: '🔍',
    logging.INFO: '✓',
    logging.WARNING: '⚠',
    logging.ERROR: '✗',
    logging.CRITICAL: '❌'
}


class LogFormatter(logging.Formatter):
    """自定义日志格式化器"""

    def format(self, record):
        """格式化日志记录"""
        # 添加时间戳
        record.timestamp = datetime.now().strftime('%H:%M:%S')

        # 根据日志级别添加图标
        record.icon = LEVEL_ICONS.get(record.levelno, '•')

        return super().format(record)


def setup_logger(name='Scrcpy', log_file=None, level=logging.INFO):
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选）
        level: 日志级别

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # 格式化器
    formatter = LogFormatter(
        '[%(timestamp)s] %(icon)s %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（可选）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_file,
            encoding='utf-8',
            mode='a'
        )
        file_handler.setLevel(level)

        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


# 创建全局日志记录器
logger = setup_logger()
