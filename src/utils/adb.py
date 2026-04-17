"""
ADB 工具函数
"""

import subprocess
from pathlib import Path


def find_tools():
    """查找 ADB 和 scrcpy-server 路径"""
    tools_dir = Path(__file__).parent.parent.parent / "tools"
    paths = {"adb": None, "scrcpy_server": None}

    for item in tools_dir.iterdir():
        if item.is_dir() and item.name.startswith("scrcpy"):
            adb = item / "adb.exe"
            if adb.exists():
                paths["adb"] = str(adb)
            server = item / "scrcpy-server"
            if server.exists():
                paths["scrcpy_server"] = str(server)

    return paths


def run_adb_command(adb_path, args, timeout=5):
    """
    执行 ADB 命令的统一封装

    Args:
        adb_path: ADB 可执行文件路径
        args: 命令参数列表（不含 adb 本身）
        timeout: 超时时间（秒）

    Returns:
        (success, output) 元组，success 为是否成功，output 为 stdout 内容
    """
    try:
        result = subprocess.run(
            [adb_path] + args,
            capture_output=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.decode('utf-8', errors='ignore').strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, ""
    except FileNotFoundError:
        return False, ""
    except Exception:
        return False, ""
