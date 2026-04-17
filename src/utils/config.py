"""
配置管理工具
"""

import json
import threading
from pathlib import Path
from typing import Dict, Optional

from .logger import logger


class ConfigManager:
    """配置管理器（线程安全）"""

    def __init__(self, config_file="config.json"):
        self.config_file = Path(config_file)
        self._lock = threading.Lock()

    def load(self):
        """
        加载配置

        Returns:
            配置字典，加载失败返回空字典
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(f"配置文件格式错误: {str(e)}")
            except PermissionError:
                logger.warning("配置文件无读取权限")
            except Exception as e:
                logger.warning(f"加载配置失败: {str(e)}")
        return {}

    def save(self, config):
        """
        保存配置（线程安全）

        Args:
            config: 配置字典

        Returns:
            保存是否成功
        """
        with self._lock:
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                return True
            except PermissionError:
                logger.warning("配置文件无写入权限")
            except Exception as e:
                logger.warning(f"保存配置失败: {str(e)}")
            return False

    def get_minimap_coords(self, resolution_key: str) -> Optional[Dict]:
        """
        获取指定分辨率的小地图坐标缓存

        Args:
            resolution_key: 分辨率键，如 "1920x840"

        Returns:
            小地图坐标字典，不存在则返回 None
        """
        config = self.load()
        minimap_cache = config.get('minimap_cache', {})
        return minimap_cache.get(resolution_key)

    def save_minimap_coords(self, coords: Dict) -> bool:
        """
        保存小地图坐标到缓存（线程安全）

        Args:
            coords: 小地图坐标字典，必须包含 resolution_key

        Returns:
            保存是否成功
        """
        if 'resolution_key' not in coords:
            return False

        with self._lock:
            config = self.load()
            if 'minimap_cache' not in config:
                config['minimap_cache'] = {}

            config['minimap_cache'][coords['resolution_key']] = coords
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                return True
            except PermissionError:
                logger.warning("配置文件无写入权限")
            except Exception as e:
                logger.warning(f"保存小地图坐标失败: {str(e)}")
            return False
