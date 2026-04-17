# 开发文档

## 开发环境设置

### 1. 安装 Python

确保安装 Python 3.8 或更高版本：

```bash
python --version
```

### 2. 克隆项目

```bash
git clone <repository-url>
cd Scrcpy
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 准备工具

确保 `tools/` 目录包含：
- `adb.exe`
- `scrcpy-server`

## 项目结构

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
├── docs/                  # 文档目录
├── tests/                 # 测试目录
├── main.py               # 主程序入口
├── requirements.txt      # Python 依赖
└── config.json          # 配置文件
```

## 核心类说明

### ScrcpySocketThread

**位置**: `src/core/streamer.py`

**职责**: 推流线程核心逻辑

**关键方法**:

```python
def run(self):
    """启动推流主流程"""

def _adb_cmd(self, *args, timeout=10):
    """执行 ADB 命令"""

def _start_server(self):
    """启动 scrcpy-server"""

def _decode_h264_stream(self):
    """解码 H.264 流"""

def _cleanup(self):
    """清理资源"""
```

**信号**:

```python
frame_ready = Signal(np.ndarray)    # 帧数据就绪
error_occurred = Signal(str)        # 错误发生
status_changed = Signal(str)        # 状态变化
```

### ScrcpyGUI

**位置**: `src/ui/main_window.py`

**职责**: 主窗口界面管理

**关键方法**:

```python
def _setup_ui(self):
    """设置界面"""

def _load_config(self):
    """加载配置"""

def _save_config(self):
    """保存配置"""

def _on_start(self):
    """开始推流"""

def _on_stop(self):
    """停止推流"""

def _apply_preset(self, preset_name):
    """应用预设"""
```

### VideoDisplayLabel

**位置**: `src/ui/video_display.py`

**职责**: 视频显示组件

**关键方法**:

```python
def update_frame(self, frame):
    """更新视频帧"""
```

### ConfigManager

**位置**: `src/utils/config.py`

**职责**: 配置管理

**关键方法**:

```python
def load(self):
    """加载配置"""

def save(self, config):
    """保存配置"""
```

### DeviceMonitor

**位置**: `src/utils/device_monitor.py`

**职责**: 设备监控

**关键方法**:

```python
def start(self):
    """开始监控"""

def stop(self):
    """停止监控"""

def get_status(self):
    """获取当前设备状态"""
```

**信号**:

```python
device_connected = Signal(str)      # 设备已连接
device_disconnected = Signal()      # 设备已断开
check_error = Signal(str)           # 检测错误
```

### StreamManager

**位置**: `src/utils/stream_manager.py`

**职责**: 推流管理

**关键方法**:

```python
def start_streaming(self):
    """开始推流"""

def stop_streaming(self):
    """停止推流"""

def on_device_reconnected(self):
    """设备重连时调用"""

def get_status(self):
    """获取当前推流状态"""
```

**信号**:

```python
reconnect_started = Signal(int, int)  # 开始重连
reconnect_success = Signal()          # 重连成功
reconnect_failed = Signal()           # 重连失败
```

### 日志系统

**位置**: `src/utils/logger.py`

**职责**: 统一日志管理

**关键函数**:

```python
def setup_logger(name='Scrcpy', log_file=None, level=logging.INFO):
    """设置日志记录器"""
```

**使用方法**:

```python
from src.utils import logger

logger.info("信息日志")
logger.warning("警告日志")
logger.error("错误日志")
logger.debug("调试日志")
```

**日志格式**:
- 控制台: `[HH:MM:SS] ✓ 消息内容`
- 文件: `[YYYY-MM-DD HH:MM:SS] [LEVEL] 消息内容`

## 开发指南

### 添加新功能

1. **添加新的推流参数**:

   - 在 `ScrcpyGUI._setup_ui()` 中添加 UI 控件
   - 在 `ScrcpySocketThread._start_server()` 中添加参数
   - 配置会自动保存（防抖 1 秒）

2. **修改默认参数**:

   在 `ScrcpyGUI._setup_ui()` 中修改默认值：
   ```python
   self.resolution.setCurrentText("1080")  # 修改默认分辨率
   self.bitrate.setCurrentText("8M")       # 修改默认码率
   ```

3. **添加新的编码器**:

   - 在 UI 中添加选项
   - 修改 `_start_server()` 参数

### 调试技巧

1. **查看日志**:
   - 查看 GUI 日志输出
   - 查看 scrcpy-server 输出

2. **测试连接**:
   ```python
   # 测试 ADB 连接
   python -c "from src.utils import find_tools; print(find_tools())"
   ```

3. **测试解码**:
   ```python
   # 测试 PyAV 解码
   import av
   codec = av.CodecContext.create("h264", "r")
   ```

### 性能优化

1. **降低延迟**:
   - 减小分辨率
   - 降低码率
   - 使用 H.264 编码

2. **提高画质**:
   - 增加码率
   - 提高分辨率
   - 使用 H.265 编码

3. **减少 CPU 占用**:
   - 降低帧率
   - 减小分辨率
   - 使用硬件加速

4. **内存优化**:
   - Buffer 限制 10MB 防止内存泄漏
   - 配置保存防抖避免频繁 IO
   - FPS 计算每秒更新一次

## 测试

### 单元测试

创建测试文件 `tests/test_streamer.py`:

```python
import unittest
from src.core import ScrcpySocketThread

class TestStreamer(unittest.TestCase):
    def test_init(self):
        streamer = ScrcpySocketThread(
            adb_path="adb.exe",
            scrcpy_server_path="scrcpy-server",
            bitrate="4M",
            max_fps=30,
            max_size=1080
        )
        self.assertIsNotNone(streamer)
```

### 集成测试

```bash
python main.py
```

手动测试：
1. 连接设备
2. 开始推流
3. 检查画面
4. 停止推流

## 发布

### 打包

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

### 发布清单

- [ ] 更新版本号
- [ ] 更新 CHANGELOG
- [ ] 测试所有功能
- [ ] 检查文档
- [ ] 打包可执行文件

## 常见问题

### 1. 导入错误

**问题**: `ModuleNotFoundError: No module named 'src'`

**解决**: 确保在项目根目录运行

### 2. ADB 找不到

**问题**: `FileNotFoundError: adb.exe`

**解决**: 检查 `tools/` 目录

### 3. 解码失败

**问题**: `av.error.InvalidDataError`

**解决**: 检查 H.264 流格式

## 贡献指南

### 代码规范

- 使用 4 空格缩进
- 函数添加文档字符串
- 变量使用蛇形命名
- 类使用驼峰命名

### 提交规范

```
feat: 添加新功能
fix: 修复 bug
docs: 更新文档
style: 代码格式
refactor: 重构
test: 测试
chore: 构建/工具
```

### Pull Request 流程

1. Fork 项目
2. 创建分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

如有问题，请提交 Issue
