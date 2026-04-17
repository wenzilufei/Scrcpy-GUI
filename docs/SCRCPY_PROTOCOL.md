# Scrcpy 协议实现文档

## 协议概述

本文档详细说明 Scrcpy 3.3.4 协议的实现细节，包括连接建立、数据传输、视频解码等核心流程。

---

## 一、协议架构

### 1.1 连接模式

**ADB Reverse 模式**（客户端主动监听，服务端主动连接）

```
┌─────────────┐                    ┌─────────────┐
│   客户端     │                    │   手机端     │
│  (PC)       │                    │             │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ 1. 创建 TCP Server               │
       │    (127.0.0.1:27183)            │
       │                                  │
       │ 2. 设置 ADB Reverse             │
       ├─────────────────────────────────►│
       │    localabstract:scrcpy_xxx     │
       │    → tcp:27183                  │
       │                                  │
       │ 3. 启动 scrcpy-server           │
       ├─────────────────────────────────►│
       │                                  │
       │ 4. Server 连接到 Socket         │
       │◄─────────────────────────────────┤
       │    (视频流连接)                  │
       │                                  │
       │ 5. Server 连接到 Socket         │
       │◄─────────────────────────────────┤
       │    (控制流连接)                  │
       │                                  │
       │ 6. 传输 H.264 视频流            │
       │◄─────────────────────────────────┤
       │                                  │
```

**关键点**：
- 客户端创建 TCP Server 并监听端口
- 使用 ADB Reverse 建立抽象套接字到 TCP 端口的映射
- scrcpy-server 启动后主动连接客户端的 Socket
- 需要建立两个 Socket 连接：视频流 + 控制流

---

## 二、协议参数

### 2.1 会话标识符 (Session ID)

**参数名称**: `scid`

**格式**: 8位十六进制字符串

**示例**: `scid=0fc8e660`

**生成方式**:
```python
scid = "%08x" % random.randint(0, 0x7FFFFFFF)
```

**作用**:
- 标识唯一的推流会话
- 用于构建套接字名称：`scrcpy_{scid}`
- 必须在设置 ADB Reverse **之前**生成

---

### 2.2 视频参数

| 参数名称 | 参数标识 | 数据类型 | 示例值 | 说明 |
|---------|---------|---------|--------|------|
| 最大分辨率 | `max_size` | 整数 | 1080 | 视频最大宽/高 |
| 视频码率 | `video_bit_rate` | 整数 | 4000000 | 码率（bps） |
| 最大帧率 | `max_fps` | 整数 | 30 | 最大 FPS |
| 音频开关 | `audio` | 布尔 | false | 是否启用音频 |
| 日志级别 | `log_level` | 字符串 | info | Server 日志级别 |

**码率转换规则**:
```python
# "4M" → 4000000 bps
if bitrate.endswith("M"):
    bitrate_val = int(float(bitrate[:-1]) * 1000000)
elif bitrate.endswith("K"):
    bitrate_val = int(float(bitrate[:-1]) * 1000)
else:
    bitrate_val = int(bitrate)
```

---

## 三、连接建立流程

### 3.1 步骤一：推送服务端文件

**命令**:
```bash
adb push scrcpy-server /data/local/tmp/scrcpy-server.jar
```

**目标路径**: `/data/local/tmp/scrcpy-server.jar`

**权限**: 需要写入 `/data/local/tmp/` 目录的权限

---

### 3.2 步骤二：生成会话标识符

**实现**:
```python
scid = "%08x" % random.randint(0, 0x7FFFFFFF)
```

**格式要求**:
- 必须是 8 位十六进制字符串
- 取值范围：`00000000` ~ `7FFFFFFF`
- 每次推流会话使用唯一标识符

---

### 3.3 步骤三：设置 ADB Reverse

**清除旧的映射**:
```bash
adb reverse --remove-all
```

**创建新的映射**:
```bash
adb reverse localabstract:scrcpy_{scid} tcp:27183
```

**参数说明**:
- `localabstract:scrcpy_{scid}`: Android 端的抽象套接字名称
- `tcp:27183`: PC 端的 TCP 端口号

**映射关系**:
```
Android 端                    PC 端
localabstract:scrcpy_xxx  →  127.0.0.1:27183
```

---

### 3.4 步骤四：创建 TCP Server

**实现**:
```python
# 创建 Socket
server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# 绑定端口
server_sock.bind(("127.0.0.1", 27183))

# 监听连接（最多 2 个：视频流 + 控制流）
server_sock.listen(2)

# 设置超时
server_sock.settimeout(10.0)
```

**关键参数**:
- 绑定地址：`127.0.0.1`（本地回环）
- 监听端口：`27183`（可自定义）
- 监听队列：`2`（视频流 + 控制流）
- 超时时间：`10.0` 秒

---

### 3.5 步骤五：启动服务端

**命令格式**:
```bash
CLASSPATH=/data/local/tmp/scrcpy-server.jar \
app_process / com.genymobile.scrcpy.Server 3.3.4 \
scid={scid} \
log_level=info \
max_size={max_size} \
video_bit_rate={bitrate_val} \
max_fps={max_fps} \
audio=false
```

**完整示例**:
```bash
adb shell \
"CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / \
com.genymobile.scrcpy.Server 3.3.4 \
scid=0fc8e660 \
log_level=info \
max_size=1080 \
video_bit_rate=4000000 \
max_fps=30 \
audio=false"
```

**启动延迟**:
- 需要等待 2 秒让服务端完成初始化
- 检查进程是否意外退出

---

### 3.6 步骤六：接受连接

**视频流连接**:
```python
sock, _ = server_sock.accept()  # 第一个连接是视频流
```

**控制流连接**:
```python
control_sock, _ = server_sock.accept()  # 第二个连接是控制流
```

**连接顺序**:
1. 视频流连接（用于传输 H.264 视频数据）
2. 控制流连接（用于传输控制命令，本项目未使用）

---

## 四、数据传输协议

### 4.1 元数据接收

**Dummy Byte**:
- 第一个字节必须是 `0x00`
- 用于同步协议版本

**实现**:
```python
dummy = sock.recv(1)
if dummy != b'\x00':
    # 警告：协议版本可能不匹配
```

**设备信息**（简化实现）:
```python
device_info = {
    "name": "Android Device",
    "width": max_size,
    "height": max_size
}
```

---

### 4.2 H.264 视频流接收

#### 4.2.1 数据格式

**H.264 裸流**（Raw H.264 Stream）

- 无容器封装（无 MP4/MKV）
- 直接传输 NALU（Network Abstraction Layer Unit）
- 使用起始码分隔 NALU

#### 4.2.2 NALU 起始码

**两种起始码格式**:

| 起始码 | 十六进制 | 使用场景 |
|--------|---------|---------|
| 4字节起始码 | `00 00 00 01` | 常见格式 |
| 3字节起始码 | `00 00 01` | 部分场景 |

**查找起始码**:
```python
pos1 = buffer.find(b"\x00\x00\x00\x01")  # 4字节起始码
pos2 = buffer.find(b"\x00\x00\x01")      # 3字节起始码

# 选择最早出现的起始码
if pos1 == -1:
    start_pos = pos2
    start_len = 3
elif pos2 == -1:
    start_pos = pos1
    start_len = 4
else:
    start_pos = min(pos1, pos2)
    start_len = 4 if pos1 < pos2 else 3
```

#### 4.2.3 NALU 提取流程

```
接收数据 → 查找起始码 → 提取 NALU → 解码 → 显示
   ↓           ↓           ↓         ↓       ↓
 Buffer    定位边界    切分数据   PyAV   QImage
```

**实现**:
```python
buffer = b""
MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB 上限

while running:
    # 接收数据块
    chunk = sock.recv(65536)
    buffer += chunk

    # 防止内存泄漏
    if len(buffer) > MAX_BUFFER_SIZE:
        buffer = b""
        continue

    # 查找 NALU 起始码
    while True:
        # 查找当前起始码
        start_pos, start_len = find_start_code(buffer)

        # 查找下一个起始码
        next_pos = find_next_start_code(buffer, start_pos + start_len)

        if next_pos == -1:
            break  # 数据不完整，等待更多数据

        # 提取 NALU
        nalu = buffer[start_pos:next_pos]
        buffer = buffer[next_pos:]

        # 解码 NALU
        decode_nalu(nalu)
```

---

## 五、视频解码协议

### 5.1 解码器初始化

**使用 PyAV 库**:
```python
import av

codec = av.CodecContext.create("h264", "r")
```

**参数说明**:
- 编码格式：`h264`
- 解码方向：`"r"`（读取/解码）

---

### 5.2 NALU 解码

**解码流程**:
```python
# 创建数据包
packet = av.Packet(nalu)

# 解码为帧
for frame in codec.decode(packet):
    # 转换为 BGR 格式
    img = frame.to_ndarray(format="bgr24")

    # 发送到显示模块
    frame_ready.emit(img)
```

**异常处理**:
```python
try:
    packet = av.Packet(nalu)
    for frame in codec.decode(packet):
        img = frame.to_ndarray(format="bgr24")
        frame_ready.emit(img)
except av.error.InvalidDataError:
    # 解码数据无效，跳过此帧
    logger.debug("解码帧失败: InvalidDataError")
except av.error.FFmpegError as e:
    # FFmpeg 错误，记录并继续
    logger.warning(f"解码异常: {e}")
```

---

### 5.3 帧格式转换

**输出格式**: BGR24

**数据类型**: `numpy.ndarray`

**维度顺序**: `[高度, 宽度, 通道]`

**示例**:
```python
# 原始帧: 1920x1080
img.shape  # (1080, 1920, 3)
img.dtype  # uint8
```

---

## 六、资源清理协议

### 6.1 清理顺序

```
1. 关闭视频流 Socket
2. 关闭控制流 Socket
3. 关闭 Server Socket
4. 终止服务端进程
5. 清理 ADB Reverse
6. 删除临时文件
```

---

### 6.2 清理实现

#### 6.2.1 关闭 Socket 连接

```python
for sock in [sock, control_sock, server_sock]:
    if sock:
        try:
            sock.close()
        except (OSError, IOError):
            pass
```

---

#### 6.2.2 终止服务端进程

```python
if server_process and server_process.poll() is None:
    # 发送 SIGTERM
    server_process.terminate()

    try:
        # 等待 3 秒
        server_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        # 强制终止
        server_process.kill()
```

---

#### 6.2.3 清理 ADB Reverse

```python
try:
    adb_cmd("reverse", "--remove-all")
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
    pass
```

---

#### 6.2.4 删除临时文件

```python
try:
    adb_cmd("shell", "rm", "-f", "/data/local/tmp/scrcpy-server.jar")
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
    pass
```

---

## 七、性能优化协议

### 7.1 Buffer 管理

**上限设置**: 10MB

**溢出处理**: 清空 Buffer

**实现**:
```python
MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB

if len(buffer) > MAX_BUFFER_SIZE:
    logger.warning(f"Buffer 超过 {MAX_BUFFER_SIZE} 字节，清空")
    buffer = b""
    continue
```

---

### 7.2 FPS 计算

**更新频率**: 每秒一次

**实现**:
```python
last_fps_time = time.time()
fps_count = 0

# 每帧计数
fps_count += 1

# 每秒更新
current_time = time.time()
if current_time - last_fps_time >= 1.0:
    fps = fps_count / (current_time - last_fps_time)
    print(f"FPS: {fps:.1f}")
    fps_count = 0
    last_fps_time = current_time
```

---

## 八、错误处理协议

### 8.1 连接错误

| 错误类型 | 检测方式 | 处理方法 |
|---------|---------|---------|
| 设备未连接 | `adb devices` 检查 | 提示用户连接设备 |
| ADB 命令失败 | 返回码非 0 | 记录错误并终止 |
| Socket 连接超时 | 10 秒超时 | 提示超时并清理资源 |
| 服务端启动失败 | 进程意外退出 | 记录 stderr 并终止 |

---

### 8.2 解码错误

| 错误类型 | 异常类 | 处理方法 |
|---------|--------|---------|
| 数据无效 | `av.error.InvalidDataError` | 跳过当前帧 |
| FFmpeg 错误 | `av.error.FFmpegError` | 记录并继续 |
| 其他异常 | `Exception` | 记录警告并继续 |

---

## 九、协议版本兼容性

### 9.1 当前实现版本

**Scrcpy 版本**: 3.3.4

**协议特性**:
- ✅ 支持会话标识符（scid）
- ✅ 支持 ADB Reverse 模式
- ✅ 支持 H.264 视频编码
- ✅ 支持双 Socket 连接
- ❌ 不支持音频传输
- ❌ 不支持控制命令

---

### 9.2 版本检测

**Dummy Byte 检测**:
```python
dummy = sock.recv(1)
if dummy != b'\x00':
    print(f"警告: 协议版本可能不匹配，收到 {dummy.hex()}")
```

---

## 十、协议扩展

### 10.1 支持控制命令

**控制流 Socket**: `control_sock`

**命令格式**: 二进制协议（未实现）

**潜在用途**:
- 触摸屏控制
- 键盘输入
- 剪贴板同步

---

### 10.2 支持音频传输

**参数修改**:
```python
audio=true
```

**音频解码**: 需要 AAC 解码器

---

## 十一、调试技巧

### 11.1 查看 ADB Reverse 映射

```bash
adb reverse --list
```

**输出示例**:
```
localabstract:scrcpy_0fc8e660 tcp:27183
```

---

### 11.2 查看服务端日志

**服务端输出**:
```python
stderr = server_process.stderr.read().decode('utf-8', errors='ignore')
print(stderr)
```

---

### 11.3 测试 Socket 连接

**使用 netstat**:
```bash
netstat -an | grep 27183
```

**预期输出**:
```
TCP    127.0.0.1:27183        0.0.0.0:0              LISTENING
```

---

## 十二、常见问题

### 12.1 连接被拒绝

**原因**: scid 格式错误或 ADB Reverse 未设置

**解决**:
1. 检查 scid 是否为 8 位十六进制
2. 检查 ADB Reverse 是否成功设置
3. 确认服务端已启动

---

### 12.2 视频流断开

**原因**: Buffer 溢出或网络问题

**解决**:
1. 检查 Buffer 大小限制
2. 降低视频码率
3. 检查 USB 连接质量

---

### 12.3 解码失败

**原因**: NALU 数据不完整或格式错误

**解决**:
1. 检查起始码查找逻辑
2. 增加异常处理
3. 记录错误帧用于分析

---

## 十三、参考资料

### 13.1 官方文档

- [Scrcpy GitHub](https://github.com/Genymobile/scrcpy)
- [Scrcpy Server 源码](https://github.com/Genymobile/scrcpy/tree/master/server)

### 13.2 相关协议

- **H.264 标准**: ITU-T H.264 / ISO/IEC 14496-10
- **ADB 协议**: Android Debug Bridge Protocol
- **Socket 编程**: BSD Socket API

### 13.3 依赖库

- **PyAV**: FFmpeg Python 绑定
- **OpenCV**: 图像处理库
- **NumPy**: 数值计算库

---

## 十四、协议总结

### 14.1 核心要点

1. **ADB Reverse 模式**: 客户端监听，服务端连接
2. **会话标识符**: 8 位十六进制，唯一标识推流会话
3. **双 Socket 连接**: 视频流 + 控制流
4. **H.264 裸流**: 无容器封装，直接传输 NALU
5. **起始码分隔**: `00 00 00 01` 或 `00 00 01`
6. **PyAV 解码**: 实时解码 H.264 帧
7. **资源清理**: 按顺序关闭连接和进程

### 14.2 性能优化

- Buffer 限制 10MB 防止内存泄漏
- FPS 计算每秒更新一次
- 异常处理捕获具体类型
- 配置保存使用防抖机制

### 14.3 扩展方向

- 支持触摸屏控制
- 支持音频传输
- 支持无线连接（TCP/IP）
- 支持多设备同时推流

---

**文档版本**: 1.0
**最后更新**: 2026-04-16
**适用版本**: Scrcpy 3.3.4
