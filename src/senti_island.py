"""Minimalist luxury desktop island for Sentinel.

Designed to match the high-end Mochi aesthetic:
- Deep black and charcoal layered surfaces
- Dual-card layout with generous, refined proportions
- Card 1 (Left): Hosts SENTI in his default cute form, live status, and action links
- Card 2 (Right): 4x2 grid of 8 metric pills with understated colored two-eyed badges (CPU, RAM, GPU, NET, DISK, TEMP, BAT/SYS, SET)
- Subtle top navigation capsule with Home, Greeting Chat, and HUD +
- Zero clutter, zero lag, delicate borders, and soft shadows
"""

import math
import time
from typing import Optional, Callable, Dict, Any, List
from PySide6.QtCore import (
    Qt,
    QRect,
    QRectF,
    QPoint,
    QPointF,
    QTimer,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QPainterPath,
    QLinearGradient,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsOpacityEffect,
    QApplication,
)

DRAG_THRESHOLD = 5


PILL_HIT_INDEX = {
    "pill_cpu": 0,
    "pill_ram": 1,
    "pill_gpu": 2,
    "pill_net": 3,
    "pill_disk": 4,
    "pill_temp": 5,
    "pill_sys": 6,
    "pill_set": 7,
}

TAB_CANONICAL: Dict[str, str] = {
    "CPU": "CPU",
    "RAM": "RAM",
    "MEMORY": "RAM",
    "GPU": "GPU",
    "NET": "NETWORK",
    "NETWORK": "NETWORK",
    "DISK": "STORAGE",
    "STORAGE": "STORAGE",
    "TEMP": "THERMALS",
    "THERMALS": "THERMALS",
    "TEMPERATURE": "THERMALS",
    "SYS": "SYSTEM",
    "BAT": "SYSTEM",
    "BATTERY": "SYSTEM",
    "SYSTEM": "SYSTEM",
    "SET": "SETTINGS",
    "SETTINGS": "SETTINGS",
    "PREF": "SETTINGS",
    "CONFIG": "SETTINGS",
}



class TopIslandWindow(QWidget):
    """Minimalist solid opaque desktop island matching Mochi reference exactly."""

    def __init__(
        self,
        on_drag_moved: Optional[Callable[[QPoint], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
        on_toggle_sound: Optional[Callable[[], None]] = None,
        is_sound_enabled_getter: Optional[Callable[[], bool]] = None,
        on_open_tab: Optional[Callable[[str], None]] = None,
        on_pill_hover: Optional[Callable[[Optional[str]], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_drag_moved = on_drag_moved
        self.on_refresh = on_refresh
        self.on_toggle_sound = on_toggle_sound
        self.is_sound_enabled_getter = is_sound_enabled_getter
        self.on_open_tab = on_open_tab
        self.on_pill_hover = on_pill_hover

        # Windows Tool window attributes: Frameless, Always on Top, Never steals keyboard focus
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Senti")
        # Ensure native platform window handle is instantiated
        self.winId()

        # Minimalist 706 x 136 layout (clean dual-card design with 8 subsystem pills)
        self.setFixedSize(706, 136)

        # Telemetry data
        self._telemetry: Dict[str, Any] = {
            "cpu": 0.0,
            "ram": 0.0,
            "disk": 0.0,
            "temperature_c": None,
            "system_drive": "C:",
            "gpu_load": 0.0,
            "net_recv_kb_s": 0.0,
            "ping_ms": None,
            "battery": None,
            "uptime_seconds": 0,
        }

        # Dragging state
        self._is_dragging = False
        self._press_pos = QPoint()
        self._window_start_pos = QPoint()

        # Hover state
        self._hover_target: Optional[str] = None
        self.setMouseTracking(True)

        # Active tab tracking (controls active pill green dot)
        self._active_tab: Optional[str] = None

        # Smooth per-pill hover weights (0.0 = idle, 1.0 = fully hovered)
        self._hover_progress: List[float] = [0.0] * 8
        self._hover_anim_timer: Optional[QTimer] = None

        # Pill entrance animations (scale, opacity) for all 8 pills (default hidden before entrance)
        self._pill_scales = [0.0] * 8
        self._pill_alphas = [0.0] * 8
        self._pill_timers: List[QTimer] = []

        # Opacity animation for hide/show
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(70)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._entrance_group: Optional[QParallelAnimationGroup] = None

    def animate_pills_entrance(self, on_pill_pop: Optional[Callable[[], None]] = None):
        """Smooth staggered spring entrance for all 8 subsystem metric pills."""
        self._pill_scales = [0.0] * 8
        self._pill_alphas = [0.0] * 8
        self.update()

        for timer in list(self._pill_timers):
            timer.stop()
        self._pill_timers.clear()

        # Fast, responsive staggered pop-in for all 8 pills (12ms apart)
        for i in range(8):
            delay_ms = i * 12
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(delay_ms)

            def _start_pill(pill_idx=i):
                if on_pill_pop:
                    try:
                        on_pill_pop(pill_idx)
                    except TypeError:
                        on_pill_pop()
                self._animate_single_pill(pill_idx)

            t.timeout.connect(_start_pill)
            self._pill_timers.append(t)
            t.start()

    def _animate_single_pill(self, idx: int):
        anim_timer = QTimer(self)
        anim_timer.setInterval(16)
        start_time = time.time()
        duration = 0.12

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
        """Calculate screen position where SENTI nests inside Card 1 (cx: 78, cy: 68)."""
        dock_x = self.x() + 78 - senti_size // 2
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
        self._telemetry["gpu_load"] = data.get("gpu_load", 0.0)
        self._telemetry["net_recv_kb_s"] = data.get("net_recv_kb_s", 0.0)
        self._telemetry["ping_ms"] = data.get("ping_ms")
        self._telemetry["battery"] = data.get("battery")
        self._telemetry["uptime_seconds"] = data.get("uptime_seconds", 0)
        if self.isVisible():
            self.update()

    # --- Mouse & Interaction ---

    def _hit_test(self, pos: QPoint) -> Optional[str]:
        px, py = pos.x(), pos.y()

        # Right Card: 8 subsystem pills in 4x2 matrix (px: 156..696, py: 10..126)
        if 156 <= px <= 696 and 10 <= py <= 126:
            # Row determination
            if py < 65:
                # Row 1: CPU, RAM, GPU, NET
                if px < 294:
                    return "pill_cpu"
                elif px < 426:
                    return "pill_ram"
                elif px < 558:
                    return "pill_gpu"
                else:
                    return "pill_net"
            else:
                # Row 2: DISK, TEMP, SYS, SET
                if px < 294:
                    return "pill_disk"
                elif px < 426:
                    return "pill_temp"
                elif px < 558:
                    return "pill_sys"
                else:
                    return "pill_set"

        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._window_start_pos = self.pos()
            self._is_dragging = False

            hit = self._hit_test(event.pos())
            if hit == "pill_cpu":
                if self.on_open_tab:
                    self.on_open_tab("CPU")
            elif hit == "pill_ram":
                if self.on_open_tab:
                    self.on_open_tab("RAM")
            elif hit == "pill_gpu":
                if self.on_open_tab:
                    self.on_open_tab("GPU")
            elif hit == "pill_net":
                if self.on_open_tab:
                    self.on_open_tab("NETWORK")
            elif hit == "pill_disk":
                if self.on_open_tab:
                    self.on_open_tab("STORAGE")
            elif hit == "pill_temp":
                if self.on_open_tab:
                    self.on_open_tab("THERMALS")
            elif hit == "pill_sys":
                if self.on_open_tab:
                    self.on_open_tab("SYSTEM")
            elif hit == "pill_set":
                if self.on_open_tab:
                    self.on_open_tab("SETTINGS")
            elif hit == "sound":
                if self.on_toggle_sound:
                    self.on_toggle_sound()
                self.update()
            elif hit == "refresh":
                if self.on_refresh:
                    self.on_refresh()

            event.accept()

    def _start_hover_animation(self):
        if not self._hover_anim_timer:
            self._hover_anim_timer = QTimer(self)
            self._hover_anim_timer.setInterval(16)
            self._hover_anim_timer.timeout.connect(self._step_hover_anim)
        if not self._hover_anim_timer.isActive():
            self._hover_anim_timer.start()

    def _step_hover_anim(self):
        active_idx = PILL_HIT_INDEX.get(self._hover_target) if self._hover_target else None
        changed = False

        for i in range(8):
            target = 1.0 if (active_idx == i) else 0.0
            diff = target - self._hover_progress[i]
            if abs(diff) > 0.005:
                self._hover_progress[i] += diff * 0.48
                changed = True
            else:
                self._hover_progress[i] = target

        if changed:
            self.update()
        elif self._hover_anim_timer:
            self._hover_anim_timer.stop()

    def mouseMoveEvent(self, event):
        hit = self._hit_test(event.pos())
        if hit != self._hover_target:
            self._hover_target = hit
            if hit and hit.startswith("pill_"):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            elif hit in ("sound", "refresh"):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()

            self._start_hover_animation()
            if self.on_pill_hover:
                self.on_pill_hover(hit)

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
        if self._hover_target is not None:
            self._hover_target = None
            self.unsetCursor()
            self._start_hover_animation()
            if self.on_pill_hover:
                self.on_pill_hover(None)

    # --- Fade In / Out & Dynamic Entrances ---

    def slide_and_fade_in(
        self,
        target_pos: QPoint,
        duration: int = 280,
        on_finished: Optional[Callable[[], None]] = None,
    ):
        """Minimalist, dynamic entrance: slides down slightly from top and fades in with low latency."""
        self.show()
        self.raise_()
        self._fade_anim.stop()

        start_pos = QPoint(target_pos.x(), max(0, target_pos.y() - 18))
        self.move(start_pos)

        if self._entrance_group and self._entrance_group.state() == QPropertyAnimation.State.Running:
            self._entrance_group.stop()

        self._entrance_group = QParallelAnimationGroup(self)

        start_geo = QRect(start_pos.x(), start_pos.y(), self.width(), self.height())
        target_geo = QRect(target_pos.x(), target_pos.y(), self.width(), self.height())

        geom_anim = QPropertyAnimation(self, b"geometry", self)
        geom_anim.setDuration(duration)
        geom_anim.setStartValue(start_geo)
        geom_anim.setEndValue(target_geo)
        geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        op_anim.setDuration(duration)
        op_anim.setStartValue(self._opacity_effect.opacity())
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._entrance_group.addAnimation(geom_anim)
        self._entrance_group.addAnimation(op_anim)

        if on_finished:
            self._entrance_group.finished.connect(on_finished)

        self._entrance_group.start()

    def set_active_tab(self, tab_name: Optional[str]):
        """Set the currently active subsystem tab and update the green indicator dot."""
        canonical = TAB_CANONICAL.get(tab_name.upper(), tab_name.upper()) if tab_name else None
        if self._active_tab != canonical:
            self._active_tab = canonical
            self.update()

    def get_active_tab(self) -> Optional[str]:
        """Return the canonical name of the currently active subsystem tab, if any."""
        return self._active_tab

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
        """Paint Card 1 (Left: 136x116, radius 20, solid dark matte #111317)."""
        c1_rect = QRectF(10.0, 10.0, 136.0, 116.0)
        p.setPen(QPen(QColor("#1c2028"), 1.0))
        p.setBrush(QColor("#111317"))
        p.drawRoundedRect(c1_rect, 20.0, 20.0)

    def _paint_card_2(self, p: QPainter):
        """Paint Card 2 (Right: 540x116, radius 20, solid dark matte #111317, 8 pills in 4x2 grid)."""
        c2_rect = QRectF(156.0, 10.0, 540.0, 116.0)
        p.setPen(QPen(QColor("#1c2028"), 1.0))
        p.setBrush(QColor("#111317"))
        p.drawRoundedRect(c2_rect, 20.0, 20.0)

        # 1. Telemetry values
        cpu_val = self._telemetry.get("cpu", 0.0)
        ram_val = self._telemetry.get("ram", 0.0)
        gpu_val = self._telemetry.get("gpu_load", 0.0)
        recv_kb = self._telemetry.get("net_recv_kb_s", 0.0)
        ping = self._telemetry.get("ping_ms")
        disk_val = self._telemetry.get("disk", 0.0)
        temp_val = self._telemetry.get("temperature_c")
        bat_val = self._telemetry.get("battery")
        sys_drive = self._telemetry.get("system_drive", "C:")
        if sys_drive.endswith("\\"):
            sys_drive = sys_drive[:-1]

        # Formatters
        if recv_kb >= 1.0:
            net_str = f"{recv_kb:.0f}K/s" if recv_kb < 1024 else f"{(recv_kb/1024):.1f}M"
        elif ping is not None:
            net_str = f"{ping:.0f}ms"
        else:
            net_str = "0 K/s"

        temp_str = f"{temp_val:.0f}°C" if temp_val is not None else "N/A"

        if bat_val is not None:
            bat_label = "BAT"
            bat_str = f"{bat_val:.0f}%"
        else:
            bat_label = "SYS"
            uptime_s = self._telemetry.get("uptime_seconds", 0)
            hours = uptime_s / 3600.0
            bat_str = f"{hours:.1f}h" if hours < 24 else f"{(hours/24):.1f}d"

        # 4x2 matrix layout (124px width, 8px gap -> 166..686)
        col1_x = 166.0
        col2_x = 298.0
        col3_x = 430.0
        col4_x = 562.0
        row1_y = 28.0
        row2_y = 70.0
        pw = 124.0
        ph = 30.0

        dim_amount = max(self._hover_progress)

        # Row 1
        # Pill 1: CPU (Emerald #22c55e)
        self._paint_pill(p, col1_x, row1_y, pw, ph, QColor("#22c55e"), "CPU", f"{cpu_val:.0f}%",
                         self._pill_scales[0], self._pill_alphas[0], self._hover_progress[0], dim_amount if self._hover_progress[0] < 0.5 else 0.0,
                         is_active=(self._active_tab == "CPU"))
        # Pill 2: RAM (Amber #f5a524)
        self._paint_pill(p, col2_x, row1_y, pw, ph, QColor("#f5a524"), "RAM", f"{ram_val:.0f}%",
                         self._pill_scales[1], self._pill_alphas[1], self._hover_progress[1], dim_amount if self._hover_progress[1] < 0.5 else 0.0,
                         is_active=(self._active_tab == "RAM"))
        # Pill 3: GPU (Cyan #00e5ff)
        self._paint_pill(p, col3_x, row1_y, pw, ph, QColor("#00e5ff"), "GPU", f"{gpu_val:.0f}%",
                         self._pill_scales[2], self._pill_alphas[2], self._hover_progress[2], dim_amount if self._hover_progress[2] < 0.5 else 0.0,
                         is_active=(self._active_tab == "GPU"))
        # Pill 4: NET (Violet #a855f7)
        self._paint_pill(p, col4_x, row1_y, pw, ph, QColor("#a855f7"), "NET", net_str,
                         self._pill_scales[3], self._pill_alphas[3], self._hover_progress[3], dim_amount if self._hover_progress[3] < 0.5 else 0.0,
                         is_active=(self._active_tab == "NETWORK"))

        # Row 2
        # Pill 5: DISK (Indigo #6366f1)
        self._paint_pill(p, col1_x, row2_y, pw, ph, QColor("#6366f1"), "DISK", f"{disk_val:.0f}%",
                         self._pill_scales[4], self._pill_alphas[4], self._hover_progress[4], dim_amount if self._hover_progress[4] < 0.5 else 0.0,
                         is_active=(self._active_tab == "STORAGE"))
        # Pill 6: TEMP (Red/Rose #f4505e)
        self._paint_pill(p, col2_x, row2_y, pw, ph, QColor("#f4505e"), "TEMP", temp_str,
                         self._pill_scales[5], self._pill_alphas[5], self._hover_progress[5], dim_amount if self._hover_progress[5] < 0.5 else 0.0,
                         is_active=(self._active_tab == "THERMALS"))
        # Pill 7: BAT / SYS (Lime #10b981)
        self._paint_pill(p, col3_x, row2_y, pw, ph, QColor("#10b981"), bat_label, bat_str,
                         self._pill_scales[6], self._pill_alphas[6], self._hover_progress[6], dim_amount if self._hover_progress[6] < 0.5 else 0.0,
                         is_active=(self._active_tab == "SYSTEM"))
        # Pill 8: SET (Sky #38bdf8)
        self._paint_pill(p, col4_x, row2_y, pw, ph, QColor("#38bdf8"), "SET", "CONFIG",
                         self._pill_scales[7], self._pill_alphas[7], self._hover_progress[7], dim_amount if self._hover_progress[7] < 0.5 else 0.0,
                         is_active=(self._active_tab == "SETTINGS"))

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
        hover_w: float = 0.0,
        dim_other: float = 0.0,
        is_active: bool = False,
    ):
        """Paint a single pill with dynamic hover glow, elevation, accent styling, and active state."""
        if scale < 0.01 or alpha < 0.01:
            return

        p.save()

        # Combine entrance scale with subtle hover elevation (scale up to 1.04)
        effective_scale = scale * (1.0 + hover_w * 0.04)
        effective_alpha = alpha * (1.0 - dim_other * 0.22)

        if effective_scale < 0.999 or effective_scale > 1.001 or effective_alpha < 0.999:
            pcx = px + pw / 2.0
            pcy = py + ph / 2.0
            p.translate(pcx, pcy)
            p.scale(effective_scale, effective_scale)
            p.translate(-pcx, -pcy)
            p.setOpacity(effective_alpha)

        rect = QRectF(px, py, pw, ph)

        # 1. Outer Accent Glow on Hover
        if hover_w > 0.02:
            glow_r = 15.0
            glow_rect = rect.adjusted(-3.0 * hover_w, -3.0 * hover_w, 3.0 * hover_w, 3.0 * hover_w)
            glow_alpha = int(55 * hover_w)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(badge_color.red(), badge_color.green(), badge_color.blue(), glow_alpha))
            p.drawRoundedRect(glow_rect, glow_r, glow_r)

        # 2. Pill Background (solid dark #16181f, or elevated luxury gradient on hover, or active state)
        if hover_w > 0.02:
            bg_grad = QLinearGradient(px, py, px, py + ph)
            top_c = QColor(
                int(22 + (badge_color.red() - 22) * 0.14 * hover_w),
                int(26 + (badge_color.green() - 26) * 0.14 * hover_w),
                int(36 + (badge_color.blue() - 36) * 0.14 * hover_w),
            )
            bot_c = QColor(
                int(20 + (badge_color.red() - 20) * 0.05 * hover_w),
                int(22 + (badge_color.green() - 22) * 0.05 * hover_w),
                int(28 + (badge_color.blue() - 28) * 0.05 * hover_w),
            )
            bg_grad.setColorAt(0.0, top_c)
            bg_grad.setColorAt(1.0, bot_c)
            p.setBrush(bg_grad)

            # Glowing Accent Border
            br = int(37 + (badge_color.red() - 37) * hover_w)
            bg = int(41 + (badge_color.green() - 41) * hover_w)
            bb = int(52 + (badge_color.blue() - 52) * hover_w)
            border_pen = QPen(QColor(br, bg, bb), 1.0 + 0.6 * hover_w)
            p.setPen(border_pen)
        elif is_active:
            # Active pill subtle emerald/graphite elevated styling
            p.setBrush(QColor("#13161c"))
            p.setPen(QPen(QColor(34, 197, 94, 140), 1.2))
        else:
            p.setPen(QPen(QColor("#252934"), 1.0))
            p.setBrush(QColor("#16181f"))

        p.drawRoundedRect(rect, 14.0, 14.0)

        # 3. Mini badge (.mini: 20x19, radius 6px) with subtle pop on hover
        bx, by, bw, bh = px + 6.0, py + 5.5, 20.0, 19.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(badge_color.lighter(int(100 + 15 * hover_w)))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 6.0, 6.0)

        # Two little black dot eyes
        p.setBrush(QColor("#000000"))
        p.drawEllipse(QPointF(bx + 6.0, by + 9.5), 1.7, 2.2)
        p.drawEllipse(QPointF(bx + 14.0, by + 9.5), 1.7, 2.2)

        # 4. Label (.lbl)
        p.setFont(QFont("Segoe UI", 7.5, QFont.Weight.DemiBold))
        lbl_metric = p.fontMetrics()
        lbl_advance = lbl_metric.horizontalAdvance(label)

        if is_active:
            lbl_color = QColor("#f1f5f9") if hover_w < 0.05 else QColor(
                int(241 + (255 - 241) * hover_w),
                int(245 + (255 - 245) * hover_w),
                int(249 + (255 - 249) * hover_w),
            )
        else:
            lbl_r = int(107 + (180 - 107) * hover_w)
            lbl_g = int(112 + (190 - 112) * hover_w)
            lbl_b = int(121 + (205 - 121) * hover_w)
            lbl_color = QColor(lbl_r, lbl_g, lbl_b)

        p.setPen(lbl_color)
        p.drawText(
            QRectF(bx + bw + 6, py, 42, ph),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        # 4b. Active Pill Indicator: Little glowing emerald jewel dot
        if is_active:
            dot_cx = bx + bw + 6.0 + lbl_advance + 5.5
            dot_cy = py + ph / 2.0

            # Soft radial emerald aura
            glow_grad = QRadialGradient(dot_cx, dot_cy, 5.0)
            glow_grad.setColorAt(0.0, QColor(34, 197, 94, 160))
            glow_grad.setColorAt(0.5, QColor(34, 197, 94, 70))
            glow_grad.setColorAt(1.0, QColor(34, 197, 94, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow_grad))
            p.drawEllipse(QPointF(dot_cx, dot_cy), 5.0, 5.0)

            # Solid vibrant emerald core (2.2px radius)
            p.setBrush(QColor("#22c55e"))
            p.drawEllipse(QPointF(dot_cx, dot_cy), 2.2, 2.2)

            # Crisp specular micro-highlight (0.7px radius)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawEllipse(QPointF(dot_cx - 0.6, dot_cy - 0.6), 0.7, 0.7)

        # 5. Value (brightens on hover or when active)
        p.setFont(QFont("Segoe UI", 8.0, QFont.Weight.Bold))
        val_color = QColor("#ffffff") if (hover_w > 0.05 or is_active) else QColor("#f5f6f8")
        p.setPen(val_color)
        p.drawText(
            QRectF(px, py, pw - 8, ph),
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
