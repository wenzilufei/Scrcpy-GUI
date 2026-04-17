"""
UI 设置模块
负责主窗口的界面布局和样式设置
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QComboBox, QGroupBox, QTextEdit, QStatusBar,
    QScrollArea, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QShortcut, QKeySequence, QPainter

from .video_display import VideoDisplayLabel


def setup_ui(main_window):
    """设置主窗口界面"""
    main_window.setWindowTitle("Scrcpy 低延迟推流 (<100ms)")
    main_window.resize(1800, 900)

    main_window.setStyleSheet(_get_stylesheet())

    central = QWidget()
    main_window.setCentralWidget(central)
    
    # 整体布局：左右分栏
    main_layout = QHBoxLayout(central)
    main_layout.setSpacing(5)
    main_layout.setContentsMargins(5, 5, 5, 5)

    # ========== 左栏：主画面 + 参数 + 日志（固定宽度，不随窗口缩放）==========
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)
    left_layout.setSpacing(5)
    left_layout.setContentsMargins(0, 0, 0, 0)
    
    # 关键：左栏使用 Preferred 策略，保持固定宽度
    left_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    # 左栏顶部：主画面（固定宽高比）
    main_window.video = VideoDisplayLabel()
    # 主画面也设置为 Preferred，不随父容器拉伸
    main_window.video.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    left_layout.addWidget(main_window.video)

    # 左栏底部：参数控制 + 日志（水平排列）
    bottom_row = QHBoxLayout()
    bottom_row.setSpacing(10)

    # 推流参数区
    params_group = _create_params_section(main_window)
    params_group.setFixedWidth(420)
    bottom_row.addWidget(params_group)

    # 运行日志区
    log_group = _create_log_section(main_window)
    bottom_row.addWidget(log_group, 1)

    left_layout.addLayout(bottom_row)

    main_layout.addWidget(left_panel)  # 不设置 stretch，保持固定宽度

    # ========== 右栏：小地图+操作(1/3) + 大地图(2/3)（占据剩余空间）==========
    right_panel = QWidget()
    right_layout = QHBoxLayout(right_panel)
    right_layout.setSpacing(5)
    right_layout.setContentsMargins(0, 0, 0, 0)
    
    # 关键：右栏使用 Expanding 策略，占据所有剩余空间
    right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # 左侧：小地图 + 操作区域（占 1/3）
    left_right = QWidget()
    left_right_layout = QVBoxLayout(left_right)
    left_right_layout.setSpacing(5)
    left_right_layout.setContentsMargins(0, 0, 0, 0)
    left_right.setFixedWidth(320)  # 固定宽度

    # 小地图区 (300x300)
    minimap_group = _create_minimap_section(main_window)
    left_right_layout.addWidget(minimap_group)

    # 操作按钮区
    action_group = _create_action_section(main_window)
    left_right_layout.addWidget(action_group)

    right_layout.addWidget(left_right)

    # 右侧：大地图显示区域（占据剩余空间）
    bigmap_group = _create_bigmap_section(main_window)
    right_layout.addWidget(bigmap_group, 1)  # stretch=1 占据剩余空间

    main_layout.addWidget(right_panel, 1)  # stretch=1 让右栏占据所有剩余空间

    # ========== 底部状态栏 ==========
    _create_status_bar(main_window)

    # ========== 信号连接 ==========
    _setup_connections(main_window)


def _create_params_section(main_window):
    """创建推流参数控制区"""
    params_group = QGroupBox("⚙ 推流参数")
    params_layout = QVBoxLayout()
    params_layout.setSpacing(8)

    params_container = QVBoxLayout()
    params_container.setSpacing(8)

    # 第一行：分辨率 | 码率
    params_row1 = QHBoxLayout()
    params_row1.setSpacing(5)

    res_label = QLabel("分辨率:")
    res_label.setStyleSheet("color: #00d4ff; font-weight: bold;")
    res_label.setFixedWidth(50)
    params_row1.addWidget(res_label)
    main_window.resolution = QComboBox()
    main_window.resolution.addItems(["1080", "1920"])
    main_window.resolution.setToolTip("视频分辨率\n1080p: 流畅优先\n1920p: 高清画质\n更高: 极致画质\n\n连接设备后会自动更新为手机最大分辨率")
    main_window.resolution.setFixedWidth(100)
    main_window.resolution.setEditable(True)
    params_row1.addWidget(main_window.resolution)

    params_row1.addSpacing(20)

    bitrate_label = QLabel("码率:")
    bitrate_label.setStyleSheet("color: #00d4ff; font-weight: bold;")
    bitrate_label.setFixedWidth(50)
    params_row1.addWidget(bitrate_label)
    main_window.bitrate = QComboBox()
    main_window.bitrate.addItems(["8M", "16M", "20M", "30M", "40M", "50M"])
    main_window.bitrate.setCurrentText("20M")
    main_window.bitrate.setToolTip("视频码率\n8-16M: 低延迟推荐\n20-30M: 高画质\n40-50M: 极致画质")
    main_window.bitrate.setFixedWidth(80)
    params_row1.addWidget(main_window.bitrate)

    params_row1.addStretch()
    params_container.addLayout(params_row1)

    # 第二行：帧率 | 编码
    params_row2 = QHBoxLayout()
    params_row2.setSpacing(5)

    fps_label = QLabel("帧率:")
    fps_label.setStyleSheet("color: #00d4ff; font-weight: bold;")
    fps_label.setFixedWidth(50)
    params_row2.addWidget(fps_label)
    main_window.fps = QComboBox()
    main_window.fps.addItems(["15", "24", "30", "45", "60", "90", "120"])
    main_window.fps.setCurrentText("30")
    main_window.fps.setToolTip("视频帧率\n30fps: 低延迟稳定\n60fps: 流畅游戏\n120fps: 极致流畅")
    main_window.fps.setFixedWidth(80)
    params_row2.addWidget(main_window.fps)

    params_row2.addSpacing(20)

    codec_label = QLabel("编码:")
    codec_label.setStyleSheet("color: #00d4ff; font-weight: bold;")
    codec_label.setFixedWidth(50)
    params_row2.addWidget(codec_label)
    main_window.codec = QComboBox()
    main_window.codec.addItems(["H.264", "H.265"])
    main_window.codec.setCurrentText("H.264")
    main_window.codec.setToolTip("视频编码\nH.264: 兼容性好\nH.265: 压缩率高")
    main_window.codec.setFixedWidth(80)
    params_row2.addWidget(main_window.codec)

    params_row2.addStretch()
    params_container.addLayout(params_row2)

    params_layout.addLayout(params_container)

    # 按钮区
    btn_layout = QHBoxLayout()
    main_window.start_btn = QPushButton("▶ 开始推流")
    main_window.start_btn.setObjectName("start")
    btn_layout.addWidget(main_window.start_btn)

    main_window.stop_btn = QPushButton("■ 停止推流")
    main_window.stop_btn.setObjectName("stop")
    main_window.stop_btn.setEnabled(False)
    btn_layout.addWidget(main_window.stop_btn)

    params_layout.addLayout(btn_layout)
    params_group.setLayout(params_layout)
    return params_group


def _create_log_section(main_window):
    """创建运行日志区"""
    log_group = QGroupBox("📋 运行日志")
    log_layout = QVBoxLayout()
    main_window.log = QTextEdit()
    main_window.log.setReadOnly(True)
    log_layout.addWidget(main_window.log)
    log_group.setLayout(log_layout)
    return log_group


def _create_minimap_section(main_window):
    """创建小地图显示区"""
    minimap_group = QGroupBox("🗺️ 小地图")
    minimap_layout = QVBoxLayout()

    # 添加顶部弹性空间，让小地图靠上显示
    minimap_layout.addStretch()

    # 小地图容器（用于居中）
    minimap_container = QHBoxLayout()
    minimap_container.addStretch()

    main_window.minimap_display = VideoDisplayLabel()
    main_window.minimap_display.setFixedSize(280, 280)

    # 清除最小尺寸限制（VideoDisplayLabel 构造函数中设置的640x480）
    main_window.minimap_display.setMinimumSize(280, 280)

    main_window.minimap_display.setStyleSheet("""
        QLabel {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
            border: 2px solid #00d4ff;
            border-radius: 8px;
            color: #00d4ff;
            font-size: 12px;
        }
    """)
    main_window.minimap_display.setText("等待推流...")
    main_window.minimap_display.setAlignment(Qt.AlignCenter)
    minimap_container.addWidget(main_window.minimap_display)

    minimap_container.addStretch()
    minimap_layout.addLayout(minimap_container)

    # 添加底部弹性空间
    minimap_layout.addStretch()

    minimap_group.setLayout(minimap_layout)
    return minimap_group


def _create_action_section(main_window):
    """创建操作按钮区"""
    action_group = QGroupBox("🎮 操作")
    action_layout = QVBoxLayout()
    action_layout.setSpacing(10)

    # 截图按钮
    main_window.screenshot_btn = QPushButton("📷 截图")
    main_window.screenshot_btn.setObjectName("screenshot")
    main_window.screenshot_btn.setToolTip("截取当前画面并保存到 screenshots 目录")
    main_window.screenshot_btn.setEnabled(False)
    action_layout.addWidget(main_window.screenshot_btn)

    # 导入大地图按钮
    main_window.load_bigmap_btn = QPushButton("🗺️ 导入大地图")
    main_window.load_bigmap_btn.setObjectName("loadbigmap")
    main_window.load_bigmap_btn.setToolTip("加载大地图图片用于显示完整地图")
    action_layout.addWidget(main_window.load_bigmap_btn)

    # 实时定位按钮
    main_window.locate_btn = QPushButton("📍 开始定位")
    main_window.locate_btn.setObjectName("locate")
    main_window.locate_btn.setToolTip("开启/关闭大地图实时定位")
    main_window.locate_btn.setCheckable(True)
    main_window.locate_btn.setEnabled(False)
    action_layout.addWidget(main_window.locate_btn)

    action_group.setLayout(action_layout)
    return action_group


class BigMapView(QGraphicsView):
    """支持缩放的大地图视图"""
    
    # 缩放比例变化信号
    zoom_changed = Signal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # 缩放相关属性
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.pixmap_item = None
        
        # 设置渲染选项
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 样式
        self.setStyleSheet("""
            QGraphicsView {
                background: #0a0a0a;
                border: 1px solid #333;
            }
            QScrollBar:vertical {
                background: #2a2a2a;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00d4ff;
            }
            QScrollBar:horizontal {
                background: #2a2a2a;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #555;
                border-radius: 6px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #00d4ff;
            }
        """)
    
    def _update_zoom_display(self):
        """更新缩放显示并发射信号"""
        self.zoom_changed.emit(self.zoom_factor)
    
    def load_image(self, file_path):
        """
        加载图片文件
        
        Args:
            file_path: 图片文件路径
        """
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            # 清除旧内容
            self.scene.clear()
            
            # 创建新的 pixmap item
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)
            self.scene.setSceneRect(pixmap.rect())
            
            # 重置缩放
            self.resetTransform()
            self.zoom_factor = 1.0

            return True
        return False
    
    def zoom_in(self):
        """放大"""
        new_factor = self.zoom_factor * 1.25
        if new_factor <= self.max_zoom:
            self.zoom_factor = new_factor
            self.apply_zoom()
            self._update_zoom_display()
    
    def zoom_out(self):
        """缩小"""
        new_factor = self.zoom_factor / 1.25
        if new_factor >= self.min_zoom:
            self.zoom_factor = new_factor
            self.apply_zoom()
            self._update_zoom_display()
    
    def zoom_fit(self):
        """适应窗口"""
        if self.pixmap_item:
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            # 计算实际缩放比例
            transform = self.transform()
            self.zoom_factor = transform.m11()  # m11 是 X 轴缩放因子
            self._update_zoom_display()
    
    def zoom_original(self):
        """原始大小 (100%)"""
        self.resetTransform()
        self.zoom_factor = 1.0
        self._update_zoom_display()

    def apply_zoom(self):
        """应用缩放变换"""
        self.resetTransform()
        self.scale(self.zoom_factor, self.zoom_factor)
    
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def update_marker(self, center_x, center_y, success=True):
        """
        在地图上更新定位标记
        """
        from PySide6.QtWidgets import QGraphicsEllipseItem
        from PySide6.QtGui import QPen, QColor
        
        if not hasattr(self, 'marker_item'):
            self.marker_item = QGraphicsEllipseItem(-15, -15, 30, 30)
            pen = QPen(QColor(255, 0, 0))
            pen.setWidth(3)
            self.marker_item.setPen(pen)
            self.scene.addItem(self.marker_item)
            self.marker_item.setZValue(10)
            
        if success:
            self.marker_item.setPos(center_x, center_y)
            self.marker_item.show()
        else:
            self.marker_item.hide()


def _create_bigmap_section(main_window):
    """
    创建大地图显示区（带缩放控制）
    
    使用 QGraphicsView 实现平滑缩放功能
    """
    from PySide6.QtWidgets import QSizePolicy as QSP
    
    bigmap_group = QGroupBox("🗺️ 大地图")
    bigmap_layout = QVBoxLayout()
    
    # 缩放工具栏
    toolbar = QHBoxLayout()
    toolbar.setSpacing(8)

    # 适应窗口按钮
    zoom_fit_btn = QPushButton("自适应")
    zoom_fit_btn.setFixedSize(65, 30)
    zoom_fit_btn.setToolTip("适应窗口大小")
    zoom_fit_btn.clicked.connect(lambda: main_window.bigmap_view.zoom_fit())
    toolbar.addWidget(zoom_fit_btn)

    # 原始大小按钮
    zoom_orig_btn = QPushButton("1:1")
    zoom_orig_btn.setFixedSize(50, 30)
    zoom_orig_btn.setToolTip("原始大小 (100%)")
    zoom_orig_btn.clicked.connect(lambda: main_window.bigmap_view.zoom_original())
    toolbar.addWidget(zoom_orig_btn)

    toolbar.addStretch()
    bigmap_layout.addLayout(toolbar)
    
    # 大地图视图（带缩放功能）
    main_window.bigmap_view = BigMapView()
    main_window.bigmap_view.setMinimumSize(400, 300)
    # 设置 Expanding 策略，让大地图区域占据所有可用空间
    main_window.bigmap_view.setSizePolicy(QSP.Policy.Expanding, QSP.Policy.Expanding)

    main_window.zoom_label = QLabel("100%")
    main_window.zoom_label.setStyleSheet("color: #00d4ff; padding: 0 6px; font-weight: bold;")
    toolbar.insertWidget(2, main_window.zoom_label)
    main_window.bigmap_view.zoom_changed.connect(
        lambda z: main_window.zoom_label.setText(f"{int(z * 100)}%")
    )

    bigmap_layout.addWidget(main_window.bigmap_view, 1)
    
    bigmap_group.setLayout(bigmap_layout)
    return bigmap_group


def _create_status_bar(main_window):
    """创建底部状态栏"""
    main_window.status_bar = QStatusBar()
    main_window.setStatusBar(main_window.status_bar)

    main_window.device_label = QLabel("设备: 未连接")
    main_window.device_label.setStyleSheet("color: #888; padding: 0 10px;")
    main_window.status_bar.addWidget(main_window.device_label, 1)

    main_window.status_indicator = QLabel("●")
    main_window.status_indicator.setStyleSheet("color: #888; font-size: 20px; padding: 0 10px;")
    main_window.status_bar.addPermanentWidget(main_window.status_indicator)

    main_window._log(f"ADB: {main_window.paths['adb'] or '✗'}")
    main_window._log(f"server: {main_window.paths['scrcpy_server'] or '✗'}")
    main_window._log("准备就绪，点击「开始推流」")


def _setup_connections(main_window):
    """设置信号连接和快捷键"""
    main_window.start_btn.clicked.connect(main_window._on_start)
    main_window.stop_btn.clicked.connect(main_window._on_stop)
    main_window.screenshot_btn.clicked.connect(main_window._on_screenshot)
    main_window.load_bigmap_btn.clicked.connect(main_window._on_load_bigmap)
    main_window.locate_btn.toggled.connect(main_window._on_locate_toggled)

    # 配置保存防抖
    main_window.resolution.currentTextChanged.connect(main_window._schedule_save_config)
    main_window.bitrate.currentTextChanged.connect(main_window._schedule_save_config)
    main_window.fps.currentTextChanged.connect(main_window._schedule_save_config)
    main_window.codec.currentTextChanged.connect(main_window._schedule_save_config)

    # 快捷键
    main_window.screenshot_shortcut = QShortcut(QKeySequence("Ctrl+S"), main_window)
    main_window.screenshot_shortcut.activated.connect(main_window._on_screenshot)


def _get_stylesheet():
    """从文件加载样式表"""
    import os

    # 获取样式文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    style_file = os.path.join(current_dir, "styles", "main.qss")

    try:
        with open(style_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 如果文件不存在，返回基础样式
        return """
            QMainWindow { background: #1a1a2e; }
            QLabel { color: white; }
        """
