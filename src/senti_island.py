"""Minimalist luxury desktop island for SYS-SENTINEL.

Designed to match the high-end Mochi aesthetic:
- Deep black and charcoal layered surfaces
- Dual-card layout with generous, refined proportions
- Card 1 (Left): Hosts SENTI in his default cute form, live status, and action links
- Card 2 (Right): 2x2 grid of metric pills with understated colored two-eyed badges (CPU, RAM, DISK, TEMP)
- Subtle top navigation capsule with Home, Greeting Chat, and HUD +
- Zero clutter, zero lag, delicate borders, and soft shadows
"""

import math
import time
from typing import Optional, Callable, Dict, Any, List
from PySide6.QtCore import (
    Qt,
    QRectF,
    QPoint,
    QPointF,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QPainterPath,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsOpacityEffect,
    QApplication,
)

DRAG_THRESHOLD = 5

# Configurable greetings list
DEFAULT_GREETINGS = [
    "Hello, Operator!",
    "SYS-SENTINEL online.",
    "All systems nominal.",
    "Ready to monitor.",
    "Hey there!",
    "Sentinel standing by.",
]


class GreetingBubbleWidget(QWidget):
    """Frameless, luxury dark glass pop-out speech bubble pointing down to SENTI."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._text: str = "Hello, Operator!"
        self.setFixedSize(190, 40)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(160)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Auto-dismiss timer (stays visible for 3.5 seconds)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.setInterval(3500)
        self._dismiss_timer.timeout.connect(self.fade_out)

    def show_greeting(self, text: str, target_pos: QPoint):
        """Position above target point and pop in smoothly without delay."""
        self._text = text
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        metric = self.fontMetrics()
        text_w = metric.horizontalAdvance(text)
        new_w = max(160, text_w + 44)
        self.setFixedSize(new_w, 40)

        gx = target_pos.x() - new_w // 2
        gy = target_pos.y() - 44
        self.move(gx, gy)

        self.show()
        self.raise_()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
        self._dismiss_timer.start()

    def fade_out(self):
        self._dismiss_timer.stop()
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

    def mousePressEvent(self, event):
        self.fade_out()
        event.accept()

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()
            bubble_h = h - 6.0

            path = QPainterPath()
            path.addRoundedRect(QRectF(1.0, 1.0, w - 2.0, bubble_h - 2.0), 9.0, 9.0)
            cx = w / 2.0
            path.moveTo(cx - 5.0, bubble_h - 1.0)
            path.lineTo(cx, h - 1.0)
            path.lineTo(cx + 5.0, bubble_h - 1.0)

            # 100% Solid Opaque Dark Matte Bubble (No glass)
            p.setBrush(QColor("#0d0e14"))
            p.setPen(QPen(QColor("#1f2430"), 1.2))
            p.drawPath(path)

            p.setFont(QFont("Segoe UI Emoji", 9))
            p.setPen(QColor("#00e5ff"))
            p.drawText(10, int(bubble_h * 0.68), "✦")

            p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            p.setPen(QColor("#f8fafc"))
            p.drawText(QRectF(26, 0, w - 32, bubble_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
        finally:
            p.end()


class TopIslandWindow(QWidget):
    """Minimalist solid opaque desktop island matching Mochi reference exactly."""

    def __init__(
        self,
        on_drag_moved: Optional[Callable[[QPoint], None]] = None,
        on_toggle_hud: Optional[Callable[[], None]] = None,
        on_trigger_greeting: Optional[Callable[[], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
        on_toggle_sound: Optional[Callable[[], None]] = None,
        is_sound_enabled_getter: Optional[Callable[[], bool]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_drag_moved = on_drag_moved
        self.on_toggle_hud = on_toggle_hud
        self.on_trigger_greeting = on_trigger_greeting
        self.on_refresh = on_refresh
        self.on_toggle_sound = on_toggle_sound
        self.is_sound_enabled_getter = is_sound_enabled_getter

        # Windows Tool window attributes: Frameless, Always on Top, Never steals keyboard focus
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Minimalist 640 x 136 layout (clean dual-card design without top header bar)
        self.setFixedSize(640, 136)

        # Telemetry data
        self._telemetry: Dict[str, Any] = {
            "cpu": 0.0,
            "ram": 0.0,
            "disk": 0.0,
            "temperature_c": None,
            "system_drive": "C:",
        }

        # Dragging state
        self._is_dragging = False
        self._press_pos = QPoint()
        self._window_start_pos = QPoint()

        # Hover state
        self._hover_target: Optional[str] = None
        self.setMouseTracking(True)

        # Pill entrance animations (scale, opacity) - hidden initially until Senti docks
        self._pill_scales = [0.0, 0.0, 0.0, 0.0]
        self._pill_alphas = [0.0, 0.0, 0.0, 0.0]
        self._pill_timers: List[QTimer] = []

        # Opacity animation for hide/show
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(160)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def animate_pills_entrance(self, on_pill_pop: Optional[Callable[[], None]] = None):
        """Smooth staggered spring entrance for the 4 metric pills."""
        self._pill_scales = [0.0, 0.0, 0.0, 0.0]
        self._pill_alphas = [0.0, 0.0, 0.0, 0.0]
        self.update()

        for timer in list(self._pill_timers):
            timer.stop()
        self._pill_timers.clear()

        # Staggered pop-in for each pill (70ms apart)
        for i in range(4):
            delay_ms = i * 70
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(delay_ms)

            def _start_pill(pill_idx=i):
                if on_pill_pop:
                    on_pill_pop()
                self._animate_single_pill(pill_idx)

            t.timeout.connect(_start_pill)
            self._pill_timers.append(t)
            t.start()

    def _animate_single_pill(self, idx: int):
        anim_timer = QTimer(self)
        anim_timer.setInterval(16)
        start_time = time.time()
        duration = 0.22

        def _step():
            elapsed = time.time() - start_time
            progress = min(1.0, elapsed / duration)
            # Spring overshoot curve
            s = 1.0 + math.sin(progress * math.pi) * 0.12 * (1.0 - progress)
            self._pill_scales[idx] = s if progress < 1.0 else 1.0
            self._pill_alphas[idx] = min(1.0, progress * 1.5)
            self.update()
            if progress >= 1.0:
                anim_timer.stop()
                try:
                    self._pill_timers.remove(anim_timer)
                except ValueError:
                    pass

        anim_timer.timeout.connect(_step)
        self._pill_timers.append(anim_timer)
        anim_timer.start()

    def get_dock_target_pos(self, senti_size: int = 80) -> QPoint:
        """Calculate screen position where SENTI nests inside Card 1 (cx: 171, cy: 68)."""
        dock_x = self.x() + 171 - senti_size // 2
        dock_y = self.y() + 68 - senti_size // 2
        return QPoint(dock_x, dock_y)

    def update_telemetry(self, data: Dict[str, Any]):
        """Update live telemetry metrics displayed on the pills."""
        if not data:
            return
        self._telemetry["cpu"] = data.get("cpu", 0.0)
        self._telemetry["ram"] = data.get("ram", 0.0)
        self._telemetry["disk"] = data.get("disk", 0.0)
        self._telemetry["temperature_c"] = data.get("temperature_c")
        self._telemetry["system_drive"] = data.get("system_drive", "C:")
        self.update()

    # --- Mouse & Interaction ---

    def _hit_test(self, pos: QPoint) -> Optional[str]:
        px, py = pos.x(), pos.y()

        # Card 2 pills area (y: 10..126, x: 342..630) -> Click opens HUD
        if 10 <= py <= 126 and 342 <= px <= 630:
            return "hud"

        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._window_start_pos = self.pos()
            self._is_dragging = False

            hit = self._hit_test(event.pos())
            if hit in ("home", "plus", "hud"):
                if self.on_toggle_hud:
                    self.on_toggle_hud()
            elif hit == "chat":
                if self.on_trigger_greeting:
                    self.on_trigger_greeting()
            elif hit == "sound":
                if self.on_toggle_sound:
                    self.on_toggle_sound()
                self.update()
            elif hit == "refresh":
                if self.on_refresh:
                    self.on_refresh()

            event.accept()

    def mouseMoveEvent(self, event):
        hit = self._hit_test(event.pos())
        if hit != self._hover_target:
            self._hover_target = hit
            self.update()

        # Drag entire island
        if event.buttons() & Qt.MouseButton.LeftButton:
            curr_pos = event.globalPosition().toPoint()
            delta = curr_pos - self._press_pos
            if not self._is_dragging and delta.manhattanLength() > DRAG_THRESHOLD:
                self._is_dragging = True

            if self._is_dragging:
                new_pos = self._window_start_pos + delta
                self.move(new_pos)
                if self.on_drag_moved:
                    self.on_drag_moved(new_pos)
                event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()

    def leaveEvent(self, event):
        del event
        self._hover_target = None
        self.update()

    # --- Fade In / Out ---

    def fade_in(self):
        self.show()
        self.raise_()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_out(self):
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

    # --- Pure Opaque Minimalist Painting ---

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            self.render_to_painter(p)
        finally:
            p.end()

    def render_to_painter(self, p: QPainter):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # 1. ENTIRE OUTER ISLAND CONTAINER (100% solid opaque dark matte, no glass)
        island_rect = QRectF(1.0, 1.0, w - 2.0, h - 2.0)
        p.setPen(QPen(QColor("#20242c"), 1.2))
        p.setBrush(QColor("#090a0d"))
        p.drawRoundedRect(island_rect, 22.0, 22.0)

        # 2. Left Card (100% solid opaque dark carbon matte)
        self._paint_card_1(p)

        # 3. Right Card (100% solid opaque dark carbon matte)
        self._paint_card_2(p)

    def _paint_card_1(self, p: QPainter):
        """Paint Card 1 (Left: 322x116, radius 20, solid dark matte #111317)."""
        c1_rect = QRectF(10.0, 10.0, 322.0, 116.0)
        p.setPen(QPen(QColor("#1c2028"), 1.0))
        p.setBrush(QColor("#111317"))
        p.drawRoundedRect(c1_rect, 20.0, 20.0)

    def _paint_card_2(self, p: QPainter):
        """Paint Card 2 (Right: 288x116, radius 20, solid dark matte #111317)."""
        c2_rect = QRectF(342.0, 10.0, 288.0, 116.0)
        p.setPen(QPen(QColor("#1c2028"), 1.0))
        p.setBrush(QColor("#111317"))
        p.drawRoundedRect(c2_rect, 20.0, 20.0)

        # Telemetry values
        cpu_val = self._telemetry.get("cpu", 0.0)
        ram_val = self._telemetry.get("ram", 0.0)
        disk_val = self._telemetry.get("disk", 0.0)
        temp_val = self._telemetry.get("temperature_c")
        sys_drive = self._telemetry.get("system_drive", "C:")
        if sys_drive.endswith("\\"):
            sys_drive = sys_drive[:-1]

        temp_str = f"{temp_val:.0f}°C" if temp_val is not None else "N/A"

        col1_x = 350.0
        col2_x = 488.0
        row1_y = 34.0
        row2_y = 74.0
        pw = 134.0
        ph = 28.0

        # Pill 1: CPU (Emerald #22c55e)
        self._paint_pill(p, col1_x, row1_y, pw, ph, QColor("#22c55e"), "CPU", f"{cpu_val:.0f}%", self._pill_scales[0], self._pill_alphas[0])
        # Pill 2: RAM (Amber #f5a524)
        self._paint_pill(p, col2_x, row1_y, pw, ph, QColor("#f5a524"), "RAM", f"{ram_val:.0f}%", self._pill_scales[1], self._pill_alphas[1])
        # Pill 3: DISK (Indigo #6366f1)
        self._paint_pill(p, col1_x, row2_y, pw, ph, QColor("#6366f1"), f"{sys_drive} DISK", f"{disk_val:.0f}%", self._pill_scales[2], self._pill_alphas[2])
        # Pill 4: TEMP (Red/Rose #f4505e)
        self._paint_pill(p, col2_x, row2_y, pw, ph, QColor("#f4505e"), "TEMP", temp_str, self._pill_scales[3], self._pill_alphas[3])

    def _paint_pill(
        self,
        p: QPainter,
        px: float,
        py: float,
        pw: float,
        ph: float,
        badge_color: QColor,
        label: str,
        val_str: str,
        scale: float = 1.0,
        alpha: float = 1.0,
    ):
        """Paint a single pill (solid dark opaque #16181f, crisp border #252934)."""
        if scale < 0.01 or alpha < 0.01:
            return

        p.save()
        if scale < 0.999 or scale > 1.001 or alpha < 0.999:
            pcx = px + pw / 2.0
            pcy = py + ph / 2.0
            p.translate(pcx, pcy)
            p.scale(scale, scale)
            p.translate(-pcx, -pcy)
            p.setOpacity(alpha)

        rect = QRectF(px, py, pw, ph)
        p.setPen(QPen(QColor("#252934"), 1.0))
        p.setBrush(QColor("#16181f"))
        p.drawRoundedRect(rect, 14.0, 14.0)

        # Mini badge (.mini: 22x19, radius 6px)
        bx, by, bw, bh = px + 6.0, py + 4.5, 22.0, 19.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(badge_color)
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 6.0, 6.0)

        # Two little black dot eyes
        p.setBrush(QColor("#000000"))
        p.drawEllipse(QPointF(bx + 7.0, by + 9.5), 1.8, 2.3)
        p.drawEllipse(QPointF(bx + 15.0, by + 9.5), 1.8, 2.3)

        # Label (.lbl)
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.setPen(QColor("#6b7079"))
        p.drawText(
            QRectF(bx + bw + 8, py, 44, ph),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        # Value
        p.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        p.setPen(QColor("#f5f6f8"))
        p.drawText(
            QRectF(px, py, pw - 10, ph),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            val_str,
        )
        p.restore()


def get_default_island_pos(island_w: int, island_h: int) -> QPoint:
    """Calculate exact center-top position on the primary desktop screen."""
    del island_h
    primary = QApplication.primaryScreen()
    if not primary:
        return QPoint(600, 10)
    geo = primary.availableGeometry()
    x = geo.x() + (geo.width() - island_w) // 2
    y = geo.y() + 8
    return QPoint(x, y)
