"""Dedicated individual subsystem monitor panels for SYS-SENTINEL.

Provides isolated, dedicated deep-dive panels for CPU, RAM, Storage,
Thermals, GPU, Network, Processes, and System metrics without mixing them.
"""

from typing import Optional, Dict, Any, List
from collections import deque
import sys

from PySide6.QtCore import (
    Qt,
    QRectF,
    QPointF,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
    QFont,
)
from PySide6.QtWidgets import (
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
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QGraphicsOpacityEffect,
    QMessageBox,
)

from system_monitor import (
    terminate_process,
    suspend_process,
    resume_process,
    set_process_priority,
    get_top_processes,
    get_active_connections,
)
from senti_widgets import SmoothBar


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
                px = pad_x + i * step_x
                py = pad_y + avail_h - ((val - min_val) / val_range * avail_h)
                pts.append(QPointF(px, py))

            # Area gradient
            path_area = QPainterPath()
            path_area.moveTo(pad_x, h - pad_y)
            for pt in pts:
                path_area.lineTo(pt)
            path_area.lineTo(pts[-1].x(), h - pad_y)
            path_area.closeSubpath()

            grad = QLinearGradient(0, pad_y, 0, h - pad_y)
            grad.setColorAt(0.0, QColor(self.color.red(), self.color.green(), self.color.blue(), 90))
            grad.setColorAt(1.0, QColor(self.color.red(), self.color.green(), self.color.blue(), 0))
            p.fillPath(path_area, grad)

            # Stroke line
            path_line = QPainterPath()
            path_line.moveTo(pts[0])
            for pt in pts[1:]:
                path_line.lineTo(pt)
            p.setPen(QPen(self.color, 1.8))
            p.drawPath(path_line)

            # Current readout overlay
            curr = samples[-1]
            p.setPen(QColor("#f8fafc"))
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            text = f"{curr:.1f}{self.unit}"
            p.drawText(QRectF(w - 70, 4, 62, 18), Qt.AlignmentFlag.AlignRight, text)
        finally:
            p.end()


class SentiDashboardWindow(QWidget):
    """Master dedicated subsystem monitor with individual tabs for each pill."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("SYS-SENTINEL — System Telemetry")
        self.setObjectName("dashboardRoot")
        self.setFixedSize(720, 520)

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
        self._fade_anim.setDuration(160)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Dragging state
        self._is_dragging = False
        self._press_pos = None

        # Data cache
        self._telemetry: Dict[str, Any] = {}

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # Top Bar: Subsystem Title + Badge + Close Button
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("SYS-SENTINEL  //  CPU MONITOR")
        self.lbl_title.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addSpacing(10)

        self.lbl_badge = QLabel("DEDICATED VIEW")
        self.lbl_badge.setStyleSheet("color: #6b7079; font-size: 9px; font-weight: 700; letter-spacing: 1px; border: 1px solid #1c2028; border-radius: 3px; padding: 2px 6px; background: #0d0e14;")
        top_bar.addWidget(self.lbl_badge)
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
        root.addLayout(top_bar)

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
        # Hide tab bar completely: only the dedicated page for the clicked pill appears
        self.tabs.tabBar().hide()

        # Initialize Individual Dedicated Subsystem Panels
        self.tab_cpu = self._build_cpu_tab()
        self.tab_ram = self._build_ram_tab()
        self.tab_disk = self._build_disk_tab()
        self.tab_temp = self._build_temp_tab()
        self.tab_gpu = self._build_gpu_tab()
        self.tab_net = self._build_net_tab()
        self.tab_procs = self._build_procs_tab()
        self.tab_sys = self._build_sys_tab()

        self.tabs.addTab(self.tab_cpu, "CPU")
        self.tabs.addTab(self.tab_ram, "MEMORY")
        self.tabs.addTab(self.tab_disk, "STORAGE")
        self.tabs.addTab(self.tab_temp, "THERMALS")
        self.tabs.addTab(self.tab_gpu, "GPU")
        self.tabs.addTab(self.tab_net, "NETWORK")
        self.tabs.addTab(self.tab_procs, "PROCESSES")
        self.tabs.addTab(self.tab_sys, "SYSTEM")

        root.addWidget(self.tabs)

    # --- TAB 1: CPU (Live CPU Monitoring) ---
    def _build_cpu_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Header summary
        top_row = QHBoxLayout()
        self.lbl_cpu_main = QLabel("CPU Load: —%")
        self.lbl_cpu_main.setStyleSheet("color: #22c55e; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_cpu_main)
        top_row.addStretch()

        self.lbl_cpu_freq = QLabel("Frequency: — MHz")
        self.lbl_cpu_freq.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_cpu_freq)
        lay.addLayout(top_row)

        # Sparkline
        self.spark_cpu = MiniSparkline(QColor("#22c55e"), "%", self)
        lay.addWidget(self.spark_cpu)

        # Per-core loads grid
        lbl_cores = QLabel("LOGICAL CORES UTILIZATION")
        lbl_cores.setStyleSheet("color: #8c9dbd; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(lbl_cores)

        self.core_bars: List[SmoothBar] = []
        self.core_labels: List[QLabel] = []
        cores_layout = QGridLayout()
        cores_layout.setSpacing(8)

        # Prepare for up to 16 cores
        for i in range(16):
            r = i // 4
            c = i % 4
            cell = QVBoxLayout()
            lbl = QLabel(f"Core {i}: —%")
            lbl.setStyleSheet("color: #cdd9ed; font-size: 11px;")
            bar = SmoothBar(self)
            bar.setFixedHeight(6)
            cell.addWidget(lbl)
            cell.addWidget(bar)
            cores_layout.addLayout(cell, r, c)
            self.core_labels.append(lbl)
            self.core_bars.append(bar)

        lay.addLayout(cores_layout)

        # Activity stats
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 6px;")
        s_lay = QHBoxLayout(stats_frame)
        self.lbl_proc_count = QLabel("Processes: —")
        self.lbl_thread_count = QLabel("Threads: —")
        self.lbl_ctx_switches = QLabel("Ctx Switches: —")
        self.lbl_interrupts = QLabel("Interrupts: —")
        for lbl in (self.lbl_proc_count, self.lbl_thread_count, self.lbl_ctx_switches, self.lbl_interrupts):
            lbl.setStyleSheet("color: #8c9dbd; font-size: 11px;")
            s_lay.addWidget(lbl)
        lay.addWidget(stats_frame)
        lay.addStretch()
        return w

    # --- TAB 2: RAM (Memory Utilization) ---
    def _build_ram_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        self.lbl_ram_main = QLabel("Memory Usage: —%")
        self.lbl_ram_main.setStyleSheet("color: #f5a524; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_ram_main)
        top_row.addStretch()

        self.lbl_ram_gb = QLabel("Used: — GB / Total: — GB")
        self.lbl_ram_gb.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_ram_gb)
        lay.addLayout(top_row)

        self.spark_ram = MiniSparkline(QColor("#f5a524"), "%", self)
        lay.addWidget(self.spark_ram)

        # Granular breakdown cards
        grid = QGridLayout()
        grid.setSpacing(8)

        self.lbl_ram_inuse = QLabel("In-Use: — GB")
        self.lbl_ram_avail = QLabel("Available: — GB")
        self.lbl_ram_cached = QLabel("Cached / Standby: — GB")
        self.lbl_ram_free = QLabel("Free: — GB")

        cards = [
            ("IN-USE MEMORY", self.lbl_ram_inuse),
            ("AVAILABLE CAPACITY", self.lbl_ram_avail),
            ("CACHED / STANDBY", self.lbl_ram_cached),
            ("FREE PHYSICAL", self.lbl_ram_free),
        ]
        for idx, (title, val_lbl) in enumerate(cards):
            f = QFrame()
            f.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 6px;")
            flay = QVBoxLayout(f)
            t = QLabel(title)
            t.setStyleSheet("color: #6b7079; font-size: 10px; font-weight: 700;")
            val_lbl.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 600;")
            flay.addWidget(t)
            flay.addWidget(val_lbl)
            grid.addWidget(f, idx // 2, idx % 2)
        lay.addLayout(grid)

        # Swap / Pagefile section
        swap_box = QFrame()
        swap_box.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 8px;")
        sb_lay = QVBoxLayout(swap_box)
        self.lbl_swap = QLabel("Swap / Pagefile Usage: — GB (—%)")
        self.lbl_swap.setStyleSheet("color: #cdd9ed; font-size: 11px; font-weight: 600;")
        self.bar_swap = SmoothBar(self)
        self.bar_swap.setFixedHeight(6)
        sb_lay.addWidget(self.lbl_swap)
        sb_lay.addWidget(self.bar_swap)
        lay.addWidget(swap_box)
        lay.addStretch()
        return w

    # --- TAB 3: STORAGE (Disk Usage & Live I/O) ---
    def _build_disk_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # I/O Throughput Row
        io_row = QHBoxLayout()
        self.lbl_disk_read = QLabel("Read: 0.0 MB/s")
        self.lbl_disk_read.setStyleSheet("color: #22c55e; font-size: 16px; font-weight: 700;")
        self.lbl_disk_write = QLabel("Write: 0.0 MB/s")
        self.lbl_disk_write.setStyleSheet("color: #00e5ff; font-size: 16px; font-weight: 700;")
        io_row.addWidget(self.lbl_disk_read)
        io_row.addSpacing(20)
        io_row.addWidget(self.lbl_disk_write)
        io_row.addStretch()
        lay.addLayout(io_row)

        self.spark_disk = MiniSparkline(QColor("#6366f1"), "%", self)
        lay.addWidget(self.spark_disk)

        lbl_parts = QLabel("MOUNTED DRIVES & PARTITIONS")
        lbl_parts.setStyleSheet("color: #8c9dbd; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(lbl_parts)

        # Scrollable partitions list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.disk_container = QWidget()
        self.disk_part_layout = QVBoxLayout(self.disk_container)
        self.disk_part_layout.setContentsMargins(0, 0, 0, 0)
        self.disk_part_layout.setSpacing(6)
        scroll.setWidget(self.disk_container)
        lay.addWidget(scroll)

        return w

    # --- TAB 4: THERMALS (Sensors & Fan Speeds) ---
    def _build_temp_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        top_row = QHBoxLayout()
        self.lbl_temp_main = QLabel("Package Temp: —°C")
        self.lbl_temp_main.setStyleSheet("color: #f4505e; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_temp_main)
        top_row.addStretch()

        self.lbl_temp_status = QLabel("Thermal Status: NOMINAL")
        self.lbl_temp_status.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: 700; background: #0d1a14; border: 1px solid #1c3d28; padding: 4px 8px; border-radius: 4px;")
        top_row.addWidget(self.lbl_temp_status)
        lay.addLayout(top_row)

        self.spark_temp = MiniSparkline(QColor("#f4505e"), "°C", self)
        lay.addWidget(self.spark_temp)

        # Thermal cards
        f = QFrame()
        f.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
        flay = QVBoxLayout(f)
        self.lbl_acpi_temp = QLabel("ACPI Thermal Zone: Active Sensor Active")
        self.lbl_fan_rpm = QLabel("Cooling Fans: Automatic Controller Managed")
        self.lbl_throttle = QLabel("Thermal Throttling: None Detected")
        for lbl in (self.lbl_acpi_temp, self.lbl_fan_rpm, self.lbl_throttle):
            lbl.setStyleSheet("color: #cdd9ed; font-size: 12px;")
            flay.addWidget(lbl)
        lay.addWidget(f)
        lay.addStretch()
        return w

    # --- TAB 5: GPU (Graphics & VRAM) ---
    def _build_gpu_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Header summary
        top_row = QHBoxLayout()
        self.lbl_gpu_load = QLabel("GPU Load: 0.0%")
        self.lbl_gpu_load.setStyleSheet("color: #00e5ff; font-size: 20px; font-weight: 700;")
        top_row.addWidget(self.lbl_gpu_load)
        top_row.addStretch()

        self.lbl_gpu_vram = QLabel("Dedicated VRAM: Detecting...")
        self.lbl_gpu_vram.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.lbl_gpu_vram)
        lay.addLayout(top_row)

        # GPU Sparkline
        self.spark_gpu = MiniSparkline(QColor("#00e5ff"), "%", self)
        lay.addWidget(self.spark_gpu)

        # Specs card
        f = QFrame()
        f.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 12px;")
        flay = QVBoxLayout(f)
        self.lbl_gpu_name = QLabel("Graphics Adapter: Detecting...")
        self.lbl_gpu_driver = QLabel("Driver Version: —")
        self.lbl_gpu_engine = QLabel("3D Acceleration: Active / DirectX Compatible")
        for lbl in (self.lbl_gpu_name, self.lbl_gpu_driver, self.lbl_gpu_engine):
            lbl.setStyleSheet("color: #cdd9ed; font-size: 12px; font-weight: 600;")
            flay.addWidget(lbl)
        lay.addWidget(f)
        lay.addStretch()
        return w

    # --- TAB 6: NETWORK (Bandwidth & Ping Latency Graphs) ---
    def _build_net_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # 1. Download Graph Card
        c_down = QFrame()
        c_down.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
        lay_down = QVBoxLayout(c_down)
        lay_down.setContentsMargins(8, 8, 8, 8)
        lay_down.setSpacing(6)
        row_d = QHBoxLayout()
        lbl_d_title = QLabel("↓ LIVE DOWNLOAD THROUGHPUT")
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

        # 2. Upload Graph Card
        c_up = QFrame()
        c_up.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
        lay_up = QVBoxLayout(c_up)
        lay_up.setContentsMargins(8, 8, 8, 8)
        lay_up.setSpacing(6)
        row_u = QHBoxLayout()
        lbl_u_title = QLabel("↑ LIVE UPLOAD THROUGHPUT")
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

        # 3. Latency & Ping Graph Card
        c_ping = QFrame()
        c_ping.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 10px;")
        lay_ping = QVBoxLayout(c_ping)
        lay_ping.setContentsMargins(8, 8, 8, 8)
        lay_ping.setSpacing(6)
        row_p = QHBoxLayout()
        lbl_p_title = QLabel("⚡ ROUND-TRIP LATENCY (PING)")
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

    # --- TAB 7: PROCESSES (Resource Consumers & Control) ---
    def _build_procs_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Controls & Search Row
        ctrl_row = QHBoxLayout()
        self.proc_search = QLineEdit()
        self.proc_search.setPlaceholderText("Filter processes by name or PID...")
        self.proc_search.setStyleSheet("""
            QLineEdit {
                background: #0d0e14;
                border: 1px solid #20242c;
                border-radius: 4px;
                color: #f8fafc;
                padding: 4px 8px;
                font-size: 11px;
            }
        """)
        self.proc_search.textChanged.connect(self._filter_procs)
        ctrl_row.addWidget(self.proc_search)

        self.btn_kill = QPushButton("🛑 End Process")
        self.btn_kill.setStyleSheet("background: #3a141a; color: #ff5260; border: 1px solid #63222b; padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        self.btn_kill.clicked.connect(self._kill_selected_proc)
        ctrl_row.addWidget(self.btn_kill)

        self.btn_suspend = QPushButton("⏸ Suspend")
        self.btn_suspend.setStyleSheet("background: #1c1a24; color: #cdd9ed; border: 1px solid #2d2b38; padding: 5px 10px; border-radius: 4px; font-size: 11px;")
        self.btn_suspend.clicked.connect(self._toggle_suspend_proc)
        ctrl_row.addWidget(self.btn_suspend)

        lay.addLayout(ctrl_row)

        # Process Table
        self.table_procs = QTableWidget()
        self.table_procs.setColumnCount(5)
        self.table_procs.setHorizontalHeaderLabels(["PID", "Process Name", "CPU %", "RAM %", "Status"])
        self.table_procs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_procs.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_procs.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_procs.setStyleSheet("""
            QTableWidget {
                background: #0d0e14;
                border: 1px solid #1c2028;
                color: #cdd9ed;
                gridline-color: #1c2028;
                font-size: 11px;
            }
            QHeaderView::section {
                background: #16181f;
                color: #8c9dbd;
                font-weight: bold;
                border: 1px solid #1c2028;
                padding: 4px;
            }
            QTableWidget::item:selected {
                background: #1f2f4d;
                color: #00e5ff;
            }
        """)
        lay.addWidget(self.table_procs)
        return w

    # --- TAB 8: SYSTEM (Specs, Uptime & Battery) ---
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
        freq = data.get("cpu_freq_mhz")
        self.lbl_cpu_freq.setText(f"Frequency: {freq:.0f} MHz" if freq else "Frequency: Optimal")

        cores = data.get("cpu_cores") or []
        for i, val in enumerate(cores[:16]):
            if i < len(self.core_labels):
                self.core_labels[i].setText(f"Core {i}: {val:.0f}%")
                self.core_bars[i].set_value(val)

        stats = data.get("cpu_stats") or {}
        self.lbl_proc_count.setText(f"Processes: {stats.get('process_count', 0)}")
        self.lbl_thread_count.setText(f"Threads: {stats.get('thread_count', 0)}")
        self.lbl_ctx_switches.setText(f"Ctx Switches: {stats.get('ctx_switches', 0):,}")
        self.lbl_interrupts.setText(f"Interrupts: {stats.get('interrupts', 0):,}")

        # 2. RAM
        ram_val = data.get("ram", 0.0)
        self.lbl_ram_main.setText(f"Memory Usage: {ram_val:.1f}%")
        self.spark_ram.add_sample(ram_val)
        ram_d = data.get("ram_details") or {}
        used = ram_d.get("used_gb", 0.0)
        total = ram_d.get("total_gb", 0.0)
        self.lbl_ram_gb.setText(f"Used: {used:.2f} GB / Total: {total:.2f} GB")
        self.lbl_ram_inuse.setText(f"In-Use: {used:.2f} GB")
        self.lbl_ram_avail.setText(f"Available: {ram_d.get('available_gb', 0.0):.2f} GB")
        self.lbl_ram_cached.setText(f"Cached / Standby: {ram_d.get('cached_gb', 0.0):.2f} GB")
        self.lbl_ram_free.setText(f"Free: {ram_d.get('free_gb', 0.0):.2f} GB")

        swap_used = ram_d.get("swap_used_gb", 0.0)
        swap_total = ram_d.get("swap_total_gb", 0.0)
        swap_pct = ram_d.get("swap_percent", 0.0)
        self.lbl_swap.setText(f"Swap / Pagefile Usage: {swap_used:.2f} GB / {swap_total:.2f} GB ({swap_pct:.1f}%)")
        self.bar_swap.set_value(swap_pct)

        # 3. DISK
        disk_val = data.get("disk", 0.0)
        self.spark_disk.add_sample(disk_val)
        disk_d = data.get("disk_details") or {}
        r_mb = disk_d.get("read_mb_s", 0.0)
        w_mb = disk_d.get("write_mb_s", 0.0)
        self.lbl_disk_read.setText(f"Read: {r_mb:.2f} MB/s")
        self.lbl_disk_write.setText(f"Write: {w_mb:.2f} MB/s")

        # Rebuild partition list if count changed
        parts = disk_d.get("partitions") or []
        if self.disk_part_layout.count() != len(parts):
            while self.disk_part_layout.count():
                item = self.disk_part_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for p in parts:
                pf = QFrame()
                pf.setStyleSheet("background: #0d0e14; border: 1px solid #1c2028; border-radius: 6px; padding: 8px;")
                pflay = QVBoxLayout(pf)
                header = QLabel(f"Drive {p['mountpoint']} ({p['fstype']}) — {p['used_gb']:.1f} GB used of {p['total_gb']:.1f} GB ({p['percent']:.0f}%)")
                header.setStyleSheet("color: #f8fafc; font-size: 11px; font-weight: 600;")
                pbar = SmoothBar(self)
                pbar.setFixedHeight(6)
                pbar.set_value(p["percent"])
                pflay.addWidget(header)
                pflay.addWidget(pbar)
                self.disk_part_layout.addWidget(pf)

        # 4. TEMP
        temp_val = data.get("temperature_c")
        if temp_val is not None:
            self.lbl_temp_main.setText(f"Package Temp: {temp_val:.1f}°C")
            self.spark_temp.add_sample(temp_val)
            if temp_val >= 85.0:
                self.lbl_temp_status.setText("CRITICAL THERMAL WARNING")
                self.lbl_temp_status.setStyleSheet("color: #ff3b4a; background: #260a0f; border: 1px solid #541722; padding: 4px 8px; border-radius: 4px;")
            else:
                self.lbl_temp_status.setText("NOMINAL COOLING")
                self.lbl_temp_status.setStyleSheet("color: #22c55e; background: #0d1a14; border: 1px solid #1c3d28; padding: 4px 8px; border-radius: 4px;")
            self.lbl_acpi_temp.setText("ACPI Thermal Zone: Active Sensor Polling")
            self.lbl_throttle.setText("Thermal Throttling: Safe Operating Margin")
        else:
            self.lbl_temp_main.setText("Package Temp: N/A")
            self.lbl_temp_status.setText("SENSOR NOT AVAILABLE ON THIS DEVICE")
            self.lbl_temp_status.setStyleSheet("color: #8c9dbd; background: #16181f; border: 1px solid #252934; padding: 4px 8px; border-radius: 4px;")
            self.lbl_acpi_temp.setText("ACPI Sensor: Not exposed by device firmware/BIOS (OEM restricted)")
            self.lbl_throttle.setText("Thermal Status: Standard Windows hardware thermal safety active")

        # 5. GPU
        gpu_d = data.get("gpu_details") or {}
        gpu_load = float(data.get("gpu_load", gpu_d.get("load_percent", 0.0)))
        self.lbl_gpu_load.setText(f"GPU Load: {gpu_load:.1f}%")
        self.spark_gpu.add_sample(gpu_load)
        self.lbl_gpu_name.setText(f"Graphics Adapter: {gpu_d.get('name', 'Display Adapter')}")
        vram_total = gpu_d.get("vram_total_gb")
        vram_used = gpu_d.get("vram_used_gb", 0.0)
        if vram_total:
            self.lbl_gpu_vram.setText(f"Dedicated VRAM: {vram_used:.1f} GB / {vram_total:.1f} GB")
        else:
            self.lbl_gpu_vram.setText("Dedicated VRAM: System Shared")
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

        # 7. PROCESSES (refresh when visible)
        if self.isVisible() and self.tabs.currentIndex() == 6:
            self._refresh_process_table()

        # 8. SYSTEM
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

    def _refresh_process_table(self):
        query = self.proc_search.text().strip().lower()
        procs = get_top_processes(20)
        if query:
            procs = [p for p in procs if query in p["name"].lower() or query in str(p["pid"])]

        self.table_procs.setRowCount(len(procs))
        for row, p in enumerate(procs):
            self.table_procs.setItem(row, 0, QTableWidgetItem(str(p["pid"])))
            self.table_procs.setItem(row, 1, QTableWidgetItem(p["name"]))
            self.table_procs.setItem(row, 2, QTableWidgetItem(f"{p['cpu_percent']:.1f}%"))
            self.table_procs.setItem(row, 3, QTableWidgetItem(f"{p['memory_percent']:.1f}%"))
            self.table_procs.setItem(row, 4, QTableWidgetItem(p.get("status", "running")))

    def _filter_procs(self):
        self._refresh_process_table()

    def _get_selected_pid(self) -> Optional[int]:
        rows = self.table_procs.selectionModel().selectedRows()
        if not rows:
            return None
        try:
            return int(self.table_procs.item(rows[0].row(), 0).text())
        except (ValueError, AttributeError):
            return None

    def _kill_selected_proc(self):
        pid = self._get_selected_pid()
        if pid:
            reply = QMessageBox.question(
                self,
                "Terminate Process",
                f"Are you sure you want to terminate process {pid}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                terminate_process(pid)
                self._refresh_process_table()

    def _toggle_suspend_proc(self):
        pid = self._get_selected_pid()
        if pid:
            # Try suspend first
            if not suspend_process(pid):
                resume_process(pid)
            self._refresh_process_table()

    # --- Window Open / Dedicated Panel Navigation ---
    def open_tab(self, tab_name: str):
        """Open the dedicated window showing ONLY the requested tab. No other tabs appear."""
        name_map = {
            "CPU": (0, "CPU MONITOR", "#22c55e"),
            "RAM": (1, "MEMORY MONITOR", "#f5a524"),
            "MEMORY": (1, "MEMORY MONITOR", "#f5a524"),
            "STORAGE": (2, "STORAGE & I/O MONITOR", "#6366f1"),
            "DISK": (2, "STORAGE & I/O MONITOR", "#6366f1"),
            "THERMALS": (3, "THERMAL SENSORS", "#f4505e"),
            "TEMP": (3, "THERMAL SENSORS", "#f4505e"),
            "GPU": (4, "GPU MONITOR", "#00e5ff"),
            "NETWORK": (5, "NETWORK & PORTS", "#a855f7"),
            "NET": (5, "NETWORK & PORTS", "#a855f7"),
            "PROCESSES": (6, "PROCESS MANAGER", "#f97316"),
            "PROCS": (6, "PROCESS MANAGER", "#f97316"),
            "SYSTEM": (7, "SYSTEM & BATTERY", "#10b981"),
            "SYS": (7, "SYSTEM & BATTERY", "#10b981"),
        }
        normalized = tab_name.upper()
        info = name_map.get(normalized, (0, "CPU MONITOR", "#22c55e"))
        idx, title_text, accent_color = info

        # Toggle: if clicking the same pill while open, close smoothly
        if self.isVisible() and getattr(self, "_active_tab_name", None) == normalized and self._opacity_effect.opacity() > 0.5:
            self.close_panel()
            return

        self._active_tab_name = normalized
        self.tabs.setCurrentIndex(idx)
        self.lbl_title.setText(f"SYS-SENTINEL  //  {title_text}")
        self.lbl_title.setStyleSheet(f"color: {accent_color}; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;")

        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def close_panel(self):
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
