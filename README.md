# Scrcpy 低延迟推流 GUI 工具

[![版本](https://img.shields.io/badge/版本-1.0.0-blue.svg)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org)
[![许可证](https://img.shields.io/badge/许可证-MIT-orange.svg)](LICENSE)

一个基于 PySide6 和 scrcpy 的手机屏幕推流工具，支持 H.264 编码、实时解码、低延迟推流（<100ms）。

## ✨ 功能特性

### 核心功能
- ✅ **H.264 实时解码**：使用 PyAV 库解码 H.264 裸流
- ✅ **低延迟推流**：延迟 <100ms，真正的实时推流
- ✅ **Socket 协议实现**：手动实现 scrcpy socket 协议
- ✅ **ADB reverse 连接**：使用 ADB reverse 实现稳定连接

### 参数配置
- ✅ **分辨率可调**：480p ~ 1920p
- ✅ **码率可调**：1M ~ 20M
- ✅ **帧率可调**：15fps ~ 120fps
- ✅ **编码器选择**：H.264 / H.265

### 界面功能
- ✅ **实时视频显示**：嵌入式视频显示，无独立窗口
- ✅ **运行日志**：实时显示推流状态和错误信息
- ✅ **状态指示**：设备名称 + 连接状态指示灯
- ✅ **配置保存**：自动保存参数和窗口状态（防抖优化）
- ✅ **自动检测设备**：启动时自动检测设备连接状态
- ✅ **自动重连**：推流中断时自动尝试恢复（最多3次）

### 操作功能
- ✅ **一键截图**：保存当前画面为 PNG 文件（支持 `Ctrl+S` 快捷键）
- ✅ **自动命名**：时间戳命名，无需手动输入文件名
- ✅ **高清保存**：PNG 格式无损画质，保留原始分辨率

## 📋 环境要求

### 必需软件

1. **Python 3.8+**
2. **ADB** (Android Debug Bridge)
3. **scrcpy-server** (已包含在 `tools/` 目录)

### Python 依赖

```bash
pip install -r requirements.txt
```

依赖列表：
- PySide6 >= 6.6.0
- opencv-python >= 4.8.0
- numpy >= 1.24.0
- av >= 10.0.0

## 🚀 使用方法

### 1. 准备工作

1. **手机设置**：
   - 开启开发者模式
   - 启用 USB 调试
   - 连接电脑时选择"传输文件"模式
   - 允许 USB 调试授权

2. **放置 scrcpy**：
   - 确保 `tools/` 目录下有 `scrcpy-server` 文件

### 2. 运行程序

```bash
python main.py
```

### 3. 操作步骤

1. 在界面中选择推流参数（分辨率、码率、帧率、编码器）

2. 点击"▶ 开始推流"

3. 等待几秒后，手机画面将显示在界面中

4. **截图操作**：
   - 点击"📷 截图"按钮保存当前画面
   - 或使用快捷键 `Ctrl+S` 快速截图
   - 截图自动保存到 `screenshots/` 目录

5. 点击"■ 停止推流"结束推流

## 📖 参数说明

### 视频参数

| 参数 | 范围 | 推荐值 | 说明 |
|------|------|--------|------|
| 分辨率 | 480p ~ 1920p | 720p | 越高越清晰但延迟可能增加 |
| 码率 | 1M ~ 20M | 4M | 越高画质越好但带宽需求越大 |
| 帧率 | 15fps ~ 120fps | 30fps | 越高越流畅但CPU占用越大 |
| 编码器 | H.264 / H.265 | H.264 | H.265压缩率更高但兼容性稍差 |

## 🏗️ 项目结构

```
Scrcpy/
├── src/                    # 源代码
│   ├── core/              # 核心模块
│   │   ├── __init__.py
│   │   └── streamer.py    # 推流核心逻辑
│   ├── ui/                # UI 模块
│   │   ├── __init__.py
│   │   ├── main_window.py # 主窗口
│   │   └── video_display.py # 视频显示组件
│   ├── utils/             # 工具模块
│   │   ├── __init__.py
│   │   ├── config.py      # 配置管理
│   │   ├── adb.py         # ADB 工具
│   │   ├── device_monitor.py # 设备监控
│   │   └── stream_manager.py # 推流管理
│   └── __init__.py
├── tools/                 # 工具目录
│   └── scrcpy-win64-v3.3.4/
│       ├── adb.exe
│       └── scrcpy-server
├── screenshots/           # 截图保存目录
│   └── screenshot_*.png  # 自动生成的截图文件
├── docs/                  # 文档目录
│   ├── ARCHITECTURE.md   # 架构文档
│   └── DEVELOPMENT.md    # 开发文档
├── tests/                 # 测试目录
├── main.py               # 主程序入口
├── requirements.txt      # Python 依赖
├── config.json          # 配置文件
└── README.md            # 说明文档
```

## 🔧 技术架构

### 连接流程

```
客户端                    ADB                    手机
  │                        │                      │
  ├─ 创建 TCP server ─────┤                      │
  ├─ 设置 ADB reverse ────┤                      │
  │                        ├─ 转发 socket ──────►│
  │                        │                      │
  │                        │    启动 server ─────┤
  │                        │                      │
  │◄───── 等待连接 ────────┤◄───── 连接 ─────────┤
  │                        │                      │
  ├◄──── 接收 H.264 流 ────┤◄───── 推送数据 ─────┤
  │                        │                      │
  ├─ 解码显示 ─────────────┤                      │
```

### 数据流程

```
手机屏幕
  ↓
scrcpy-server (H.264 编码)
  ↓
Socket 传输 (H.264 裸流)
  ↓
PyAV 解码 (H.264 → BGR)
  ↓
OpenCV 处理
  ↓
PySide6 显示
```

## 🐛 常见问题

### 1. 检测不到手机
- 确保 USB 已连接且开启调试模式
- 运行 `adb devices` 检查设备
- 授权 USB 调试弹窗

### 2. 推流失败
- 确保 `tools/` 目录有 `scrcpy-server`
- 检查 scrcpy 版本是否兼容
- 查看日志输出错误信息

### 3. 画面卡顿
- 降低分辨率（720p）
- 降低码率（2M 以下）
- 降低帧率（30fps）

### 4. 画面延迟高
- 使用"低延迟"预设
- 检查网络连接质量
- 关闭其他占用带宽的应用

### 5. 截图失败
- 确保推流已启动（截图按钮启用状态）
- 检查 `screenshots/` 目录是否有写入权限
- 查看日志输出错误信息

## 📝 开发说明

### 核心类

- `ScrcpySocketThread`: 推流线程核心逻辑
- `ScrcpyGUI`: 主窗口界面、参数配置、操作区域管理
- `VideoDisplayLabel`: 视频显示组件、帧渲染、截图功能
- `ConfigManager`: 配置管理器

### 关键信号

```python
# ScrcpySocketThread 信号
frame_ready = Signal(np.ndarray)    # 帧数据 → VideoDisplayLabel.update_frame()
error_occurred = Signal(str)        # 错误 → ScrcpyGUI._on_error()
status_changed = Signal(str)        # 状态 → ScrcpyGUI._on_status()
```

### 截图实现

```python
# VideoDisplayLabel 维护当前帧
self.current_frame = None

# 更新帧时保存副本
def update_frame(self, frame):
    self.current_frame = frame.copy()
    # ... 显示逻辑

# 截图保存
def capture_screenshot(self):
    cv2.imwrite(f"screenshots/screenshot_{timestamp}.png", self.current_frame)
```

### 扩展方向

- [ ] 支持触摸屏控制
- [x] 支持截图和保存（已完成）
- [ ] 支持录制视频
- [ ] 支持无线连接（TCP/IP）
- [ ] 支持多设备同时推流
- [ ] 添加音频支持

## 📄 许可证

本项目基于 MIT 许可证开源

## 🔗 参考链接

- [scrcpy 官方仓库](https://github.com/Genymobile/scrcpy)
- [PySide6 文档](https://doc.qt.io/qtforpython/)
- [OpenCV 文档](https://docs.opencv.org/)
- [PyAV 文档](https://pyav.org/)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请提交 Issue。
