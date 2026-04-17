"""
Scrcpy 核心推流模块
实现 H.264 流接收和解码
"""

import subprocess
import socket
import time
import secrets
import av
import numpy as np
from PySide6.QtCore import QThread, Signal

from ..utils import logger
from ..utils.subprocess_compat import subprocess_kwargs
from .scrcpy_metadata import parse_device_name, parse_codec_meta


class ScrcpySocketThread(QThread):
    """
    scrcpy socket 推流线程

    工作流程：
    1. 推送 scrcpy-server 到手机
    2. 设置 ADB reverse 端口转发
    3. 启动 scrcpy-server 并建立 socket 连接
    4. 接收 H.264 裸流
    5. 使用 PyAV 解码
    6. 输出帧到 GUI
    """

    frame_ready = Signal(np.ndarray)
    error_occurred = Signal(str)
    status_changed = Signal(str)

    def __init__(self, adb_path, scrcpy_server_path, bitrate="4M", max_fps=30, max_size=1080, codec="H.264"):
        super().__init__()
        self.adb_path = adb_path
        self.scrcpy_server_path = scrcpy_server_path
        self.bitrate = bitrate
        self.max_fps = max_fps
        self.max_size = max_size
        self.codec = codec
        self.running = False
        self.server_process = None
        self.server_sock = None
        self.sock = None
        self.control_sock = None
        self.scid = None

    def run(self):
        """启动推流"""
        self.running = True

        try:
            # 1. 检查设备
            self.status_changed.emit("检查设备连接...")
            logger.info("开始推流流程")
            if not self._adb_cmd("devices").stdout:
                self.error_occurred.emit("ADB 命令失败")
                logger.error("ADB 命令失败")
                return

            # 2. 推送 server
            self.status_changed.emit("推送 scrcpy-server...")
            result = self._adb_cmd("push", self.scrcpy_server_path, "/data/local/tmp/scrcpy-server.jar")
            if result.returncode != 0:
                self.error_occurred.emit(f"推送失败: {result.stderr.decode()}")
                return

            # 3. 生成 session ID (31-bit random number, formatted as hex)
            # scrcpy expects a hex string representing a 31-bit integer
            scid_value = secrets.randbits(31)  # 31-bit random number
            self.scid = f"{scid_value:x}"  # Convert to hex string (lowercase)
            self.status_changed.emit(f"Session ID: {self.scid}")
            logger.debug(f"生成 Session ID: {self.scid} (decimal: {scid_value})")

            # 4. 设置 ADB reverse
            self.status_changed.emit("设置 ADB reverse...")
            self._adb_cmd("reverse", "--remove-all")

            socket_name = f"scrcpy_{self.scid}"
            local_port = 27183
            result = self._adb_cmd("reverse", f"localabstract:{socket_name}", f"tcp:{local_port}")
            if result.returncode != 0:
                self.error_occurred.emit("ADB reverse 失败")
                return

            self.status_changed.emit(f"✓ ADB reverse 已设置: {socket_name}")

            # 等待 ADB reverse 完全生效（关键：避免竞争条件）
            time.sleep(0.5)

            # 5. 创建 TCP server 并监听
            self.status_changed.emit("创建 TCP server...")
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind(("127.0.0.1", local_port))
            self.server_sock.listen(2)
            self.server_sock.settimeout(10.0)
            self.status_changed.emit("✓ TCP server 已启动")

            # 确保 TCP server 完全准备好（避免竞争条件）
            time.sleep(0.3)

            # 6. 启动 server
            self.status_changed.emit("启动 scrcpy-server...")
            self._start_server()

            # 7. 等待 server 连接
            self.status_changed.emit("等待视频流连接...")
            logger.info("等待视频流连接...")
            try:
                self.sock, _ = self.server_sock.accept()
                self.status_changed.emit("✓ 视频流连接已建立")
                logger.info("视频流连接已建立")

                self.status_changed.emit("等待控制流连接...")
                self.control_sock, _ = self.server_sock.accept()
                self.status_changed.emit("✓ 控制流连接已建立")
                logger.info("控制流连接已建立")
            except socket.timeout:
                self.error_occurred.emit("等待连接超时")
                logger.error("等待连接超时")
                return
            except Exception as e:
                self.error_occurred.emit(f"连接失败: {str(e)}")
                logger.error(f"连接失败: {str(e)}")
                return

            # 8. 接收元数据
            self.status_changed.emit("接收设备信息...")
            device_info = self._recv_metadata()
            if not device_info:
                self.error_occurred.emit("接收设备信息失败")
                return

            # 9. 解码 H.264 流
            self.status_changed.emit("开始解码 H.264 流...")
            self._decode_h264_stream()

        except Exception as e:
            self.error_occurred.emit(f"推流失败: {str(e)}")
        finally:
            self._cleanup()

    def _adb_cmd(self, *args, timeout=10):
        """执行 ADB 命令"""
        cmd = [self.adb_path] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            **subprocess_kwargs()
        )

    def _start_server(self):
        """启动 scrcpy-server"""
        # 解析码率
        if self.bitrate.endswith("M"):
            bitrate_val = int(float(self.bitrate[:-1]) * 1000000)
        elif self.bitrate.endswith("K"):
            bitrate_val = int(float(self.bitrate[:-1]) * 1000)
        else:
            bitrate_val = int(self.bitrate)

        # 解析编码格式
        codec_name = "h265" if self.codec == "H.265" else "h264"

        # scrcpy 3.3.4 server 启动参数（优化画质）
        server_cmd = (
            f"CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / "
            f"com.genymobile.scrcpy.Server 3.3.4 "
            f"scid={self.scid} "
            f"log_level=info "
            f"max_size={self.max_size} "
            f"video_bit_rate={bitrate_val} "
            f"max_fps={self.max_fps} "
            f"video_codec={codec_name} "
            f"video_source=display "
            f"send_frame_meta=true "
            f"audio=false"
        )

        self.status_changed.emit(f"启动命令: {server_cmd[:100]}...")

        self.server_process = subprocess.Popen(
            [self.adb_path, "shell", server_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **subprocess_kwargs()
        )

        # 等待 server 启动 - 2秒是经验值，确保 server 进程完成初始化
        time.sleep(2)

        if self.server_process.poll() is not None:
            stderr = self.server_process.stderr.read().decode('utf-8', errors='ignore')
            self.status_changed.emit(f"server 退出: {stderr[:300]}")

    def _recv_exact(self, size):
        """精确接收指定大小的数据"""
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _recv_metadata(self):
        """
        接收设备元数据（scrcpy 3.x 协议 - reverse 模式）

        协议格式（reverse 模式，dummy byte 可选）：
        1. 可选 dummy byte (1字节, 0x00)
        2. 设备名 (64字节, null-terminated) - 在第一个 socket 上发送
        3. 视频流元数据 (12字节):
           - codec_id (4字节, big-endian uint32)
           - video_width (4字节, big-endian uint32)
           - video_height (4字节, big-endian uint32)
        """
        try:
            first = self._recv_exact(1)
            if not first:
                self.status_changed.emit("元数据接收错误: 设备名读取失败")
                return None

            if first == b"\x00":
                name_data = self._recv_exact(64)
                if not name_data:
                    self.status_changed.emit("元数据接收错误: 设备名读取失败")
                    return None
            else:
                rest = self._recv_exact(63)
                if not rest:
                    self.status_changed.emit("元数据接收错误: 设备名读取失败")
                    return None
                name_data = first + rest

            device_name = parse_device_name(name_data)
            logger.info(f"设备名: {device_name}")

            # 接收视频流元数据（12字节）
            codec_meta = self._recv_exact(12)
            if not codec_meta:
                self.status_changed.emit("元数据接收错误: 视频元数据读取失败")
                return None

            codec_id, video_width, video_height = parse_codec_meta(codec_meta)

            logger.info(f"Codec ID: {codec_id}, 分辨率: {video_width}x{video_height}")

            self.status_changed.emit(f"✓ 设备: {device_name}")
            self.status_changed.emit(f"✓ 屏幕: {video_width}x{video_height}")

            return {
                "name": device_name,
                "width": video_width,
                "height": video_height
            }
        except Exception as e:
            self.status_changed.emit(f"元数据接收错误: {str(e)}")
            logger.error(f"元数据接收异常: {str(e)}", exc_info=True)
            return None

    def _decode_h264_stream(self):
        """解码 H.264 流"""
        codec = av.CodecContext.create("h264", "r")

        buffer = b""
        frame_count = 0
        last_fps_time = time.time()
        fps_count = 0
        MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB buffer 上限

        while self.running:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    self.status_changed.emit("视频流断开")
                    break

                buffer += chunk

                # 防止 buffer 无限增长
                if len(buffer) > MAX_BUFFER_SIZE:
                    logger.warning(f"Buffer 超过 {MAX_BUFFER_SIZE} 字节，清空")
                    buffer = b""
                    continue

                # 查找 NALU 起始码
                while True:
                    pos1 = buffer.find(b"\x00\x00\x00\x01")
                    pos2 = buffer.find(b"\x00\x00\x01")

                    if pos1 == -1 and pos2 == -1:
                        break

                    if pos1 == -1:
                        start_pos = pos2
                        start_len = 3
                    elif pos2 == -1:
                        start_pos = pos1
                        start_len = 4
                    else:
                        start_pos = min(pos1, pos2)
                        start_len = 4 if pos1 < pos2 else 3

                    next_pos1 = buffer.find(b"\x00\x00\x00\x01", start_pos + start_len)
                    next_pos2 = buffer.find(b"\x00\x00\x01", start_pos + start_len)

                    if next_pos1 == -1 and next_pos2 == -1:
                        break

                    next_pos = min(next_pos1, next_pos2) if next_pos1 != -1 and next_pos2 != -1 else (next_pos1 if next_pos1 != -1 else next_pos2)

                    nalu = buffer[start_pos:next_pos]
                    buffer = buffer[next_pos:]

                    try:
                        packet = av.Packet(nalu)
                        for frame in codec.decode(packet):
                            img = frame.to_ndarray(format="bgr24")
                            self.frame_ready.emit(img)

                            frame_count += 1
                            fps_count += 1

                            # 仅每秒更新一次 FPS
                            current_time = time.time()
                            if current_time - last_fps_time >= 1.0:
                                fps = fps_count / (current_time - last_fps_time)
                                self.status_changed.emit(f"推流中 | 帧数: {frame_count} | FPS: {fps:.1f}")
                                fps_count = 0
                                last_fps_time = current_time
                    except (av.error.InvalidDataError, av.error.FFmpegError) as e:
                        # 解码错误通常可以忽略，继续处理下一帧
                        logger.debug(f"解码帧失败: {type(e).__name__}")
                    except Exception as e:
                        logger.warning(f"解码异常: {type(e).__name__}: {str(e)}")

            except socket.timeout:
                continue
            except Exception as e:
                self.status_changed.emit(f"接收错误: {str(e)}")
                logger.error(f"接收错误: {str(e)}")
                time.sleep(0.1)

        self.status_changed.emit(f"推流结束，总帧数: {frame_count}")

    def _cleanup(self):
        """清理资源"""
        self.running = False

        # 关闭 socket 连接
        for sock in [self.sock, self.control_sock, self.server_sock]:
            if sock:
                try:
                    sock.close()
                except (OSError, IOError):
                    pass

        # 终止 server 进程
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            except Exception as e:
                logger.warning(f"终止 server 进程失败: {str(e)}")

        # 清理 ADB reverse
        try:
            self._adb_cmd("reverse", "--remove-all")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            logger.debug(f"清理 ADB reverse 失败: {str(e)}")

        # 删除临时文件
        try:
            self._adb_cmd("shell", "rm", "-f", "/data/local/tmp/scrcpy-server.jar")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            logger.debug(f"删除临时文件失败: {str(e)}")

    def stop(self):
        """停止推流"""
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except (OSError, IOError):
                pass
