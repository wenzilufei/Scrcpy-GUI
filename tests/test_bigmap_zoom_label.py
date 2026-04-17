import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PySide6.QtWidgets import QApplication
    from src.ui.main_window import ScrcpyGUI
    _HAS_PYSIDE6 = True
except ModuleNotFoundError:
    _HAS_PYSIDE6 = False


class TestBigMapZoomLabel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _HAS_PYSIDE6:
            cls.app = QApplication.instance() or QApplication([])

    @unittest.skipIf(not _HAS_PYSIDE6, "PySide6 not installed")
    def test_zoom_label_exists(self):
        w = ScrcpyGUI()
        self.assertTrue(hasattr(w, "zoom_label"))


if __name__ == "__main__":
    unittest.main()
