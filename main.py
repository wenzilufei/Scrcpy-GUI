"""
Scrcpy 低延迟推流 GUI - 主程序入口
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.ui.main_window import ScrcpyGUI


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ScrcpyGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
