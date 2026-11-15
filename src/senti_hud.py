"""Compact HUD panel for SYS-SENTINEL.

Frameless, transparent, stays on top, never steals keyboard focus,
and displays live system hardware telemetry.
"""

from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import (
    Qt,
    QRect,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QGuiApplication,
    QScreen,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGraphicsOpacityEffect,
)

from senti_state import (
    CPU_THRESHOLDS,
    RAM_THRESHOLDS,
    DISK_THRESHOLDS,
    TEMP_THRESHOLDS,
    STATUS_NORMAL,
    STATUS_WARNING,
    STATUS_CRITICAL,
    STATUS_UNAVAILABLE,
    STATUS_CHECKING,
    get_metric_status,
    format_uptime,
    format_gb,
    format_percent,
    format_temp,
)
from senti_widgets import (
    DARK_THEME_QSS,
    SmoothBar,
)


class MetricCard(QFrame):
    """Small card with metric title, live value, smooth progress bar, and status pill."""

    def __init__(self, title: str, warn: float, crit: float, unit: str = "%", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.warn = warn
        self.crit = crit
        self.unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Top row: Title + Status Tag
        top_row = QHBoxLayout()
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 600; text-transform: uppercase;")
        top_row.addWidget(self.title_lbl)

        top_row.addStretch()

        self.status_lbl = QLabel(STATUS_CHECKING)
        self.status_lbl.setStyleSheet("color: #687894; font-size: 10px; font-weight: 700; padding: 1px 4px; border-radius: 3px;")
        top_row.addWidget(self.status_lbl)
        layout.addLayout(top_row)

        # Middle row: Large value label
        self.val_lbl = QLabel("—")
        self.val_lbl.setStyleSheet("color: #eef4fc; font-size: 18px; font-weight: 700;")
        layout.addWidget(self.val_lbl)

        # Bottom row: Smooth Progress Bar
        self.bar = SmoothBar(self)
        layout.addWidget(self.bar)

    def update_reading(self, value: Optional[float], custom_text: Optional[str] = None):
        if value is None:
            status = STATUS_UNAVAILABLE
            self.val_lbl.setText("Unavailable")
            self.val_lbl.setStyleSheet("color: #687894; font-size: 14px; font-weight: 600;")
        else:
            status = get_metric_status(value, self.warn, self.crit)
            if custom_text:
                self.val_lbl.setText(custom_text)
            else:
                self.val_lbl.setText(f"{value:.0f}{self.unit}")
            self.val_lbl.setStyleSheet("color: #eef4fc; font-size: 18px; font-weight: 700;")

        # Style status tag
        if status == STATUS_CRITICAL:
            tag_style = "color: #ff3b4a; background: #3d141b; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px;"
        elif status == STATUS_WARNING:
            tag_style = "color: #ffb020; background: #3d2c12; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px;"
        elif status == STATUS_NORMAL:
            tag_style = "color: #00e5ff; background: #0c2b3d; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px;"
        else:
            tag_style = "color: #687894; background: #172033; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px;"

        self.status_lbl.setText(status)
        self.status_lbl.setStyleSheet(tag_style)

        # Update smooth bar
        self.bar.set_value(value, status)


class SentiHud(QWidget):
    """Frameless, floating HUD window providing live system telemetry."""

    def __init__(self, on_open_control: Optional[Callable[[], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.on_open_control = on_open_control

        # Windows flags: Tool, Frameless, StaysOnTop, WindowDoesNotAcceptFocus
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setObjectName("hudRoot")
        self.setStyleSheet(DARK_THEME_QSS)
        self.setFixedSize(360, 480)

        # Opacity animation for smooth fade
        self._is_open: bool = False
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._init_ui()

    def is_open(self) -> bool:
        return self._is_open

    def paintEvent(self, event):
        del event
        from PySide6.QtGui import QPainter, QColor, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#0b1020"))
        p.setPen(QPen(QColor("#1f2f4d"), 1.2))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        p.end()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        # 1. Header (Title + Close [X])
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        app_title = QLabel("SYS-SENTINEL")
        app_title.setStyleSheet("color: #00e5ff; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
        sub_title = QLabel("LIVE TELEMETRY HUD")
        sub_title.setStyleSheet("color: #687894; font-size: 9px; font-weight: 600;")
        title_box.addWidget(app_title)
        title_box.addWidget(sub_title)
        header.addLayout(title_box)

        header.addStretch()

        self.close_btn = QPushButton("×")
        self.close_btn.setProperty("class", "closeButton")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_hud)
        header.addWidget(self.close_btn)
        root_layout.addLayout(header)

        # 2. Metric Cards Grid (CPU, RAM, System Drive, Temp)
        grid = QGridLayout()
        grid.setSpacing(8)

        self.card_cpu = MetricCard("CPU", CPU_THRESHOLDS[0], CPU_THRESHOLDS[1], "%", self)
        self.card_ram = MetricCard("Memory", RAM_THRESHOLDS[0], RAM_THRESHOLDS[1], "%", self)
        self.card_disk = MetricCard("System Drive", DISK_THRESHOLDS[0], DISK_THRESHOLDS[1], "%", self)
        self.card_temp = MetricCard("Temperature", TEMP_THRESHOLDS[0], TEMP_THRESHOLDS[1], " °C", self)

        grid.addWidget(self.card_cpu, 0, 0)
        grid.addWidget(self.card_ram, 0, 1)
        grid.addWidget(self.card_disk, 1, 0)
        grid.addWidget(self.card_temp, 1, 1)
        root_layout.addLayout(grid)

        # 3. Hardware Details Card
        details_frame = QFrame()
        details_frame.setProperty("class", "card")
        det_layout = QGridLayout(details_frame)
        det_layout.setContentsMargins(10, 8, 10, 8)
        det_layout.setVerticalSpacing(4)
        det_layout.setHorizontalSpacing(10)

        def add_detail_row(row: int, label: str):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #687894; font-size: 10px; font-weight: 600;")
            val = QLabel("—")
            val.setStyleSheet("color: #cdd9ed; font-size: 10px; font-weight: 500;")
            val.setWordWrap(False)
            det_layout.addWidget(lbl, row, 0)
            det_layout.addWidget(val, row, 1)
            return val

        self.lbl_cpu_name = add_detail_row(0, "PROCESSOR")
        self.lbl_cores = add_detail_row(1, "CORES")
        self.lbl_os = add_detail_row(2, "OS")
        self.lbl_host = add_detail_row(3, "COMPUTER")
        self.lbl_ram_detail = add_detail_row(4, "RAM USAGE")
        self.lbl_disk_detail = add_detail_row(5, "STORAGE")
        self.lbl_battery = add_detail_row(6, "BATTERY")
        self.lbl_uptime = add_detail_row(7, "UPTIME")

        root_layout.addWidget(details_frame)

        # 4. Footer Button (Close)
        self.control_btn = QPushButton("Close")
        self.control_btn.setProperty("class", "actionButton")
        self.control_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_btn.clicked.connect(self.close_hud)
        root_layout.addWidget(self.control_btn)

    def update_data(self, data: Dict[str, Any]):
        """Refresh all telemetry values from snapshot data."""
        if not data:
            return

        # CPU
        self.card_cpu.update_reading(data.get("cpu"))

        # RAM
        self.card_ram.update_reading(data.get("ram"))

        # Disk (with dynamic system drive letter)
        drive_name = data.get("system_drive", "C:")
        if drive_name.endswith("\\"):
            drive_name = drive_name[:-1]
        self.card_disk.title_lbl.setText(f"{drive_name} DRIVE")
        self.card_disk.update_reading(data.get("disk"))

        # Temperature
        self.card_temp.update_reading(data.get("temperature_c"))

        # Hardware detail labels
        self.lbl_cpu_name.setText(data.get("processor", "Unknown"))
        self.lbl_cores.setText(f"{data.get('logical_cores', 0)} Logical Threads")
        self.lbl_os.setText(data.get("os", "Windows"))
        self.lbl_host.setText(data.get("hostname", "Unknown"))

        # RAM details
        used_ram = data.get("ram_used_gb")
        total_ram = data.get("ram_total_gb")
        if used_ram is not None and total_ram is not None:
            self.lbl_ram_detail.setText(f"{used_ram:.1f} / {total_ram:.1f} GB")
        else:
            self.lbl_ram_detail.setText("Unavailable")

        # Storage details
        used_disk = data.get("disk_used_gb")
        free_disk = data.get("disk_free_gb")
        total_disk = data.get("disk_total_gb")
        if used_disk is not None and free_disk is not None and total_disk is not None:
            self.lbl_disk_detail.setText(f"{used_disk:.1f} GB used ({free_disk:.1f} GB free)")
        else:
            self.lbl_disk_detail.setText("Unavailable")

        # Battery details
        bat = data.get("battery")
        plugged = data.get("battery_plugged")
        if bat is not None:
            state_str = " (Plugged in)" if plugged else " (On Battery)"
            self.lbl_battery.setText(f"{bat:.0f}%{state_str}")
        else:
            self.lbl_battery.setText("Unavailable (No battery)")

        # Uptime
        uptime_sec = data.get("uptime_seconds", 0)
        self.lbl_uptime.setText(format_uptime(uptime_sec))

    def reposition_beside(self, companion_rect: QRect):
        """Align HUD beside SENTI, flipping left/right to stay on-screen."""
        screen = QGuiApplication.screenAt(companion_rect.center())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        hud_w = self.width()
        hud_h = self.height()

        margin = 12

        # Try placing to the right
        x = companion_rect.right() + margin
        if x + hud_w > screen_geo.right() - 4:
            # Flip to the left
            x = companion_rect.left() - hud_w - margin

        # Align Y center with companion
        y = int(companion_rect.center().y() - hud_h / 2)
        # Clamp to screen borders
        y = max(screen_geo.top() + 6, min(screen_geo.bottom() - hud_h - 6, y))
        x = max(screen_geo.left() + 6, min(screen_geo.right() - hud_w - 6, x))

        self.move(x, y)

    def open_hud(self, companion_rect: QRect):
        """Fade and slide open beside SENTI."""
        self._is_open = True
        self.reposition_beside(companion_rect)
        self.show()
        self.raise_()

        self._anim.stop()
        self._anim.setStartValue(self._opacity_effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def close_hud(self):
        """Fade out and hide."""
        self._is_open = False
        self._anim.stop()
        self._anim.setStartValue(self._opacity_effect.opacity())
        self._anim.setEndValue(0.0)

        def _on_done():
            if not self._is_open:
                self.hide()
            try:
                self._anim.finished.disconnect(_on_done)
            except Exception:
                pass

        self._anim.finished.connect(_on_done)
        self._anim.start()
