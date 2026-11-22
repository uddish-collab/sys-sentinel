"""Dedicated individual subsystem monitor panels for Sentinel.

Provides isolated, dedicated deep-dive panels for CPU, RAM, Storage,
Thermals, GPU, Network, System, and Settings without mixing them.
"""

from typing import Optional, Dict, Any, List, Callable, Tuple
from collections import deque
import sys
import math

from PySide6.QtCore import (
    Qt,
    QRectF,
    QPointF,
    QTimer,
    Property,
    QPropertyAnimation,
    QEasingCurve,
    Signal,
    QUrl,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
    QFont,
    QDesktopServices,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTabWidget,
    QTabBar,
    QScrollArea,
    QColorDialog,
    QGraphicsOpacityEffect,
    QLineEdit,
    QTextEdit,
    QMessageBox,
)

from senti_widgets import SmoothBar
from senti_settings import SentiSettings, PRESET_THEMES, DEFAULT_COLORS
try:
    from src.senti_brain import SentiBrain
except ImportError:
    from senti_brain import SentiBrain
try:
    from src.senti_sound import play_sound
except ImportError:
    try:
        from senti_sound import play_sound
    except ImportError:
        def play_sound(name: str, enabled: bool = True):
            pass
try:
    from src.senti_island import TAB_CANONICAL
except ImportError:
    from senti_island import TAB_CANONICAL



class MiniSparkline(QWidget):
    """Clean 60-sample historical rolling sparkline with smooth anti-aliased gradient fill."""

    def __init__(self, color: QColor, unit: str = "%", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.color = color
        self.unit = unit
        self.history: deque = deque(maxlen=60)
        self.setFixedHeight(64)
        self.setMinimumWidth(160)

    def add_sample(self, val: Optional[float]):
        if val is not None:
            self.history.append(float(val))
            self.update()

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()

            # Background track
            p.setPen(QPen(QColor("#1c2028"), 1.0))
            p.setBrush(QColor("#0d0e14"))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 6.0, 6.0)

            if len(self.history) < 2:
                p.setPen(QColor("#6b7079"))
                p.setFont(QFont("Segoe UI", 9))
                p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Collecting telemetry...")
                return

            samples = list(self.history)
            max_val = max(100.0, max(samples))
            min_val = 0.0
            val_range = max(1.0, max_val - min_val)

            pad_x = 8.0
            pad_y = 8.0
            avail_w = w - (pad_x * 2.0)
            avail_h = h - (pad_y * 2.0)

            step_x = avail_w / (len(samples) - 1)
            pts = []
            for i, val in enumerate(samples):
                norm = (val - min_val) / val_range
                norm = max(0.0, min(1.0, norm))
                x = pad_x + (i * step_x)
                y = pad_y + avail_h - (norm * avail_h)
                pts.append(QPointF(x, y))

            # Fill path
            fill_path = QPainterPath()
            fill_path.moveTo(pad_x, pad_y + avail_h)
            for pt in pts:
                fill_path.lineTo(pt)
            fill_path.lineTo(pad_x + avail_w, pad_y + avail_h)
            fill_path.closeSubpath()

            grad = QLinearGradient(0, pad_y, 0, pad_y + avail_h)
            c_top = QColor(self.color)
            c_top.setAlpha(80)
            c_bot = QColor(self.color)
            c_bot.setAlpha(5)
            grad.setColorAt(0.0, c_top)
            grad.setColorAt(1.0, c_bot)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(fill_path)

            # Stroke line
            line_path = QPainterPath()
            line_path.moveTo(pts[0])
            for pt in pts[1:]:
                line_path.lineTo(pt)

            p.setPen(QPen(self.color, 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(line_path)

            # Current reading pill badge
            cur_val = samples[-1]
            p.setPen(self.color)
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            tag_text = f"{cur_val:.1f}{self.unit}"
            p.drawText(QRectF(w - 74, 4, 66, 16), Qt.AlignmentFlag.AlignRight, tag_text)
        finally:
            p.end()


THEME_DATA: List[Dict[str, Any]] = [
    {
        "name": "Cyberpunk Cyan",
        "tag": "CYBERPUNK // CYAN",
        "accent": "#00e5ff",
        "desc": "Electric cyan optics & luminous high-contrast HUD",
        "colors": [
            ("BODY", "#f4f1ea"),
            ("DETAILS", "#14213d"),
            ("EYES", "#00e5ff"),
            ("GLOW", "#00e5ff"),
        ],
    },
    {
        "name": "Stealth Obsidian",
        "tag": "STEALTH // OBSIDIAN",
        "accent": "#94a3b8",
        "desc": "Ultra-dark obsidian surfaces with low-luminescence HUD",
        "colors": [
            ("BODY", "#181b22"),
            ("DETAILS", "#07080a"),
            ("EYES", "#00e5ff"),
            ("GLOW", "#00e5ff"),
        ],
    },
    {
        "name": "Matrix Emerald",
        "tag": "TERMINAL // EMERALD",
        "accent": "#22c55e",
        "desc": "Phosphor matrix aesthetics with phosphor trace glow",
        "colors": [
            ("BODY", "#121a14"),
            ("DETAILS", "#060e08"),
            ("EYES", "#22c55e"),
            ("GLOW", "#10b981"),
        ],
    },
    {
        "name": "Solar Amber",
        "tag": "CHRONO // SOLAR AMBER",
        "accent": "#f5a524",
        "desc": "Warm incandescent amber inspired by analog vacuum tubes",
        "colors": [
            ("BODY", "#201712"),
            ("DETAILS", "#0c0805"),
            ("EYES", "#f5a524"),
            ("GLOW", "#ff7a00"),
        ],
    },
    {
        "name": "Synthwave Neon",
        "tag": "SYNTHWAVE // NEON",
        "accent": "#f43f5e",
        "desc": "Hyper-saturated magenta and ultraviolet retrowave palette",
        "colors": [
            ("BODY", "#1a1226"),
            ("DETAILS", "#0c0614"),
            ("EYES", "#f43f5e"),
            ("GLOW", "#a855f7"),
        ],
    },
]


class RotaryThemeDial(QWidget):
    """Precision rotary theme selector knob with tactile graduation ticks and smooth snapping."""
    themeChanged = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(130, 130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._current_index = 0
        self._angle = 150.0  # Angle in degrees (150° to 390°)
        self._anim = QPropertyAnimation(self, b"dialAngle", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._is_dragging = False

    def get_dial_angle(self) -> float:
        return self._angle

    def set_dial_angle(self, val: float):
        self._angle = val
        self.update()

    dialAngle = Property(float, get_dial_angle, set_dial_angle)

    def _index_to_angle(self, idx: int) -> float:
        return 150.0 + idx * 60.0

    def set_theme_index(self, idx: int, animate: bool = True):
        idx = max(0, min(len(THEME_DATA) - 1, idx))
        if idx == self._current_index and not animate:
            return
        self._current_index = idx
        target_a = self._index_to_angle(idx)
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._angle)
            self._anim.setEndValue(target_a)
            self._anim.start()
        else:
            self._angle = target_a
            self.update()
        self.themeChanged.emit(idx, THEME_DATA[idx]["name"])

    def current_theme(self) -> dict:
        return THEME_DATA[self._current_index]

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._handle_mouse(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self._handle_mouse(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_theme_index(self._current_index - 1)
        elif delta < 0:
            self.set_theme_index(self._current_index + 1)
        event.accept()

    def _handle_mouse(self, pos: QPointF):
        cx, cy = self.width() / 2.0, self.height() / 2.0
        dx = pos.x() - cx
        dy = pos.y() - cy
        rad = math.atan2(dy, dx)
        deg = math.degrees(rad)
        if deg < 0:
            deg += 360.0

        best_idx = 0
        min_diff = 999.0
        for i in range(5):
            target = (150.0 + i * 60.0) % 360.0
            diff = abs(deg - target)
            diff = min(diff, 360.0 - diff)
            if diff < min_diff:
                min_diff = diff
                best_idx = i
        if best_idx != self._current_index:
            self.set_theme_index(best_idx)

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            cx, cy = self.width() / 2.0, self.height() / 2.0
            cur_theme = THEME_DATA[self._current_index]
            accent_col = QColor(cur_theme["accent"])

            outer_r = 46.0

            # 1. Subtle Calibration Arc
            arc_rect = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
            p.setPen(QPen(QColor("#242730"), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(arc_rect, int(-150 * 16), int(-240 * 16))

            # 2. Draw fine graduation tick marks
            for deg in range(150, 395, 6):
                rad = math.radians(deg)
                is_major = (deg % 30 == 0)
                t_in = 37.0 if not is_major else 34.0
                t_out = 42.0
                p1 = QPointF(cx + t_in * math.cos(rad), cy + t_in * math.sin(rad))
                p2 = QPointF(cx + t_out * math.cos(rad), cy + t_out * math.sin(rad))
                p.setPen(QPen(QColor("#272a33") if not is_major else QColor("#444b5c"), 1.0))
                p.drawLine(p1, p2)

            # 3. Draw 5 theme notch nodes & micro labels
            f_num = QFont("Consolas", 7)
            f_num.setBold(True)
            p.setFont(f_num)

            for i in range(5):
                angle_deg = 150.0 + i * 60.0
                rad = math.radians(angle_deg)
                nx = cx + outer_r * math.cos(rad)
                ny = cy + outer_r * math.sin(rad)
                is_active = (i == self._current_index)

                if is_active:
                    glow = QColor(accent_col)
                    glow.setAlpha(65)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(glow)
                    p.drawEllipse(QPointF(nx, ny), 7.0, 7.0)

                    p.setBrush(accent_col)
                    p.setPen(QPen(QColor("#ffffff"), 1.2))
                    p.drawEllipse(QPointF(nx, ny), 4.0, 4.0)
                else:
                    node_col = QColor(THEME_DATA[i]["accent"])
                    p.setBrush(node_col)
                    p.setPen(QPen(QColor("#111216"), 1.0))
                    p.drawEllipse(QPointF(nx, ny), 2.8, 2.8)

                # Micro numbering outside notches
                num_r = outer_r + 13.0
                lx = cx + num_r * math.cos(rad)
                ly = cy + num_r * math.sin(rad)
                p.setPen(accent_col if is_active else QColor("#52525b"))
                p.drawText(QRectF(lx - 10, ly - 6, 20, 12), Qt.AlignmentFlag.AlignCenter, f"0{i+1}")

            # 4. Rotary Knob Outer Bezel
            knob_r = 29.0
            knob_rect = QRectF(cx - knob_r, cy - knob_r, knob_r * 2, knob_r * 2)

            grad = QLinearGradient(cx - knob_r, cy - knob_r, cx + knob_r, cy + knob_r)
            grad.setColorAt(0.0, QColor("#22252c"))
            grad.setColorAt(0.5, QColor("#14161b"))
            grad.setColorAt(1.0, QColor("#0c0d10"))

            p.setBrush(grad)
            p.setPen(QPen(QColor("#313642"), 1.2))
            p.drawEllipse(knob_rect)

            # 5. Inner Machined Texture Ring
            mach_r = 21.0
            mach_rect = QRectF(cx - mach_r, cy - mach_r, mach_r * 2, mach_r * 2)
            p.setBrush(QColor("#0d0e12"))
            p.setPen(QPen(QColor("#1e222b"), 1.0))
            p.drawEllipse(mach_rect)

            # 6. Dial Indicator Needle
            a_rad = math.radians(self._angle)
            needle_len = 25.0
            n_tip = QPointF(cx + needle_len * math.cos(a_rad), cy + needle_len * math.sin(a_rad))
            n_base = QPointF(cx + 6.0 * math.cos(a_rad), cy + 6.0 * math.sin(a_rad))

            n_pen = QPen(QColor("#f4f4f5"), 2.0)
            n_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(n_pen)
            p.drawLine(n_base, n_tip)

            # 7. Center Glowing Hub Cap
            p.setPen(QPen(QColor("#2d3340"), 1.0))
            p.setBrush(QColor("#16181f"))
            p.drawEllipse(QPointF(cx, cy), 5.5, 5.5)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent_col)
            p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)

        finally:
            p.end()


class SettingsTabCanvas(QWidget):
    """Clean, minimalist dark matte canvas matching all other subsystem panels."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(1.5, 1.5, self.width() - 3.0, self.height() - 3.0)
            p.setPen(QPen(QColor("#1f2229"), 1.0))
            p.setBrush(QColor("#0d0e12"))
            p.drawRoundedRect(rect, 8.0, 8.0)
        finally:
            p.end()


class SentiDashboardWindow(QWidget):
    """Comprehensive, dedicated subsystem monitor panels for Sentinel.
    
    Each pill opens only its dedicated subsystem view (CPU, RAM, DISK, TEMP, GPU, NET, SYS, SETTINGS).
    Features smooth cross-fade navigation and zero window blinking.
    """

    closed = Signal()

    def __init__(
        self,
        settings: Optional[Any] = None,
        on_colors_changed: Optional[Callable[[], None]] = None,
        on_sound_toggled: Optional[Callable[[bool], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.settings = settings or SentiSettings()
        self.on_colors_changed = on_colors_changed
        self.on_sound_toggled = on_sound_toggled

        self.setWindowTitle("Senti — System Telemetry")
        self.setObjectName("dashboardRoot")
        self.setFixedSize(720, 570)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # 100% solid opacity
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(70)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Dragging state
        self._is_dragging = False
        self._press_pos = None

        # Data cache & Brain
        self._telemetry: Dict[str, Any] = {}
        self.brain = SentiBrain()
        self._pre_instructions_pos = None

        self._init_ui()

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        # Left Column: Subsystem View (Fixed 692px width to preserve exact layout)
        self.main_column = QWidget()
        self.main_column.setFixedWidth(692)
        main_lay = QVBoxLayout(self.main_column)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(10)

        # Top Bar: Minimalist Luxury Brand Breadcrumb + Close Button
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("SENTINEL  ·  CPU")
        self.lbl_title.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: 700; letter-spacing: 2px;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #111317;
                color: #8c9dbd;
                border: 1px solid #20242c;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #ff3b4a;
                color: #ffffff;
                border-color: #ff3b4a;
            }
        """)
        btn_close.clicked.connect(self.close_panel)
        top_bar.addWidget(btn_close)
        main_lay.addLayout(top_bar)

        # Subsystem Panel Container (Tab bar completely hidden so only the selected view appears)
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1c2028;
                border-radius: 8px;
                background: #111317;
                top: 0px;
            }
        """)
        self.tabs.tabBar().hide()
        self.tabs.tabBar().setFixedHeight(0)

        # Initialize Individual Dedicated Subsystem Panels (8 Subsystems, aligned 1:1 with Island)
        self.tab_cpu = self._build_cpu_tab()
        self.tab_ram = self._build_ram_tab()
        self.tab_gpu = self._build_gpu_tab()
        self.tab_net = self._build_net_tab()
        self.tab_disk = self._build_disk_tab()
        self.tab_temp = self._build_temp_tab()
        self.tab_sys = self._build_sys_tab()
        self.tab_settings = self._build_settings_tab()

        self.tabs.addTab(self.tab_cpu, "CPU")
        self.tabs.addTab(self.tab_ram, "MEMORY")
        self.tabs.addTab(self.tab_gpu, "GPU")
        self.tabs.addTab(self.tab_net, "NETWORK")
        self.tabs.addTab(self.tab_disk, "STORAGE")
        self.tabs.addTab(self.tab_temp, "THERMALS")
        self.tabs.addTab(self.tab_sys, "SYSTEM")
        self.tabs.addTab(self.tab_settings, "SETTINGS")

        main_lay.addWidget(self.tabs)
        root.addWidget(self.main_column)

        # Right Column: Instructions Pop-Out Drawer (Hidden by default)
        self.instructions_panel = self._build_instructions_panel()
        self.instructions_panel.hide()
        root.addWidget(self.instructions_panel)

    # --- TAB 1: CPU (Live CPU Monitoring) ---
    def _build_cpu_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # 1. Header Overview: Overall Load, Processor Name & Live Clock Frequency
        top_row = QHBoxLayout()
        self.lbl_cpu_main = QLabel("CPU Load: —%")
        self.lbl_cpu_main.setStyleSheet("color: #22c55e; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_cpu_main)
        top_row.addSpacing(14)

        self.lbl_cpu_model = QLabel("Processor: Detecting...")
        self.lbl_cpu_model.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 600;")
        top_row.addWidget(self.lbl_cpu_model)
        top_row.addStretch()

        self.lbl_cpu_freq = QLabel("Frequency: — MHz")
        self.lbl_cpu_freq.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_cpu_freq)
        lay.addLayout(top_row)

        # 2. Historical 60s Telemetry Sparkline
        self.spark_cpu = MiniSparkline(QColor("#22c55e"), "%", self)
        self.spark_cpu.setFixedHeight(54)
        lay.addWidget(self.spark_cpu)

        # 3. Overview Telemetry Badges (Architecture, Clock Speed, Sockets, Cores)
        specs_row = QHBoxLayout()
        specs_row.setSpacing(8)
        self.lbl_cpu_threads = QLabel("— Threads")
        self.lbl_cpu_physical = QLabel("— Cores")
        self.lbl_cpu_cur_freq = QLabel("— MHz")
        self.lbl_cpu_active_threads = QLabel("— Threads")

        for title, lbl, parent_lay in [
            ("LOGICAL THREADS", self.lbl_cpu_threads, specs_row),
            ("PHYSICAL CORES", self.lbl_cpu_physical, specs_row),
            ("CLOCK SPEED", self.lbl_cpu_cur_freq, specs_row),
            ("ACTIVE THREADS", self.lbl_cpu_active_threads, specs_row),
        ]:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #0d0e14;
                    border: 1px solid #1c2028;
                    border-radius: 6px;
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(8, 6, 8, 6)
            c_lay.setSpacing(2)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #6b7079; font-size: 8.5px; font-weight: 700; letter-spacing: 0.5px;")
            lbl.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700;")
            c_lay.addWidget(t_lbl)
            c_lay.addWidget(lbl)
            parent_lay.addWidget(card)
        lay.addLayout(specs_row)

        # 4. Dynamic Logical Cores Section Header
        self.lbl_cores_header = QLabel("LOGICAL CORES")
        self.lbl_cores_header.setStyleSheet("color: #8c9dbd; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lay.addWidget(self.lbl_cores_header)

        # 5. Scrollable Adaptive Cores Grid (Supports any CPU: 2, 4, 6, 8, 12, 16, 24, 32, 64+ cores)
        self.cpu_cores_scroll = QScrollArea()
        self.cpu_cores_scroll.setWidgetResizable(True)
        self.cpu_cores_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cpu_cores_scroll.setStyleSheet("""
            QScrollArea {
                background: #111317;
                border: 1px solid #1c2028;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                background: #0d0e14;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #252934;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3b4252;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.cpu_cores_scroll.viewport().setStyleSheet("background: #111317; border: none;")
        self.cpu_cores_container = QWidget()
        self.cpu_cores_container.setStyleSheet("background: #111317;")
        self.cores_grid = QGridLayout(self.cpu_cores_container)
        self.cores_grid.setContentsMargins(8, 8, 8, 8)
        self.cores_grid.setSpacing(8)
        self.cpu_cores_scroll.setWidget(self.cpu_cores_container)
        lay.addWidget(self.cpu_cores_scroll)

        # Keep tracking lists for telemetry updates
        self._cpu_tiles: List[Dict[str, Any]] = []
        self.core_labels: List[QLabel] = []
        self.core_bars: List[SmoothBar] = []

        # 6. Bottom Hardware Activity Statistics Frame
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #0d0e14;
                border: 1px solid #1c2028;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        s_lay = QHBoxLayout(stats_frame)
        s_lay.setContentsMargins(12, 6, 12, 6)
        self.lbl_ctx_switches = QLabel("Context Switches: —")
        self.lbl_interrupts = QLabel("Hardware Interrupts: —")
        for lbl in (self.lbl_ctx_switches, self.lbl_interrupts):
            lbl.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 600;")
            s_lay.addWidget(lbl)
        lay.addWidget(stats_frame)

        return w

    # --- TAB 2: RAM (Memory Utilization) ---
    def _build_ram_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        self.lbl_ram_main = QLabel("Memory: —%")
        self.lbl_ram_main.setStyleSheet("color: #f5a524; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_ram_main)
        top_row.addStretch()

        self.lbl_ram_gb = QLabel("Used: — GB / Total: — GB")
        self.lbl_ram_gb.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_ram_gb)
        lay.addLayout(top_row)

        self.spark_ram = MiniSparkline(QColor("#f5a524"), "%", self)
        lay.addWidget(self.spark_ram)

        grid = QGridLayout()
        grid.setSpacing(8)

        self.lbl_ram_inuse = QLabel("— GB")
        self.lbl_ram_avail = QLabel("— GB")
        self.lbl_ram_cached = QLabel("— GB")
        self.lbl_ram_free = QLabel("— GB")

        cards = [
            ("IN USE", self.lbl_ram_inuse),
            ("AVAILABLE", self.lbl_ram_avail),
            ("STANDBY CACHE", self.lbl_ram_cached),
            ("FREE PHYSICAL", self.lbl_ram_free),
        ]
        for idx, (title, lbl) in enumerate(cards):
            r = idx // 2
            c = idx % 2
            f = QFrame()
            f.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
            flay = QVBoxLayout(f)
            t = QLabel(title)
            t.setStyleSheet("color: #6b7079; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
            lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: 700;")
            flay.addWidget(t)
            flay.addWidget(lbl)
            grid.addWidget(f, r, c)
        lay.addLayout(grid)

        swap_frame = QFrame()
        swap_frame.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 8px;")
        swap_lay = QVBoxLayout(swap_frame)
        self.lbl_swap = QLabel("Paging File: — GB / — GB (—%)")
        self.lbl_swap.setStyleSheet("color: #8c9dbd; font-size: 11px;")
        self.bar_swap = SmoothBar(self)
        self.bar_swap.setFixedHeight(6)
        swap_lay.addWidget(self.lbl_swap)
        swap_lay.addWidget(self.bar_swap)
        lay.addWidget(swap_frame)

        lay.addStretch()
        return w

    # --- TAB 3: STORAGE (Disk Usage & I/O Speeds) ---
    def _build_disk_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        io_row = QHBoxLayout()
        self.lbl_disk_read = QLabel("Read: 0.00 MB/s")
        self.lbl_disk_read.setStyleSheet("color: #22c55e; font-size: 16px; font-weight: 700;")
        self.lbl_disk_write = QLabel("Write: 0.00 MB/s")
        self.lbl_disk_write.setStyleSheet("color: #00e5ff; font-size: 16px; font-weight: 700;")
        io_row.addWidget(self.lbl_disk_read)
        io_row.addSpacing(20)
        io_row.addWidget(self.lbl_disk_write)
        io_row.addStretch()
        lay.addLayout(io_row)

        self.spark_disk = MiniSparkline(QColor("#6366f1"), "%", self)
        lay.addWidget(self.spark_disk)

        lbl_parts = QLabel("STORAGE VOLUMES")
        lbl_parts.setStyleSheet("color: #8c9dbd; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(lbl_parts)

        self.disk_scroll = QScrollArea()
        self.disk_scroll.setWidgetResizable(True)
        self.disk_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.disk_scroll.setStyleSheet("""
            QScrollArea {
                background: #111317;
                border: 1px solid #1c2028;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                background: #0d0e14;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #252934;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3b4252;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.disk_scroll.viewport().setStyleSheet("background: #111317; border: none;")
        self.disk_part_container = QWidget()
        self.disk_part_container.setStyleSheet("background: #111317;")
        self.disk_part_layout = QVBoxLayout(self.disk_part_container)
        self.disk_part_layout.setContentsMargins(8, 8, 8, 8)
        self.disk_part_layout.setSpacing(8)
        self.disk_scroll.setWidget(self.disk_part_container)
        lay.addWidget(self.disk_scroll)

        return w

    # --- TAB 4: THERMALS (Temperatures & Fan Speeds) ---
    def _build_temp_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        self.lbl_temp_main = QLabel("Package Temp: —°C")
        self.lbl_temp_main.setStyleSheet("color: #f4505e; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_temp_main)
        top_row.addStretch()

        self.lbl_temp_status = QLabel("Thermal State: Normal")
        self.lbl_temp_status.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_temp_status)
        lay.addLayout(top_row)

        self.spark_temp = MiniSparkline(QColor("#f4505e"), "°C", self)
        lay.addWidget(self.spark_temp)

        f_zones = QFrame()
        f_zones.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
        zlay = QVBoxLayout(f_zones)
        self.lbl_cpu_temp = QLabel("CPU Core Thermal Sensor: Detecting...")
        self.lbl_gpu_temp = QLabel("GPU Package Sensor: Detecting...")
        self.lbl_fan_speed = QLabel("Cooling Fan: Regulated by System Firmware")
        for lbl in (self.lbl_cpu_temp, self.lbl_gpu_temp, self.lbl_fan_speed):
            lbl.setStyleSheet("color: #cdd9ed; font-size: 12px;")
            zlay.addWidget(lbl)
        lay.addWidget(f_zones)

        self.lbl_temp_note = QLabel("Note: Motherboard and vendor fan speeds are read directly from Windows ACPI/WMI sensors.")
        self.lbl_temp_note.setStyleSheet("color: #6b7079; font-size: 10px; font-style: italic;")
        lay.addWidget(self.lbl_temp_note)

        lay.addStretch()
        return w

    # --- TAB 5: GPU (Utilization & VRAM) ---
    def _build_gpu_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        self.lbl_gpu_main = QLabel("GPU Load: —%")
        self.lbl_gpu_main.setStyleSheet("color: #00e5ff; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_gpu_main)
        top_row.addStretch()

        self.lbl_gpu_name = QLabel("Graphics Adapter: Detecting...")
        self.lbl_gpu_name.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_gpu_name)
        lay.addLayout(top_row)

        self.spark_gpu = MiniSparkline(QColor("#00e5ff"), "%", self)
        lay.addWidget(self.spark_gpu)

        vram_frame = QFrame()
        vram_frame.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
        vlay = QVBoxLayout(vram_frame)
        self.lbl_vram = QLabel("Dedicated Video Memory (VRAM): — GB used of — GB")
        self.lbl_vram.setStyleSheet("color: #cdd9ed; font-size: 12px; font-weight: 600;")
        self.bar_vram = SmoothBar(self)
        self.bar_vram.setFixedHeight(8)
        self.lbl_gpu_driver = QLabel("Driver Version: Detecting...")
        self.lbl_gpu_driver.setStyleSheet("color: #6b7079; font-size: 11px;")

        vlay.addWidget(self.lbl_vram)
        vlay.addWidget(self.bar_vram)
        vlay.addSpacing(4)
        vlay.addWidget(self.lbl_gpu_driver)
        lay.addWidget(vram_frame)

        lay.addStretch()
        return w

    # --- TAB 6: NETWORK (3 Dedicated Telemetry Graphs: Download, Upload, Ping) ---
    def _build_net_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Graph 1: Live Download Throughput
        c_down = QFrame()
        c_down.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 6px 10px;")
        lay_down = QVBoxLayout(c_down)
        lay_down.setContentsMargins(4, 4, 4, 4)
        lay_down.setSpacing(4)
        row_d = QHBoxLayout()
        lbl_d_title = QLabel("DOWNLOAD RATE")
        lbl_d_title.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        self.lbl_net_down = QLabel("0.0 KB/s")
        self.lbl_net_down.setStyleSheet("color: #22c55e; font-size: 15px; font-weight: 700;")
        self.lbl_net_total_down = QLabel("Total Recv: 0.0 MB")
        self.lbl_net_total_down.setStyleSheet("color: #8c9dbd; font-size: 11px;")
        row_d.addWidget(lbl_d_title)
        row_d.addSpacing(14)
        row_d.addWidget(self.lbl_net_down)
        row_d.addStretch()
        row_d.addWidget(self.lbl_net_total_down)
        lay_down.addLayout(row_d)
        self.spark_net_down = MiniSparkline(QColor("#22c55e"), " KB/s", self)
        self.spark_net_down.setFixedHeight(54)
        lay_down.addWidget(self.spark_net_down)
        lay.addWidget(c_down)

        # Graph 2: Live Upload Throughput
        c_up = QFrame()
        c_up.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 6px 10px;")
        lay_up = QVBoxLayout(c_up)
        lay_up.setContentsMargins(4, 4, 4, 4)
        lay_up.setSpacing(4)
        row_u = QHBoxLayout()
        lbl_u_title = QLabel("UPLOAD RATE")
        lbl_u_title.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        self.lbl_net_up = QLabel("0.0 KB/s")
        self.lbl_net_up.setStyleSheet("color: #00e5ff; font-size: 15px; font-weight: 700;")
        self.lbl_net_total_up = QLabel("Total Sent: 0.0 MB")
        self.lbl_net_total_up.setStyleSheet("color: #8c9dbd; font-size: 11px;")
        row_u.addWidget(lbl_u_title)
        row_u.addSpacing(14)
        row_u.addWidget(self.lbl_net_up)
        row_u.addStretch()
        row_u.addWidget(self.lbl_net_total_up)
        lay_up.addLayout(row_u)
        self.spark_net_up = MiniSparkline(QColor("#00e5ff"), " KB/s", self)
        self.spark_net_up.setFixedHeight(54)
        lay_up.addWidget(self.spark_net_up)
        lay.addWidget(c_up)

        # Graph 3: Live Ping / Latency Tracker
        c_ping = QFrame()
        c_ping.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 6px 10px;")
        lay_ping = QVBoxLayout(c_ping)
        lay_ping.setContentsMargins(4, 4, 4, 4)
        lay_ping.setSpacing(4)
        row_p = QHBoxLayout()
        lbl_p_title = QLabel("ROUND-TRIP LATENCY (PING)")
        lbl_p_title.setStyleSheet("color: #a855f7; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        self.lbl_ping = QLabel("— ms")
        self.lbl_ping.setStyleSheet("color: #a855f7; font-size: 15px; font-weight: 700;")
        self.lbl_ping_status = QLabel("Target: DNS Gateway (8.8.8.8)")
        self.lbl_ping_status.setStyleSheet("color: #8c9dbd; font-size: 11px;")
        row_p.addWidget(lbl_p_title)
        row_p.addSpacing(14)
        row_p.addWidget(self.lbl_ping)
        row_p.addStretch()
        row_p.addWidget(self.lbl_ping_status)
        lay_ping.addLayout(row_p)
        self.spark_net_ping = MiniSparkline(QColor("#a855f7"), " ms", self)
        self.spark_net_ping.setFixedHeight(54)
        lay_ping.addWidget(self.spark_net_ping)
        lay.addWidget(c_ping)

        lay.addStretch()
        return w

    # --- TAB 7: SYSTEM (Specs, Uptime & Battery) ---
    def _build_sys_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # OS & Hardware Specs Card
        f = QFrame()
        f.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 12px;")
        flay = QVBoxLayout(f)
        self.lbl_sys_os = QLabel("Operating System: Detecting...")
        self.lbl_sys_host = QLabel("Hostname: Detecting...")
        self.lbl_sys_proc = QLabel("Processor: Detecting...")
        self.lbl_sys_uptime = QLabel("Continuous Uptime: 0s")
        for lbl in (self.lbl_sys_os, self.lbl_sys_host, self.lbl_sys_proc, self.lbl_sys_uptime):
            lbl.setStyleSheet("color: #cdd9ed; font-size: 12px; font-weight: 600;")
            flay.addWidget(lbl)
        lay.addWidget(f)

        # Battery Card
        b_box = QFrame()
        b_box.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 12px;")
        b_lay = QVBoxLayout(b_box)
        self.lbl_battery = QLabel("Battery: Detecting...")
        self.lbl_battery.setStyleSheet("color: #22c55e; font-size: 14px; font-weight: 700;")
        self.bar_battery = SmoothBar(self)
        self.bar_battery.setFixedHeight(8)
        b_lay.addWidget(self.lbl_battery)
        b_lay.addWidget(self.bar_battery)
        lay.addWidget(b_box)

        lay.addStretch()
        return w

    # --- TAB 8: SETTINGS & WORKSTATION CONFIGURATION ---
    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # -------------------------------------------------------------
        # CARD 1: AUTHOR & REPOSITORY (MATCHES OTHER TABS)
        # -------------------------------------------------------------
        c1 = QFrame()
        c1.setStyleSheet("""
            QFrame {
                background: #0d0e14;
                border: 1px solid #1c2028;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        c1_lay = QVBoxLayout(c1)
        c1_lay.setContentsMargins(16, 14, 16, 14)
        c1_lay.setSpacing(12)

        lbl_c1_header = QLabel("AUTHOR & REPOSITORY")
        lbl_c1_header.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        c1_lay.addWidget(lbl_c1_header)

        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # ---------------------------------------------------------
        # LEFT COLUMN: AUTHOR & SPECIFICATIONS
        # ---------------------------------------------------------
        left_meta = QVBoxLayout()
        left_meta.setSpacing(8)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        lbl_username = QLabel("Uddish")
        lbl_username.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 800; font-family: 'Segoe UI', Consolas;")
        name_row.addWidget(lbl_username)

        lbl_role_tag = QLabel("●  LEAD ARCHITECT & CREATOR")
        lbl_role_tag.setStyleSheet("color: #64748b; font-size: 9.5px; font-weight: 700; letter-spacing: 0.6px;")
        name_row.addWidget(lbl_role_tag)
        name_row.addStretch()
        left_meta.addLayout(name_row)

        specs_grid = QGridLayout()
        specs_grid.setHorizontalSpacing(10)
        specs_grid.setVerticalSpacing(4)
        specs_grid.setColumnStretch(1, 1)

        def _spec_row(r: int, label: str, val_widget: QWidget):
            l = QLabel(label)
            l.setStyleSheet("color: #64748b; font-size: 9.5px; font-weight: 700;")
            specs_grid.addWidget(l, r, 0)
            specs_grid.addWidget(val_widget, r, 1)

        p_lbl = QLabel("SYS-SENTINEL Desktop Workstation Companion")
        p_lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
        _spec_row(0, "PROJECT", p_lbl)

        f_lbl = QLabel("Python 3.10+ · Qt6 / PySide6 Engine")
        f_lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
        _spec_row(1, "FRAMEWORK", f_lbl)

        t_lbl = QLabel("Zero-Latency Real-Time Hardware Diagnostics")
        t_lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
        _spec_row(2, "TELEMETRY", t_lbl)

        # Repository link
        repo_link = QLabel(
            "<a href='https://github.com/uddish-collab/sys-sentinel' "
            "style='color: #38bdf8; text-decoration: none; font-weight: 600;'>"
            "github.com/uddish-collab/sys-sentinel</a>"
        )
        repo_link.setOpenExternalLinks(True)
        repo_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        repo_link.setStyleSheet("font-size: 10px;")
        _spec_row(3, "REPOSITORY", repo_link)

        left_meta.addLayout(specs_grid)
        row1.addLayout(left_meta, 5)

        # ---------------------------------------------------------
        # VERTICAL HAIRLINE DIVIDER
        # ---------------------------------------------------------
        vdiv = QFrame()
        vdiv.setFixedWidth(1)
        vdiv.setStyleSheet("background: #1c2028; border: none;")
        row1.addWidget(vdiv)

        # ---------------------------------------------------------
        # RIGHT COLUMN: LICENSE & PERMISSIONS (UNBOXED, MINIMALIST LUXURY)
        # ---------------------------------------------------------
        right_lic = QVBoxLayout()
        right_lic.setSpacing(8)

        lic_head = QHBoxLayout()
        lbl_lic_title = QLabel("LICENSE & PERMISSIONS")
        lbl_lic_title.setStyleSheet("color: #8c9dbd; font-size: 10px; font-weight: 700; letter-spacing: 0.6px;")
        lbl_lic_badge = QLabel("●  MIT PERMISSIVE")
        lbl_lic_badge.setStyleSheet("color: #22c55e; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
        lic_head.addWidget(lbl_lic_title)
        lic_head.addStretch()
        lic_head.addWidget(lbl_lic_badge)
        right_lic.addLayout(lic_head)

        lic_grid = QGridLayout()
        lic_grid.setHorizontalSpacing(10)
        lic_grid.setVerticalSpacing(4)
        lic_grid.setColumnStretch(1, 1)

        def _lic_row(r: int, label: str, val: str):
            l = QLabel(label)
            l.setStyleSheet("color: #64748b; font-size: 9.5px; font-weight: 700;")
            v = QLabel(val)
            v.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600;")
            lic_grid.addWidget(l, r, 0)
            lic_grid.addWidget(v, r, 1)

        _lic_row(0, "STANDARD", "MIT Open Source License")
        _lic_row(1, "COPYRIGHT", "© 2026 Uddish")
        _lic_row(2, "GRANT", "Use, modify, distribute, sublicense freely")
        _lic_row(3, "WARRANTY", "Provided 'as is' without limitation")

        right_lic.addLayout(lic_grid)
        row1.addLayout(right_lic, 4)

        c1_lay.addLayout(row1)
        lay.addWidget(c1)

        # -------------------------------------------------------------
        # CARD 2: THEME ROTARY DIAL (MINIMALIST, ZERO PALETTE FLUFF)
        # -------------------------------------------------------------
        c2 = QFrame()
        c2.setStyleSheet("""
            QFrame {
                background: #0d0e14;
                border: 1px solid #1c2028;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        c2_lay = QVBoxLayout(c2)
        c2_lay.setContentsMargins(16, 14, 16, 14)
        c2_lay.setSpacing(12)

        c2_hdr_row = QHBoxLayout()
        lbl_c2_header = QLabel("WORKSTATION THEME MATRIX")
        lbl_c2_header.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        c2_hdr_row.addWidget(lbl_c2_header)
        c2_hdr_row.addStretch()

        btn_autostart = QPushButton()
        btn_autostart.setFixedHeight(24)
        btn_autostart.setCursor(Qt.CursorShape.PointingHandCursor)

        def _refresh_autostart_style():
            enabled = self.settings.is_autostart_enabled()
            if enabled:
                btn_autostart.setText("●  START ON BOOT: ON")
                btn_autostart.setStyleSheet("""
                    QPushButton {
                        background: #101c18;
                        color: #22c55e;
                        font-size: 10px;
                        font-weight: 700;
                        letter-spacing: 0.8px;
                        border: 1px solid #1c3d2a;
                        border-radius: 4px;
                        padding: 0px 10px;
                    }
                    QPushButton:hover {
                        background: #142820;
                        border: 1px solid #22c55e;
                    }
                """)
            else:
                btn_autostart.setText("○  START ON BOOT: OFF")
                btn_autostart.setStyleSheet("""
                    QPushButton {
                        background: #12151e;
                        color: #64748b;
                        font-size: 10px;
                        font-weight: 700;
                        letter-spacing: 0.8px;
                        border: 1px solid #232938;
                        border-radius: 4px;
                        padding: 0px 10px;
                    }
                    QPushButton:hover {
                        background: #181d2a;
                        color: #94a3b8;
                        border: 1px solid #38bdf8;
                    }
                """)
        _refresh_autostart_style()

        def _on_autostart_clicked():
            cur = self.settings.is_autostart_enabled()
            self.settings.set_autostart_enabled(not cur)
            _refresh_autostart_style()

        btn_autostart.clicked.connect(_on_autostart_clicked)
        c2_hdr_row.addWidget(btn_autostart)

        btn_instructions = QPushButton("●  INSTRUCTIONS")
        btn_instructions.setFixedHeight(24)
        btn_instructions.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_instructions.setStyleSheet("""
            QPushButton {
                background: #12151e;
                color: #94a3b8;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.8px;
                border: 1px solid #232938;
                border-radius: 4px;
                padding: 0px 12px;
            }
            QPushButton:hover {
                background: #181d2a;
                color: #38bdf8;
                border: 1px solid #38bdf8;
            }
            QPushButton:pressed {
                background: #0d1017;
                color: #0284c7;
            }
        """)
        btn_instructions.clicked.connect(self.toggle_instructions_drawer)
        c2_hdr_row.addWidget(btn_instructions)
        c2_lay.addLayout(c2_hdr_row)

        # -------------------------------------------------------------
        # BODY: ROTARY DIAL & HEADING NEATLY BESIDE IT (CLEAN & COMPACT)
        # -------------------------------------------------------------
        dial_row = QHBoxLayout()
        dial_row.setSpacing(24)

        # 1. Rotary Dial
        dial = RotaryThemeDial()

        init_idx = 0
        cur_eyes = self.settings.get_color("eyes").name().lower()
        for i, t in enumerate(THEME_DATA):
            if t["colors"][2][1].lower() == cur_eyes:
                init_idx = i
                break

        dial.set_theme_index(init_idx, animate=False)
        dial_row.addWidget(dial)

        # 2. Information & Controls (Channel, Theme Heading, and Navigation Buttons neatly beside it)
        info_col = QVBoxLayout()
        info_col.setSpacing(8)
        info_col.addStretch()

        lbl_ch = QLabel(f"CHANNEL 0{init_idx + 1} / 0{len(THEME_DATA)}")
        lbl_ch.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        info_col.addWidget(lbl_ch)

        cur_t = THEME_DATA[init_idx]
        lbl_theme_name = QLabel(cur_t["name"].upper())
        lbl_theme_name.setStyleSheet(f"color: {cur_t['accent']}; font-size: 20px; font-weight: 800; letter-spacing: 1px;")
        info_col.addWidget(lbl_theme_name)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_prev = QPushButton("◀  PREV THEME")
        btn_next = QPushButton("NEXT THEME  ▶")
        for b in (btn_prev, btn_next):
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: #141720;
                    color: #8c9dbd;
                    font-size: 10px;
                    font-weight: 700;
                    border: 1px solid #232836;
                    border-radius: 4px;
                    padding: 0px 14px;
                }
                QPushButton:hover {
                    background: #1c212e;
                    color: #f8fafc;
                    border: 1px solid #38bdf8;
                }
            """)
        btn_prev.clicked.connect(lambda: dial.set_theme_index(dial._current_index - 1))
        btn_next.clicked.connect(lambda: dial.set_theme_index(dial._current_index + 1))
        btn_row.addWidget(btn_prev)
        btn_row.addWidget(btn_next)
        btn_row.addStretch()
        info_col.addLayout(btn_row)
        info_col.addStretch()

        dial_row.addLayout(info_col, 1)
        c2_lay.addLayout(dial_row)
        lay.addWidget(c2)

        # -------------------------------------------------------------
        # CARD 3: SENTI COMM LINK (STARK / JARVIS WORKSTATION TERMINAL)
        # -------------------------------------------------------------
        c3 = QFrame()
        c3.setObjectName("CommLinkCard")
        c3.setStyleSheet("""
            QFrame#CommLinkCard {
                background: #0d0e14;
                border: 1px solid #1c2028;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        c3_lay = QVBoxLayout(c3)
        c3_lay.setContentsMargins(16, 10, 16, 10)
        c3_lay.setSpacing(6)

        c3_head = QHBoxLayout()
        lbl_c3_title = QLabel("SENTI COMS")
        lbl_c3_title.setStyleSheet("color: #8c9dbd; font-size: 10px; font-weight: 700; letter-spacing: 0.6px;")
        lbl_c3_status = QLabel("●  ONLINE")
        lbl_c3_status.setStyleSheet("color: #22c55e; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
        c3_head.addWidget(lbl_c3_title)
        c3_head.addStretch()
        c3_head.addWidget(lbl_c3_status)
        c3_lay.addLayout(c3_head)

        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFixedHeight(75)
        self.chat_log.setStyleSheet("""
            QTextEdit {
                background: #08090d;
                border: 1px solid #1a1e28;
                border-radius: 5px;
                color: #cbd5e1;
                font-family: Consolas, 'Segoe UI';
                font-size: 10px;
                padding: 6px;
                line-height: 140%;
            }
            QScrollBar:vertical {
                background: #090b10;
                width: 9px;
                margin: 2px 2px 2px 0px;
                border: 1px solid #141822;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #222938, stop:0.4 #333e54, stop:0.7 #283144, stop:1 #1a202c);
                border: 1px solid #3d4a66;
                border-radius: 3px;
                min-height: 22px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2c3a54, stop:0.5 #38bdf8, stop:1 #1e2c44);
                border: 1px solid #38bdf8;
            }
            QScrollBar::handle:vertical:pressed {
                background: #1e2636;
                border: 1px solid #22c55e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.chat_log.setHtml(
            "<span style='color: #38bdf8; font-weight: 700;'>SENTI:</span> "
            "<span style='color: #e2e8f0;'>All telemetry feeds green, sir. Ask me about your silicon, memory, or creator.</span>"
        )
        c3_lay.addWidget(self.chat_log)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.comm_prompt_input = QLineEdit()
        self.comm_prompt_input.setPlaceholderText("Ask Senti about CPU, RAM, thermals, creator...")
        self.comm_prompt_input.setStyleSheet("""
            QLineEdit {
                background: #141722;
                border: 1px solid #23293a;
                border-radius: 4px;
                color: #f8fafc;
                font-size: 10px;
                padding: 5px 10px;
                font-family: 'Segoe UI', Consolas;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background: #161b28;
            }
        """)

        btn_send = QPushButton("TRANSMIT ↵")
        btn_send.setFixedSize(86, 26)
        btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send.setStyleSheet("""
            QPushButton {
                background: #1a2234;
                color: #38bdf8;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.5px;
                border: 1px solid #283550;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #243048;
                color: #ffffff;
                border: 1px solid #38bdf8;
            }
            QPushButton:pressed {
                background: #141b2a;
            }
        """)

        def _send_msg():
            text = self.comm_prompt_input.text().strip()
            if not text:
                return
            self.comm_prompt_input.clear()
            play_sound("click", enabled=self.settings.is_sound_enabled())

            self.chat_log.append(f"<span style='color: #64748b; font-weight: 700;'>YOU:</span> <span style='color: #cbd5e1;'>{text}</span>")
            reply, mood = self.brain.respond(text, self._telemetry)

            accent = "#38bdf8" if mood in ("calm", "stark") else ("#22c55e" if mood == "wink" else "#ef4444")
            self.chat_log.append(f"<span style='color: {accent}; font-weight: 700;'>SENTI:</span> <span style='color: #f1f5f9;'>{reply}</span>")
            self.chat_log.verticalScrollBar().setValue(self.chat_log.verticalScrollBar().maximum())

        btn_send.clicked.connect(_send_msg)
        self.comm_prompt_input.returnPressed.connect(_send_msg)

        input_row.addWidget(self.comm_prompt_input, 1)
        input_row.addWidget(btn_send)
        c3_lay.addLayout(input_row)

        lay.addWidget(c3)
        lay.addStretch()

        def on_dial(idx: int, tname: str):
            t = THEME_DATA[idx]
            lbl_ch.setText(f"CHANNEL 0{idx + 1} / 0{len(THEME_DATA)}")
            lbl_theme_name.setText(tname.upper())
            lbl_theme_name.setStyleSheet(f"color: {t['accent']}; font-size: 20px; font-weight: 800; letter-spacing: 1px;")
            self.settings.apply_preset_theme(tname)
            if self.on_colors_changed:
                self.on_colors_changed()
            play_sound(f"tick_{idx % 8}", enabled=self.settings.is_sound_enabled())

        dial.themeChanged.connect(on_dial)
        return w

    # --- Telemetry Refresh Dispatcher ---
    def update_telemetry(self, data: Dict[str, Any]):
        """Live dashboard refresh called on each background polling tick."""
        if not data:
            return
        self._telemetry = data

        # 1. CPU
        cpu_val = data.get("cpu", 0.0)
        self.lbl_cpu_main.setText(f"CPU Load: {cpu_val:.1f}%")
        self.spark_cpu.add_sample(cpu_val)
        
        proc_str = data.get("processor", "CPU")
        self.lbl_cpu_model.setText(f"Processor: {proc_str}")
        
        freq = data.get("cpu_freq_mhz")
        self.lbl_cpu_freq.setText(f"Frequency: {freq:.0f} MHz" if freq else "Frequency: Optimal")

        # Dynamic Core Tiles: Handles any CPU core count (2, 4, 6, 8, 12, 16, 24, 32, 64+ cores)
        cores = data.get("cpu_cores") or []
        if not hasattr(self, "_cpu_tiles") or len(self._cpu_tiles) != len(cores):
            # Clear existing items
            while self.cores_grid.count():
                item = self.cores_grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._cpu_tiles = []
            self.core_labels = []
            self.core_bars = []

            cols = 4 if len(cores) >= 4 else max(1, len(cores))
            for i, val in enumerate(cores):
                tile = QFrame()
                tile.setFixedHeight(54)
                tile.setStyleSheet("""
                    QFrame {
                        background: #0d0e14;
                        border: 1px solid #1c2028;
                        border-radius: 6px;
                    }
                    QLabel {
                        border: none;
                        background: transparent;
                        padding: 0px;
                    }
                """)
                t_lay = QVBoxLayout(tile)
                t_lay.setContentsMargins(10, 8, 10, 8)
                t_lay.setSpacing(6)

                row = QHBoxLayout()
                # 1-indexed for end users: Core 1, Core 2, Core 3, etc.
                lbl_name = QLabel(f"Core {i + 1}")
                lbl_name.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
                lbl_pct = QLabel(f"{val:.0f}%")
                lbl_pct.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 700;")
                row.addWidget(lbl_name)
                row.addStretch()
                row.addWidget(lbl_pct)
                t_lay.addLayout(row)

                bar = SmoothBar(self)
                bar.setFixedHeight(5)
                bar.set_value(val)
                t_lay.addWidget(bar)

                r = i // cols
                c = i % cols
                self.cores_grid.addWidget(tile, r, c)
                self._cpu_tiles.append((lbl_pct, bar))
                self.core_labels.append(lbl_pct)
                self.core_bars.append(bar)

            self.cores_grid.setAlignment(Qt.AlignmentFlag.AlignTop)

            num_c = len(cores)
            phys = data.get("physical_cores", 0)
            phys_str = f" · {phys} PHYSICAL" if phys > 0 else ""
            self.lbl_cores_header.setText(f"LOGICAL CORES  ·  {num_c} THREADS ACTIVE{phys_str}")
        else:
            for (lbl_pct, bar), val in zip(self._cpu_tiles, cores):
                lbl_pct.setText(f"{val:.0f}%")
                bar.set_value(val)

        # Overview Stats Badges
        num_c = len(cores)
        phys = data.get("physical_cores", 0)
        self.lbl_cpu_threads.setText(f"{num_c} Logical")
        self.lbl_cpu_physical.setText(f"{phys} Physical" if phys > 0 else f"{num_c} Cores")
        self.lbl_cpu_cur_freq.setText(f"{freq:.0f} MHz" if freq else "Optimal")

        stats = data.get("cpu_stats") or {}
        threads_count = stats.get('thread_count', 0)
        self.lbl_cpu_active_threads.setText(f"{threads_count:,} Running")
        self.lbl_ctx_switches.setText(f"Context Switches: {stats.get('ctx_switches', 0):,}")
        self.lbl_interrupts.setText(f"Hardware Interrupts: {stats.get('interrupts', 0):,}")

        # 2. RAM
        ram_val = data.get("ram", 0.0)
        self.lbl_ram_main.setText(f"Memory: {ram_val:.1f}%")
        self.spark_ram.add_sample(ram_val)
        ram_d = data.get("ram_details") or {}
        used = ram_d.get("used_gb", 0.0)
        total = ram_d.get("total_gb", 0.0)
        self.lbl_ram_gb.setText(f"Used: {used:.2f} GB / Total: {total:.2f} GB")
        self.lbl_ram_inuse.setText(f"{used:.2f} GB")
        self.lbl_ram_avail.setText(f"{ram_d.get('available_gb', 0.0):.2f} GB")
        cached = ram_d.get('cached_gb', 0.0)
        self.lbl_ram_cached.setText(f"{(cached * 1024):.0f} MB" if cached < 1.0 else f"{cached:.2f} GB")
        free = ram_d.get('free_gb', 0.0)
        self.lbl_ram_free.setText(f"{(free * 1024):.0f} MB" if free < 1.0 else f"{free:.2f} GB")

        swap_used = ram_d.get("swap_used_gb", 0.0)
        swap_total = ram_d.get("swap_total_gb", 0.0)
        swap_pct = ram_d.get("swap_percent", 0.0)
        self.lbl_swap.setText(f"Paging File: {swap_used:.2f} GB / {swap_total:.2f} GB ({swap_pct:.1f}%)")
        self.bar_swap.set_value(swap_pct)

        # 3. DISK
        disk_val = data.get("disk", 0.0)
        self.spark_disk.add_sample(disk_val)
        disk_d = data.get("disk_details") or {}
        r_mb = disk_d.get("read_mb_s", 0.0)
        w_mb = disk_d.get("write_mb_s", 0.0)
        self.lbl_disk_read.setText(f"Read: {r_mb:.2f} MB/s")
        self.lbl_disk_write.setText(f"Write: {w_mb:.2f} MB/s")

        # Rebuild or update partition cards smoothly
        parts = disk_d.get("partitions") or []
        if not hasattr(self, "_disk_card_widgets") or len(self._disk_card_widgets) != len(parts):
            while self.disk_part_layout.count():
                item = self.disk_part_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._disk_card_widgets = []
            for p in parts:
                pf = QFrame()
                pf.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
                pflay = QVBoxLayout(pf)
                pflay.setSpacing(6)
                header = QLabel(f"Volume {p['mountpoint']} [{p['fstype']}]  ·  {p['used_gb']:.1f} GB of {p['total_gb']:.1f} GB ({p['percent']:.0f}%)")
                header.setStyleSheet("color: #f8fafc; font-size: 11px; font-weight: 600;")
                pbar = SmoothBar(self)
                pbar.setFixedHeight(6)
                pbar.set_value(p["percent"])
                pflay.addWidget(header)
                pflay.addWidget(pbar)
                self.disk_part_layout.addWidget(pf)
                self._disk_card_widgets.append((header, pbar))
            self.disk_part_layout.addStretch()
        else:
            for (header, pbar), p in zip(self._disk_card_widgets, parts):
                header.setText(f"Volume {p['mountpoint']} [{p['fstype']}]  ·  {p['used_gb']:.1f} GB of {p['total_gb']:.1f} GB ({p['percent']:.0f}%)")
                pbar.set_value(p["percent"])

        # 4. TEMP
        temp_val = data.get("temperature_c")
        if temp_val is not None:
            self.lbl_temp_main.setText(f"Package Temp: {temp_val:.1f}°C")
            self.spark_temp.add_sample(temp_val)
            if temp_val >= 85.0:
                self.lbl_temp_status.setText("CRITICAL THERMAL THROTTLING")
                self.lbl_temp_status.setStyleSheet("color: #ff3b4a; font-size: 12px; font-weight: 700;")
            elif temp_val >= 75.0:
                self.lbl_temp_status.setText("Elevated Load Temp")
                self.lbl_temp_status.setStyleSheet("color: #f5a524; font-size: 12px; font-weight: 600;")
            else:
                self.lbl_temp_status.setText("Optimal Operating Temp")
                self.lbl_temp_status.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 600;")
            self.lbl_cpu_temp.setText(f"CPU Thermal Sensor: {temp_val:.1f}°C (Active ACPI Reading)")
        else:
            self.lbl_temp_main.setText("Package Temp: Not Available")
            self.lbl_temp_status.setText("Thermal Sensor: Not available for your device")
            self.lbl_temp_status.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
            self.lbl_cpu_temp.setText("CPU Thermal Sensor: Not available for your device hardware")

        # 5. GPU
        gpu_val = data.get("gpu_load", 0.0)
        self.lbl_gpu_main.setText(f"GPU Load: {gpu_val:.1f}%")
        self.spark_gpu.add_sample(gpu_val)
        gpu_d = data.get("gpu_details") or {}
        self.lbl_gpu_name.setText(f"Adapter: {gpu_d.get('name', 'Generic Video Controller')}")
        v_total = gpu_d.get("vram_total_gb")
        v_used = gpu_d.get("vram_used_gb", 0.0)
        if v_total:
            self.lbl_vram.setText(f"Dedicated Video Memory: {v_used:.2f} GB / {v_total:.2f} GB")
            self.bar_vram.set_value((v_used / v_total) * 100.0)
        else:
            self.lbl_vram.setText("Dedicated Video Memory: Shared System Memory")
            self.bar_vram.set_value(gpu_val)
        self.lbl_gpu_driver.setText(f"Driver Version: {gpu_d.get('driver', 'Standard')}")

        # 6. NETWORK (3 Live Telemetry Graphs)
        net_d = data.get("net_details") or {}
        r_kb = net_d.get("recv_kb_s", 0.0)
        s_kb = net_d.get("sent_kb_s", 0.0)
        total_recv = net_d.get("total_recv_mb", 0.0)
        total_sent = net_d.get("total_sent_mb", 0.0)

        self.lbl_net_down.setText(f"{r_kb:.1f} KB/s" if r_kb < 1024 else f"{(r_kb/1024):.2f} MB/s")
        self.lbl_net_up.setText(f"{s_kb:.1f} KB/s" if s_kb < 1024 else f"{(s_kb/1024):.2f} MB/s")
        self.lbl_net_total_down.setText(f"Total Recv: {total_recv:.1f} MB" if total_recv < 1024 else f"{(total_recv/1024):.2f} GB")
        self.lbl_net_total_up.setText(f"Total Sent: {total_sent:.1f} MB" if total_sent < 1024 else f"{(total_sent/1024):.2f} GB")

        self.spark_net_down.add_sample(r_kb)
        self.spark_net_up.add_sample(s_kb)

        ping = net_d.get("ping_ms")
        if ping is not None:
            self.lbl_ping.setText(f"{ping:.0f} ms")
            self.spark_net_ping.add_sample(ping)
            if ping < 60:
                self.lbl_ping_status.setText("Optimal Latency (<60ms) · Target: 8.8.8.8")
            elif ping < 150:
                self.lbl_ping_status.setText("Moderate Latency · Target: 8.8.8.8")
            else:
                self.lbl_ping_status.setText("High Latency Warning · Target: 8.8.8.8")
        else:
            self.lbl_ping.setText("Offline / Checking...")
            self.lbl_ping_status.setText("Target: 8.8.8.8 (Waiting for ping response)")

        # 7. SYSTEM
        self.lbl_sys_os.setText(f"Operating System: {data.get('os', 'Windows')}")
        self.lbl_sys_host.setText(f"Hostname: {data.get('hostname', 'Unknown')}")
        self.lbl_sys_proc.setText(f"Processor: {data.get('processor', 'CPU')}")
        uptime = data.get("uptime_seconds", 0)
        days = uptime // 86400
        hrs = (uptime % 86400) // 3600
        mins = (uptime % 3600) // 60
        secs = uptime % 60
        self.lbl_sys_uptime.setText(f"Continuous Uptime: {days}d {hrs}h {mins}m {secs}s")

        bat = data.get("battery")
        plugged = data.get("battery_plugged")
        if bat is not None:
            plug_str = "Plugged In (AC)" if plugged else "On Battery"
            self.lbl_battery.setText(f"Battery: {bat:.0f}% · {plug_str}")
            self.bar_battery.set_value(bat)
        else:
            self.lbl_battery.setText("Battery: Desktop Workstation (AC Line Power)")
            self.bar_battery.set_value(100.0)

    # --- Comm Link Chat Management ---
    def flush_comm_link_chat(self):
        """Purge Comm Link conversation history back to clean baseline greeting."""
        if hasattr(self, "chat_log") and self.chat_log:
            self.chat_log.setHtml(
                "<span style='color: #38bdf8; font-weight: 700;'>SENTI:</span> "
                "<span style='color: #e2e8f0;'>All telemetry feeds green, sir. Ask me about your silicon, memory, or creator.</span>"
            )
        if hasattr(self, "comm_prompt_input") and self.comm_prompt_input:
            self.comm_prompt_input.clear()

    # --- Window Open / Dedicated Panel Navigation ---
    def open_tab(self, tab_name: str):
        """Open the dedicated window showing ONLY the requested tab. No other tabs appear."""
        name_map = {
            "CPU": (0, "CPU", "#22c55e"),
            "RAM": (1, "MEMORY", "#f5a524"),
            "MEMORY": (1, "MEMORY", "#f5a524"),
            "GPU": (2, "GPU", "#00e5ff"),
            "NETWORK": (3, "NETWORK", "#a855f7"),
            "NET": (3, "NETWORK", "#a855f7"),
            "STORAGE": (4, "STORAGE", "#6366f1"),
            "DISK": (4, "STORAGE", "#6366f1"),
            "THERMALS": (5, "THERMALS", "#f4505e"),
            "TEMP": (5, "THERMALS", "#f4505e"),
            "SYSTEM": (6, "SYSTEM", "#10b981"),
            "SYS": (6, "SYSTEM", "#10b981"),
            "BAT": (6, "SYSTEM", "#10b981"),
            "BATTERY": (6, "SYSTEM", "#10b981"),
            "SETTINGS": (7, "SETTINGS", "#e2e8f0"),
            "SET": (7, "SETTINGS", "#e2e8f0"),
            "PREF": (7, "SETTINGS", "#e2e8f0"),
            "CONFIG": (7, "SETTINGS", "#e2e8f0"),
        }
        normalized = tab_name.upper()
        if normalized not in ("SETTINGS", "SET", "PREF", "CONFIG"):
            self.flush_comm_link_chat()

        info = name_map.get(normalized, (0, "CPU", "#22c55e"))
        idx, title_text, accent_color = info

        self._active_tab_name = TAB_CANONICAL.get(normalized, normalized)

        # Immediate, deterministic tab switch - synchronous, instant, rock-solid
        self.tabs.setCurrentIndex(idx)
        self.lbl_title.setText(f"SENTINEL  ·  {title_text}")
        self.lbl_title.setStyleSheet(f"color: {accent_color}; font-size: 11px; font-weight: 700; letter-spacing: 2px;")

        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1c2028;
                border-radius: 8px;
                background: #111317;
                top: 0px;
            }
        """)
        self.update()

        if not self.isVisible() or self._opacity_effect.opacity() < 0.2:
            self.show()
            self.raise_()
            self.activateWindow()
            self._fade_anim.stop()
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.start()
        else:
            self.raise_()
            self.activateWindow()

    def get_active_tab(self) -> Optional[str]:
        """Return the canonical name of the active subsystem tab, or None if panel is hidden/closed."""
        if not self.isVisible() or not getattr(self, "_active_tab_name", None):
            return None
        return self._active_tab_name

    def toggle_instructions_drawer(self):
        """Toggle the right-side User Guide & Instructions pop-out drawer."""
        if hasattr(self, "instructions_panel") and self.instructions_panel.isVisible():
            self.instructions_panel.hide()
            self.setFixedSize(720, 570)
            self.resize(720, 570)
            if getattr(self, "_pre_instructions_pos", None) is not None:
                self.move(self._pre_instructions_pos)
                self._pre_instructions_pos = None
        else:
            self._pre_instructions_pos = self.pos()
            self.instructions_panel.show()
            target_w = 1180
            screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
            if screen:
                screen_geo = screen.availableGeometry()
                if self.x() + target_w > screen_geo.right() - 10:
                    new_x = max(screen_geo.left() + 10, screen_geo.right() - target_w - 10)
                    self.move(new_x, self.y())
            self.setFixedSize(target_w, 570)
            self.resize(target_w, 570)
        self.update()

    def _build_instructions_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(440)
        panel.setStyleSheet("""
            QFrame#InstructionsPanelRoot {
                background: #06070a;
                border: 1px solid #161922;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        panel.setObjectName("InstructionsPanelRoot")
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(18, 14, 18, 14)
        panel_lay.setSpacing(12)

        # Header bar
        hdr_row = QHBoxLayout()
        lbl_title = QLabel("SENTINEL  ·  INSTRUCTIONS")
        lbl_title.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700; letter-spacing: 2px;")
        hdr_row.addWidget(lbl_title)
        hdr_row.addStretch()

        btn_close = QPushButton("CLOSE  ✕")
        btn_close.setFixedHeight(22)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #0f121a;
                color: #8c9dbd;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.5px;
                border: 1px solid #1e2433;
                border-radius: 4px;
                padding: 0px 10px;
            }
            QPushButton:hover {
                background: #181d2a;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        btn_close.clicked.connect(self.toggle_instructions_drawer)
        hdr_row.addWidget(btn_close)
        panel_lay.addLayout(hdr_row)

        # Hairline divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #161922; border: none;")
        panel_lay.addWidget(div)

        # Scroll Area with custom 3D luxury cyan scrollbar
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #06070a;
                width: 6px;
                border-radius: 3px;
                margin: 2px 0 2px 0;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0ea5e9, stop:1 #0284c7);
                min-height: 32px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38bdf8, stop:1 #0284c7);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 4, 10, 4)
        c_lay.setSpacing(16)

        def add_instruction_section(category: str, color: str, items: list):
            lbl_cat = QLabel(category)
            lbl_cat.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 800; letter-spacing: 1.5px;")
            c_lay.addWidget(lbl_cat)

            for action, desc in items:
                row = QLabel(f"""
                    <div style="line-height: 1.45; margin-bottom: 2px;">
                        <span style="color: #f1f5f9; font-weight: 700; font-size: 11px;">• {action}</span><br>
                        <span style="color: #8c9dbd; font-size: 11px; padding-left: 12px;">{desc}</span>
                    </div>
                """)
                row.setWordWrap(True)
                row.setTextFormat(Qt.TextFormat.RichText)
                c_lay.addWidget(row)

        # 1. COMPANION INTERACTION & EMOTIONS
        add_instruction_section("COMPANION INTERACTION & EMOTIONS", "#38bdf8", [
            ("Click Senti (Docked in Island)",
             "Triggers expressive emotional reactions (Shocked, Annoyed, Wink, Loved, Dizzy) with synthesized audio feedback and physics VFX. Governed by a 2.0-second cooldown gate to ensure animations complete smoothly."),
            ("Left-Click & Drag (Undock to Desktop)",
             "Pulls Senti out of his top Island nest into a free-floating companion. Position him anywhere across your screens for continuous desktop companionship."),
            ("Double-Click Floating Companion (Recall to Island)",
             "Engages automated home navigation, smoothly flying Senti across your desktop back into the top Dynamic Island dock.")
        ])

        # 2. COMPACT ORB & TRAY SHORTCUTS
        add_instruction_section("COMPACT ORB & TRAY SHORTCUTS", "#a855f7", [
            ("Middle-Click Floating Companion (Desktop Orb Mode)",
             "Morphs the full robot body into a high-density, minimalist metallic Orb. Designed for zero-distraction monitoring when screen real estate is limited."),
            ("Double-Click Desktop Orb (Restore Companion)",
             "Expands the compact Orb back into the fully articulated Senti astronaut avatar."),
            ("Single-Click Floating Senti / Orb (Hide to Tray)",
             "Instantly minimizes Senti into the Windows Taskbar Notification Area (System Tray). Click the tray icon at any time to summon him back."),
            ("Right-Click Senti / Desktop Orb (Quick Context Menu)",
             "Opens a context menu to toggle Orb mode, launch telemetry dashboards, recall Senti to the Island, or safely quit.")
        ])

        # 3. DYNAMIC ISLAND & TELEMETRY
        add_instruction_section("DYNAMIC ISLAND & TELEMETRY", "#22c55e", [
            ("Cursor Proximity Hover (Procedural Gaze Tracking)",
             "Move your cursor across the 8 telemetry pills (CPU, RAM, GPU, NET, DISK, TEMP, BAT, CONFIG). Senti turns his gaze to follow your cursor, accompanied by harmonic acoustic chimes."),
            ("Click Any Telemetry Metric (Deep Diagnostics)",
             "Opens the dedicated real-time hardware diagnostics dashboard for that subsystem, displaying live load graphs, memory allocation, and performance metrics."),
            ("Click Config / Set Pill (Settings & Manual)",
             "Opens this Command Matrix window to adjust themes, interact via COM-link, or reference this instructions guide.")
        ])

        # 4. THEME MATRIX & COMMAND COMMS
        add_instruction_section("THEME MATRIX & COMMAND COMMS", "#f59e0b", [
            ("Rotary Theme Dial (Rotate to Switch LED Spectrum)",
             "Rotate the tactile dial in Settings to cycle through 5 workstation themes (Cyberpunk Cyan, Toxic Green, Solar Flare, Neon Violet, Crimson Void). Updates all dashboard accents, Island illumination, and Senti's LED suit trim."),
            ("Senti Comms Console (Telemetry Intelligence Terminal)",
             "Type natural-language queries into the terminal (e.g., asking about CPU load, memory usage, GPU thermals, system health, or creator details) and press TRANSMIT ↵ or Enter for instantaneous diagnostic evaluation and companion dialogue.")
        ])

        c_lay.addStretch()
        scroll.setWidget(container)
        panel_lay.addWidget(scroll)

        return panel

    def close_panel(self):
        self._active_tab_name = None
        self.flush_comm_link_chat()
        if hasattr(self, "instructions_panel") and self.instructions_panel.isVisible():
            self.instructions_panel.hide()
            self.setFixedSize(720, 570)
            self.resize(720, 570)
            if getattr(self, "_pre_instructions_pos", None) is not None:
                self.move(self._pre_instructions_pos)
                self._pre_instructions_pos = None
        self.update()
        self.closed.emit()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)

        def _on_done():
            self.hide()
            try:
                self._fade_anim.finished.disconnect(_on_done)
            except Exception:
                pass

        self._fade_anim.finished.connect(_on_done)
        self._fade_anim.start()

    def closeEvent(self, event):
        self._active_tab_name = None
        self.flush_comm_link_chat()
        if hasattr(self, "instructions_panel") and self.instructions_panel.isVisible():
            self.instructions_panel.hide()
            self.setFixedSize(720, 570)
            self.resize(720, 570)
            if getattr(self, "_pre_instructions_pos", None) is not None:
                self.move(self._pre_instructions_pos)
                self._pre_instructions_pos = None
        self.update()
        self.closed.emit()
        super().closeEvent(event)

    def hideEvent(self, event):
        self._active_tab_name = None
        self.flush_comm_link_chat()
        if hasattr(self, "instructions_panel") and self.instructions_panel.isVisible():
            self.instructions_panel.hide()
            self.setFixedSize(720, 570)
            self.resize(720, 570)
            if getattr(self, "_pre_instructions_pos", None) is not None:
                self.move(self._pre_instructions_pos)
                self._pre_instructions_pos = None
        self.update()
        self.closed.emit()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_panel()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._press_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and self._press_pos:
            self.move(event.globalPosition().toPoint() - self._press_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        event.accept()

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
            p.setPen(QPen(QColor("#20242c"), 1.2))
            p.setBrush(QColor("#090a0d"))
            p.drawRoundedRect(rect, 14.0, 14.0)
        finally:
            p.end()
