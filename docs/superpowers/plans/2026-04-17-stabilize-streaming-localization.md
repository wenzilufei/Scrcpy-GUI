# Stabilize Streaming + Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复当前项目中会崩溃/不可跨平台/不可观测的关键问题，并把“大地图实时定位”链路做成稳定可控的实时系统。

**Architecture:** 保持现有目录分层与“主窗口委托 UIHandlers”的风格；针对崩溃点与跨平台点做最小侵入改造；定位线程引入背压/节流并统一日志体系；补齐可运行的单元测试脚本用于回归。

**Tech Stack:** Python 3.8+、PySide6、OpenCV、NumPy、PyAV、(stdlib) unittest

---

## Scope / Non-Goals

- In scope
  - 修复加载大地图后的 `zoom_label` 崩溃
  - scrcpy 推流子进程与 adb 调用跨平台（Windows/Linux/macOS）兼容
  - 定位线程背压/节流，避免 UI 线程高频 copy 浪费
  - 将算法层 `print()` 全部纳入统一 logger（可按级别开关）
  - scrcpy reverse 元数据接收（dummy byte）行为与文档一致，并支持兼容模式
  - 增加最小单元测试/回归脚本（不引入新依赖）
- Out of scope
  - 触控控制、录屏、无线连接、多设备、音频（后续单独立项）
  - 大幅重构 UI 布局或替换推流协议实现

---

## File Map (What to touch)

**Modify**
- `src/ui/ui_setup.py`：补齐 `zoom_label`，并将 `BigMapView.zoom_changed` 输出到 UI
- `src/ui/ui_handlers.py`：修复对 `zoom_label` 的引用；定位链路节流/背压；统一定位状态输出
- `src/core/streamer.py`：subprocess creationflags 跨平台；元数据 dummy byte 兼容；增加可测的协议解析辅助函数
- `src/utils/adb.py`：`find_tools()` 跨平台（优先 `shutil.which("adb")`），以及 Windows tools fallback
- `src/utils/device_monitor.py`：subprocess creationflags 跨平台
- `src/localization/hybrid_locator.py`：移除 `print()`，改用 logger；支持“静默/调试”模式
- `docs/SCRCPY_PROTOCOL.md`：更新 reverse 模式元数据描述，与实现一致

**Create**
- `src/utils/subprocess_compat.py`：封装跨平台的 `popen_kwargs()` / `creationflags` 获取
- `tests/test_bigmap_zoom_label.py`：验证 `setup_ui` 创建了 `zoom_label` 且不会 AttributeError（最小可运行）
- `tests/test_scrcpy_metadata_parsing.py`：验证元数据解析对“带/不带 dummy byte”两种输入都能成功

---

### Task 1: 修复大地图加载后的 zoom_label 崩溃

**Problem**
- `UIHandlers._delayed_zoom_fit()` 调用了 `self.main_window.zoom_label.setText(...)`，但 `ui_setup.py` 未创建 `zoom_label`，导入大地图后会触发 AttributeError。

**Files:**
- Modify: `src/ui/ui_setup.py`
- Modify: `src/ui/ui_handlers.py`
- Test: `tests/test_bigmap_zoom_label.py`

- [ ] **Step 1: 写一个最小回归测试（先失败）**

`tests/test_bigmap_zoom_label.py`

```python
import unittest
from PySide6.QtWidgets import QApplication

from src.ui.main_window import ScrcpyGUI


class TestBigMapZoomLabel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_zoom_label_exists(self):
        w = ScrcpyGUI()
        self.assertTrue(hasattr(w, "zoom_label"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
python -m unittest tests/test_bigmap_zoom_label.py -v
```

Expected: FAIL（`hasattr` 为 False 或初始化过程中抛 AttributeError）

- [ ] **Step 3: 在 UI 中创建 zoom_label 并接入 zoom_changed 信号**

在 `src/ui/ui_setup.py` 的 `_create_bigmap_section()` 工具栏中创建：

```python
from PySide6.QtWidgets import QLabel

main_window.zoom_label = QLabel("100%")
main_window.zoom_label.setStyleSheet("color: #00d4ff; padding: 0 6px; font-weight: bold;")
toolbar.addWidget(main_window.zoom_label)

main_window.bigmap_view.zoom_changed.connect(
    lambda z: main_window.zoom_label.setText(f"{int(z * 100)}%")
)
```

并确保 `UIHandlers._delayed_zoom_fit()` 不再依赖未初始化对象（保留逻辑，但以控件存在为前提）：

```python
if hasattr(self.main_window, "zoom_label"):
    zoom_percent = int(self.main_window.bigmap_view.zoom_factor * 100)
    self.main_window.zoom_label.setText(f"{zoom_percent}%")
```

- [ ] **Step 4: 重新运行测试，确认通过**

Run:

```bash
python -m unittest tests/test_bigmap_zoom_label.py -v
```

Expected: PASS

- [ ] **Acceptance Criteria**
- [ ] 导入大地图不再报 AttributeError
- [ ] UI 上能看到并更新缩放百分比（自适应/1:1/滚轮缩放都会更新）

---

### Task 2: subprocess 与 adb 调用跨平台兼容（Windows/Linux/macOS）

**Problem**
- 多处使用 `subprocess.CREATE_NO_WINDOW`（Windows-only），并且 adb 路径查找偏 Windows。

**Files:**
- Create: `src/utils/subprocess_compat.py`
- Modify: `src/utils/adb.py`
- Modify: `src/utils/device_monitor.py`
- Modify: `src/core/streamer.py`

- [ ] **Step 1: 添加跨平台 subprocess 兼容封装**

`src/utils/subprocess_compat.py`

```python
import os
import subprocess


def popen_kwargs():
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
```

- [ ] **Step 2: 修改所有 Popen 调用点使用 popen_kwargs()**

示例（`src/core/streamer.py`）：

```python
from ..utils.subprocess_compat import popen_kwargs

subprocess.Popen(
    [self.adb_path, "shell", server_cmd],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    **popen_kwargs()
)
```

同理替换 `device_monitor.py`、`adb.py` 中的 subprocess 调用点。

- [ ] **Step 3: 改造 find_tools() 优先使用系统 adb**

在 `src/utils/adb.py` 中优先：

```python
import shutil

adb_in_path = shutil.which("adb")
if adb_in_path:
    adb_path = adb_in_path
```

仅当找不到时再 fallback 到 `tools/scrcpy-win64-v3.3.4/` 里的 `adb.exe`（Windows）。

- [ ] **Step 4: 验证（无需真实设备）**

Run:

```bash
python -m py_compile src/utils/subprocess_compat.py
python -m py_compile src/utils/adb.py
python -m py_compile src/utils/device_monitor.py
python -m py_compile src/core/streamer.py
```

Expected: 全部无语法错误

- [ ] **Acceptance Criteria**
- [ ] 在 Linux 环境导入模块不再触发 `AttributeError: subprocess has no attribute CREATE_NO_WINDOW`
- [ ] 在 Windows 环境仍保持 “无控制台窗口” 行为（如你需要）

---

### Task 3: scrcpy reverse 元数据接收（dummy byte）兼容 + 文档对齐

**Problem**
- `docs/SCRCPY_PROTOCOL.md` 与 `_recv_metadata()` 对 reverse 模式 dummy byte 的描述不一致；后续升级/排障会踩坑。

**Files:**
- Modify: `src/core/streamer.py`
- Modify: `docs/SCRCPY_PROTOCOL.md`
- Test: `tests/test_scrcpy_metadata_parsing.py`

- [ ] **Step 1: 抽出纯函数用于解析元数据（便于测试）**

在 `src/core/streamer.py` 增加函数（位置随项目风格，推荐放在类外或类的 staticmethod）：

```python
def parse_reverse_metadata(first_64: bytes, next_12: bytes):
    name = first_64.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    codec_id = int.from_bytes(next_12[0:4], "big")
    w = int.from_bytes(next_12[4:8], "big")
    h = int.from_bytes(next_12[8:12], "big")
    return name, codec_id, w, h
```

- [ ] **Step 2: 在 _recv_metadata() 中增加“dummy byte 兼容模式”**

策略（不破坏现有 reverse 行为）：
- 先按当前逻辑读取 64 bytes 设备名
- 若解析出来的 `device_name` 为空或明显不合理，则回退：
  - 将第 1 字节视为 dummy byte，再补读 1 字节凑满 64，再解析

伪代码：

```python
name_data = self._recv_exact(64)
name = parse_name(name_data)
if not name:
    # 兼容：把第一个字节当 dummy byte
    extra = self._recv_exact(1)
    if extra:
        name_data2 = name_data[1:] + extra
        name = parse_name(name_data2)
```

- [ ] **Step 3: 添加单测覆盖“两种输入”**

`tests/test_scrcpy_metadata_parsing.py`

```python
import unittest

from src.core.streamer import parse_reverse_metadata


class TestScrcpyMetadataParsing(unittest.TestCase):
    def test_parse_without_dummy(self):
        name64 = b"Android Phone\x00" + b"\x00" * (64 - len("Android Phone") - 1)
        meta12 = (1).to_bytes(4, "big") + (1920).to_bytes(4, "big") + (840).to_bytes(4, "big")
        name, codec_id, w, h = parse_reverse_metadata(name64, meta12)
        self.assertEqual(name, "Android Phone")
        self.assertEqual(codec_id, 1)
        self.assertEqual((w, h), (1920, 840))

    def test_parse_with_dummy_shifted(self):
        # 模拟：dummy(1 byte) + 设备名(63 bytes)
        raw = b"\x00" + (b"Android\x00" + b"\x00" * (63 - len("Android") - 1))
        # 这里仅验证 parse_reverse_metadata 本身；兼容逻辑在 _recv_metadata() 回退分支中做
        name64 = raw[1:] + b"\x00"
        meta12 = (1).to_bytes(4, "big") + (1080).to_bytes(4, "big") + (472).to_bytes(4, "big")
        name, codec_id, w, h = parse_reverse_metadata(name64, meta12)
        self.assertEqual(name, "Android")
        self.assertEqual((w, h), (1080, 472))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: 文档对齐**

在 `docs/SCRCPY_PROTOCOL.md` 明确：
- reverse 模式默认无 dummy byte（与当前实现一致）
- 兼容模式：若存在 dummy byte，将自动回退解析

- [ ] **Step 5: 运行测试**

Run:

```bash
python -m unittest tests/test_scrcpy_metadata_parsing.py -v
```

Expected: PASS

- [ ] **Acceptance Criteria**
- [ ] reverse 元数据解析在两种输入下都能得到正确设备名与分辨率
- [ ] 文档描述与实现一致（并说明兼容策略）

---

### Task 4: 定位线程背压/节流（避免 UI 高频 copy 浪费）

**Problem**
- UI 每帧都 `update_minimap(minimap.copy())`，而定位 `locate()` 约 150ms，定位线程追不上 UI，会造成不必要的内存 copy 与 CPU 竞争。

**Files:**
- Modify: `src/localization/localization_thread.py`
- Modify: `src/ui/ui_handlers.py`

- [ ] **Step 1: 把定位线程从“轮询 sleep”改为“事件驱动 + 节流”**

建议改法（保持简单、无需引入新依赖）：
- 增加 `QWaitCondition` + `QMutex`：只有收到新 minimap 才唤醒定位线程
- 增加节流：例如至少间隔 200ms 才做一次定位（或按帧计数）

核心结构（示意）：

```python
from PySide6.QtCore import QWaitCondition, QElapsedTimer

self._cond = QWaitCondition()
self._timer = QElapsedTimer()
self._timer.start()

def update_minimap(...):
    with QMutexLocker(self._mutex):
        self._minimap_img = minimap_img  # 只存最新
        self._cond.wakeOne()

def run(self):
    while self._running:
        with QMutexLocker(self._mutex):
            if self._minimap_img is None:
                self._cond.wait(self._mutex, 500)
            minimap = self._minimap_img
            self._minimap_img = None
        if minimap is None:
            continue
        if self._timer.elapsed() < 200:
            continue
        self._timer.restart()
        ...
```

- [ ] **Step 2: UI 侧去掉对线程内部字段的访问**

目前 UI 用了 `self.main_window.localization_thread._running` 判断线程状态，这属于跨模块耦合。
改为公开方法（例如 `is_localizing()`）或用 `QThread.isRunning()`。

- [ ] **Step 3: 验证（编译检查 + 手动验证）**

Run:

```bash
python -m py_compile src/localization/localization_thread.py
python -m py_compile src/ui/ui_handlers.py
```

Manual:
- 启动推流 + 导入大地图 + 开启定位
- 观察 CPU 占用：开启定位后明显增加但不应出现 UI 卡顿

- [ ] **Acceptance Criteria**
- [ ] 开启定位后 UI 主画面不卡顿（主线程不阻塞）
- [ ] 定位频率受控（例如 5Hz），并且始终使用“最新小地图”

---

### Task 5: 算法层 print() 全部替换为 logger（可观测性 + 性能）

**Problem**
- `HybridLocator.locate()` 大量 `print()`，实时模式下会极其影响性能且无法按级别过滤。

**Files:**
- Modify: `src/localization/hybrid_locator.py`
- Modify: `src/utils/logger.py`（如需补齐 child logger）

- [ ] **Step 1: 引入 logger 并替换 print**

在 `hybrid_locator.py` 顶部：

```python
from ..utils.logger import logger
```

将 `print("...")` 改为：
- 调试信息：`logger.debug("...")`
- 关键步骤：`logger.info("...")`
- 失败回退：`logger.warning("...")`

- [ ] **Step 2: 提供一个“静默运行”开关（可选，但推荐）**

例如 `HybridLocator.__init__(..., verbose: bool = False)`，verbose 为 False 时仅输出 warning/error。

- [ ] **Step 3: 验证**

Run:

```bash
python -m py_compile src/localization/hybrid_locator.py
```

- [ ] **Acceptance Criteria**
- [ ] 实时定位时终端不再被 print 刷屏
- [ ] 仍能通过 logger 看到关键定位结果（按级别可控）

---

## Self-Review Checklist (for this plan)
- [ ] 覆盖了当前已知的“崩溃点 / 跨平台点 / 协议口径 / 实时定位稳定性 / 可观测性”
- [ ] 计划中所有步骤都给出了具体文件路径、具体代码片段、具体命令
- [ ] 未引入新的第三方依赖（测试使用 unittest）

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-stabilize-streaming-localization.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - 我按 Task 逐个派发子 agent 实现，任务间做审查与回归验证
2. **Inline Execution** - 我在当前会话里按任务逐条执行并做阶段性验收

你选哪一种？

