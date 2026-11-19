"""Original painter-drawn SENTI character and compact Orb companion widget.

Renders high-fidelity animated expressions, lighting, blinking, and morphing.
"""

import math
import random
import time
from typing import Optional, Tuple
from PySide6.QtCore import (
    Qt,
    QTimer,
    QRectF,
    QPointF,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QLinearGradient,
    QRadialGradient,
    QPainterPath,
    QPixmap,
    QImage,
)
from PySide6.QtWidgets import QWidget

from senti_state import MOOD_CALM, MOOD_WARNING, MOOD_CRITICAL


class SentiMascot(QWidget):
    """The animated visual embodiment of SENTI."""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._mood = MOOD_CALM

        # Morph property: 0.0 = full character, 1.0 = compact orb
        self._orb: float = 0.0

        # Animation states & smoothing variables
        self._phase: float = 0.0
        self._squish_scale: float = 1.0

        # Expression targets and current eased values
        self._eye_width: float = 1.0
        self._target_eye_width: float = 1.0

        self._eye_height: float = 1.0
        self._target_eye_height: float = 1.0

        self._brow_angle: float = 0.0  # 0.0 calm, +0.3 warning, +0.6 critical
        self._target_brow_angle: float = 0.0

        self._mouth_curve: float = 1.0  # +1.0 smile, 0.0 flat, -1.0 frown
        self._target_mouth_curve: float = 1.0

        self._pulse_speed: float = 1.5
        self._target_pulse_speed: float = 1.5

        # Lighting tint smoothing
        self._tint_amount: float = 0.0
        self._target_tint_amount: float = 0.0
        self._tint_r: float = 0.0
        self._tint_g: float = 0.0
        self._tint_b: float = 0.0

        # Shake & sweat drop
        self._shake_amount: float = 0.0
        self._target_shake_amount: float = 0.0
        self._sweat_progress: float = 0.0

        # Blinking state
        self._is_blinking: bool = False
        self._blink_progress: float = 0.0
        self._last_blink_time = time.time()
        self._next_blink_interval = random.uniform(2.5, 4.5)

        # Waving hand animation state
        self._wave_amount: float = 0.0
        self._target_wave_amount: float = 0.0
        self._wave_time_remaining: float = 0.0

        # Gaze tracking & expressive reactions (when hovering telemetry pills)
        self._gaze_x: float = 0.0
        self._target_gaze_x: float = 0.0
        self._gaze_y: float = 0.0
        self._target_gaze_y: float = 0.0
        self._wink_amount: float = 0.0
        self._target_wink_amount: float = 0.0
        self._pill_focus: Optional[str] = None

        # Base custom colors (provided by settings/controller)
        self.color_body = QColor("#f4f1ea")
        self.color_details = QColor("#14213d")
        self.color_eyes = QColor("#00e5ff")
        self.color_glow = QColor("#00e5ff")

        # 60 fps animation timer (starts on show, stops on hide)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_animation_frame)

        self._apply_mood_targets()

    def showEvent(self, event):
        super().showEvent(event)
        self._last_blink_time = time.time()
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._timer.isActive():
            self._timer.stop()

    # --- Properties ---

    def get_orb(self) -> float:
        return self._orb

    def set_orb(self, val: float):
        self._orb = max(0.0, min(1.0, float(val)))
        self.update()

    orb = Property(float, get_orb, set_orb)

    def set_mood(self, mood: str):
        if self._mood != mood:
            self._mood = mood
            self._apply_mood_targets()

    def get_mood(self) -> str:
        return self._mood

    def set_palette_colors(self, body: QColor, details: QColor, eyes: QColor, glow: QColor):
        self.color_body = QColor(body)
        self.color_details = QColor(details)
        self.color_eyes = QColor(eyes)
        self.color_glow = QColor(glow)
        self.update()

    def trigger_squish(self):
        """Squish feedback when clicked."""
        self._squish_scale = 0.88

    def trigger_greeting_wave(self, duration_s: float = 2.2):
        """Startup friendly hi/hello hand waving animation."""
        self._target_wave_amount = 1.0
        self._wave_time_remaining = duration_s
        self.trigger_squish()
        self.update()

    def trigger_wave(self, duration_s: float = 2.2):
        self.trigger_greeting_wave(duration_s)

    def stop_wave(self):
        """Immediately stop any waving animation and tuck hand back down."""
        self._target_wave_amount = 0.0
        self._wave_amount = 0.0
        self._wave_time_remaining = 0.0
        self.update()

    def set_pill_hover_focus(self, pill_name: Optional[str], telemetry: Optional[dict] = None):
        """Dynamic eye tracking & expressive reaction when hovering over island pills."""
        self._pill_focus = pill_name

        if not pill_name:
            self._target_gaze_x = 0.0
            self._target_gaze_y = 0.0
            self._target_wink_amount = 0.0
            self._target_eye_width = 1.0
            self._target_eye_height = 1.0
            self._target_brow_angle = 0.0
            self._target_tint_amount = 0.0
            self.update()
            return

        # Senti sits in Card 1 on the left; pills are arranged in Card 2 on the right.
        # Set distinct gaze vectors looking toward the specific pill.
        gaze_map = {
            "pill_cpu": (0.60, -0.22, QColor("#22c55e")),
            "pill_ram": (0.75, -0.22, QColor("#f5a524")),
            "pill_gpu": (0.90, -0.18, QColor("#00e5ff")),
            "pill_net": (1.00, -0.12, QColor("#a855f7")),
            "pill_disk": (0.60, 0.28, QColor("#6366f1")),
            "pill_temp": (0.75, 0.28, QColor("#f4505e")),
            "pill_sys": (0.90, 0.24, QColor("#10b981")),
            "pill_set": (1.00, 0.24, QColor("#38bdf8")),
        }

        gx, gy, color = gaze_map.get(pill_name, (0.75, 0.0, QColor("#00e5ff")))
        self._target_gaze_x = gx
        self._target_gaze_y = gy

        # Pill accent lighting tint on Senti's visor glow and eyes
        self._tint_r = float(color.red())
        self._tint_g = float(color.green())
        self._tint_b = float(color.blue())
        self._target_tint_amount = 0.50

        # Check telemetry for metric state
        telem = telemetry or {}
        val = 0.0
        if pill_name == "pill_cpu":
            val = telem.get("cpu", 0.0)
        elif pill_name == "pill_ram":
            val = telem.get("ram", 0.0)
        elif pill_name == "pill_gpu":
            val = telem.get("gpu_load", 0.0)
        elif pill_name == "pill_disk":
            val = telem.get("disk", 0.0)
        elif pill_name == "pill_temp":
            val = telem.get("temperature_c") or 0.0

        if pill_name == "pill_set":
            # Playful cute wink when hovering Settings!
            self._target_wink_amount = 1.0
            self._target_brow_angle = 0.15
            self._target_eye_width = 1.05
            self.trigger_squish()
        elif val >= 75.0:
            # Alert / curious attentive wide-eyed look
            self._target_wink_amount = 0.0
            self._target_eye_width = 1.25
            self._target_eye_height = 1.20
            self._target_brow_angle = 0.25
            self.trigger_squish()
        else:
            # Happy attentive focus
            self._target_wink_amount = 0.0
            self._target_eye_width = 1.08
            self._target_eye_height = 1.0
            self._target_brow_angle = 0.0
            self.trigger_squish()

        self.update()

    # --- Mood Configurations ---

    def _apply_mood_targets(self):
        if self._mood == MOOD_CRITICAL:
            self._target_eye_width = 1.35
            self._target_eye_height = 1.35
            self._target_brow_angle = 0.65
            self._target_mouth_curve = -1.0  # frown
            self._target_pulse_speed = 4.5
            self._target_shake_amount = 2.2
            # Red tint (255, 59, 74)
            self._target_tint_amount = 0.95
            self._tint_r, self._tint_g, self._tint_b = 255.0, 59.0, 74.0

        elif self._mood == MOOD_WARNING:
            self._target_eye_width = 1.18
            self._target_eye_height = 1.15
            self._target_brow_angle = 0.35
            self._target_mouth_curve = 0.0   # flat
            self._target_pulse_speed = 3.0
            self._target_shake_amount = 0.0
            # Amber tint (255, 176, 32). Blend factor 0.92 so cyan + amber never looks green!
            self._target_tint_amount = 0.92
            self._tint_r, self._tint_g, self._tint_b = 255.0, 176.0, 32.0

        else:  # Calm
            self._target_eye_width = 1.0
            self._target_eye_height = 1.0
            self._target_brow_angle = 0.0
            self._target_mouth_curve = 1.0   # smile
            self._target_pulse_speed = 1.5
            self._target_shake_amount = 0.0
            self._target_tint_amount = 0.0

    # --- Animation Frame ---

    def _on_animation_frame(self):
        if not self.isVisible() or not self.window().isVisible():
            return

        now = time.time()
        dt = 0.016

        # Bobbing & pulsing phase
        self._phase += self._pulse_speed * dt

        # Smooth exponential easing for expression parameters
        alpha = 0.14
        self._eye_width += (self._target_eye_width - self._eye_width) * alpha
        self._eye_height += (self._target_eye_height - self._eye_height) * alpha
        self._brow_angle += (self._target_brow_angle - self._brow_angle) * alpha
        self._mouth_curve += (self._target_mouth_curve - self._mouth_curve) * alpha
        self._pulse_speed += (self._target_pulse_speed - self._pulse_speed) * alpha
        self._shake_amount += (self._target_shake_amount - self._shake_amount) * alpha
        self._tint_amount += (self._target_tint_amount - self._tint_amount) * alpha

        # Gaze and expressive wink easing
        self._gaze_x += (self._target_gaze_x - self._gaze_x) * 0.22
        self._gaze_y += (self._target_gaze_y - self._gaze_y) * 0.22
        self._wink_amount += (self._target_wink_amount - self._wink_amount) * 0.22

        # Waving hand timer
        if self._wave_time_remaining > 0:
            self._wave_time_remaining -= dt
            if self._wave_time_remaining <= 0:
                self._target_wave_amount = 0.0
        self._wave_amount += (self._target_wave_amount - self._wave_amount) * 0.18

        # Squish spring back
        self._squish_scale += (1.0 - self._squish_scale) * 0.20

        # Sweat drop cycle in critical state
        if self._mood == MOOD_CRITICAL:
            self._sweat_progress = (self._sweat_progress + dt * 1.2) % 1.0
        else:
            self._sweat_progress = 0.0

        # Blinking logic (160ms total duration)
        if not self._is_blinking:
            if (now - self._last_blink_time) >= self._next_blink_interval:
                self._is_blinking = True
                self._blink_progress = 0.0
        else:
            self._blink_progress += dt / 0.160
            if self._blink_progress >= 1.0:
                self._is_blinking = False
                self._last_blink_time = now
                self._next_blink_interval = random.uniform(2.2, 5.0)

        self.update()

    # --- Tint Blending Helper ---

    def _get_effective_colors(self) -> Tuple[QColor, QColor, QColor, QColor]:
        """Blend lighting tint into eye and glow colors at paint time without writing to settings."""
        if self._tint_amount <= 0.01:
            return self.color_body, self.color_details, self.color_eyes, self.color_glow

        t = self._tint_amount

        # Blend eyes
        er = int(self.color_eyes.red() * (1.0 - t) + self._tint_r * t)
        eg = int(self.color_eyes.green() * (1.0 - t) + self._tint_g * t)
        eb = int(self.color_eyes.blue() * (1.0 - t) + self._tint_b * t)
        effective_eyes = QColor(er, eg, eb)

        # Blend glow
        gr = int(self.color_glow.red() * (1.0 - t) + self._tint_r * t)
        gg = int(self.color_glow.green() * (1.0 - t) + self._tint_g * t)
        gb = int(self.color_glow.blue() * (1.0 - t) + self._tint_b * t)
        effective_glow = QColor(gr, gg, gb)

        return self.color_body, self.color_details, effective_eyes, effective_glow

    # --- Painting ---

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self.render_to_painter(p, self.width(), self.height())
        finally:
            p.end()

    def render_to_painter(self, p: QPainter, w: float, h: float):
        """Render mascot graphics to any QPainter target."""
        cx = w / 2.0
        cy = h / 2.0

        body_c, details_c, eyes_c, glow_c = self._get_effective_colors()

        # Shake calculation (active in critical state)
        shake_x = 0.0
        shake_y = 0.0
        if self._shake_amount > 0.05:
            shake_x = math.sin(self._phase * 18.0) * self._shake_amount
            shake_y = math.cos(self._phase * 22.0) * (self._shake_amount * 0.7)

        # Vertical bobbing (calm: smooth gentle float; orb: minimal/none)
        bob = math.sin(self._phase) * (2.8 * (1.0 - self._orb))

        # Pulse multiplier for glow
        pulse = 0.78 + 0.22 * math.sin(self._phase * 2.0)

        # Center with squish and shake
        p.save()
        p.translate(cx + shake_x, cy + bob + shake_y)
        p.scale(1.0 / self._squish_scale, self._squish_scale)
        p.translate(-cx, -cy)

        # Draw character or orb based on self._orb interpolation
        if self._orb > 0.99:
            self._paint_orb(p, cx, cy, body_c, details_c, eyes_c, glow_c, pulse)
        elif self._orb < 0.01:
            self._paint_character(p, cx, cy, w, h, body_c, details_c, eyes_c, glow_c, pulse)
        else:
            # Cross-fade between full character and orb
            p.save()
            p.setOpacity(1.0 - self._orb)
            self._paint_character(p, cx, cy, w, h, body_c, details_c, eyes_c, glow_c, pulse)
            p.restore()

            p.save()
            p.setOpacity(self._orb)
            self._paint_orb(p, cx, cy, body_c, details_c, eyes_c, glow_c, pulse)
            p.restore()

        p.restore()

    def _paint_character(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        w: float,
        h: float,
        body_c: QColor,
        details_c: QColor,
        eyes_c: QColor,
        glow_c: QColor,
        pulse: float,
    ):
        """Paint Option D: The Visor Astronaut (Cyber-Luxury Minimalist)."""
        del details_c

        # Body bounds (sleek ceramic squircle helmet)
        bw = max(40.0, min(w * 0.70, 54.0))
        bh = max(34.0, min(h * 0.60, 46.0))
        bx = cx - bw / 2.0
        by = cy - bh / 2.0 + (h * 0.03)
        body_rect = QRectF(bx, by, bw, bh)
        corner_r = bw * 0.36

        # 1. Radiant Outer Aura Glow (Dynamic theme glow)
        glow_radius = max(bw, bh) * 0.80
        glow_grad = QRadialGradient(cx, cy, glow_radius)
        glow_alpha = int(115 * pulse)
        glow_grad.setColorAt(0.0, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), glow_alpha))
        glow_grad.setColorAt(0.40, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), int(glow_alpha * 0.60)))
        glow_grad.setColorAt(0.72, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), int(glow_alpha * 0.20)))
        glow_grad.setColorAt(1.0, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow_grad)
        p.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

        # 2. Dynamic Theme Helmet Shell
        shell_grad = QLinearGradient(bx, by, bx, by + bh)
        shell_grad.setColorAt(0.0, body_c)
        bot_c = body_c.darker(118) if body_c.lightness() > 90 else body_c.lighter(130)
        shell_grad.setColorAt(1.0, bot_c)
        border_c = QColor(255, 255, 255, 45) if body_c.lightness() > 90 else QColor(255, 255, 255, 25)
        p.setPen(QPen(border_c, 1.0))
        p.setBrush(shell_grad)
        p.drawRoundedRect(body_rect, corner_r, corner_r)

        # Subtle specular hairline on top curve of helmet
        spec_path = QPainterPath()
        spec_path.moveTo(bx + corner_r * 0.7, by + 1.2)
        spec_path.lineTo(bx + bw - corner_r * 0.7, by + 1.2)
        p.setPen(QPen(QColor(255, 255, 255, 140), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(spec_path)

        # 3. Solid Opaque Obsidian Visor (No glass sheen, deep dark matte)
        vw = bw * 0.76
        vh = bh * 0.48
        vx = cx - vw / 2.0
        vy = cy - vh / 2.0 + (h * 0.02)
        visor_rect = QRectF(vx, vy, vw, vh)
        vr = vh / 2.0  # Fully rounded capsule pill

        p.setPen(QPen(QColor("#141720"), 1.0))
        p.setBrush(QColor("#07080a"))
        p.drawRoundedRect(visor_rect, vr, vr)

        # 4. Glowing Eyes inside Visor
        self._paint_facial_features(p, cx, vy + vh * 0.5, vw, vh, eyes_c, pulse)

        # 5. Animated Single Waving Glove Paw (Only one hand when waving)
        if self._wave_amount > 0.01:
            pw = max(9.0, bw * 0.20)
            ph = max(14.0, bh * 0.30)
            paw_cx = bx + bw + 1.0
            paw_cy = by + bh * 0.35 - (self._wave_amount * 10.0)
            wave_rot = -26.0 + 22.0 * math.sin(self._phase * 12.0)

            p.save()
            p.translate(paw_cx, paw_cy)
            p.rotate(wave_rot)
            p.scale(self._wave_amount, self._wave_amount)

            # Glove body
            glove_rect = QRectF(-pw / 2.0, -ph / 2.0, pw, ph)
            p.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
            p.setBrush(QColor("#f4f5f9"))
            p.drawRoundedRect(glove_rect, pw / 2.0, pw / 2.0)

            # Micro-accent cuff matching theme aura
            cuff_rect = QRectF(-pw * 0.42, ph * 0.25, pw * 0.84, max(2.0, ph * 0.15))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow_c)
            p.drawRoundedRect(cuff_rect, 1.2, 1.2)
            p.restore()

    def _paint_facial_features(
        self,
        p: QPainter,
        cx: float,
        eye_center_y: float,
        visor_w: float,
        visor_h: float,
        eyes_c: QColor,
        pulse: float,
    ):
        """Paint glowing pill eyes inside the visor."""
        # Blink height factor
        blink_factor = 1.0
        if self._is_blinking:
            s = math.sin(self._blink_progress * math.pi)
            blink_factor = max(0.08, 1.0 - s * 0.92)

        # Eye sizing
        eye_w = max(4.0, visor_w * 0.16 * self._eye_width)
        base_h = max(7.0, visor_h * 0.44 * self._eye_height)
        eye_h = max(1.8, base_h * blink_factor)
        eye_spacing = visor_w * 0.24

        # Gaze tracking shifts (looking directly at hovered pill)
        shift_x = self._gaze_x * (visor_w * 0.12)
        shift_y = self._gaze_y * (visor_h * 0.12)

        left_eye_x = cx - eye_spacing + shift_x
        right_eye_x = cx + eye_spacing + shift_x
        gaze_center_y = eye_center_y + shift_y

        # Soft halo glow behind eyes
        halo_r = max(eye_w, base_h) * 1.4
        glow_alpha = int(55 * pulse)
        for ex in (left_eye_x, right_eye_x):
            halo = QRadialGradient(ex, gaze_center_y, halo_r)
            halo.setColorAt(0.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), glow_alpha))
            halo.setColorAt(0.65, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(glow_alpha * 0.3)))
            halo.setColorAt(1.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(ex, gaze_center_y), halo_r, halo_r)

        # Solid Glowing Pill Eyes
        p.setBrush(eyes_c)
        er = eye_w / 2.0

        # Left eye
        left_eye_rect = QRectF(left_eye_x - er, gaze_center_y - eye_h / 2.0, eye_w, eye_h)
        p.drawRoundedRect(left_eye_rect, er, er)
        if blink_factor > 0.6:
            spec_r = max(1.0, eye_w * 0.22)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(left_eye_x - er * 0.3, gaze_center_y - eye_h * 0.25), spec_r, spec_r)
            p.setBrush(eyes_c)

        # Right eye (handles normal blink and playful wink)
        right_blink = blink_factor * max(0.12, 1.0 - self._wink_amount * 0.88)
        right_eye_h = max(1.8, base_h * right_blink)
        right_eye_rect = QRectF(right_eye_x - er, gaze_center_y - right_eye_h / 2.0, eye_w, right_eye_h)
        p.drawRoundedRect(right_eye_rect, er, min(er, right_eye_h / 2.0))
        if right_blink > 0.6:
            spec_r = max(1.0, eye_w * 0.22)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(right_eye_x - er * 0.3, gaze_center_y - right_eye_h * 0.25), spec_r, spec_r)
            p.setBrush(eyes_c)

    def _paint_orb(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        body_c: QColor,
        details_c: QColor,
        eyes_c: QColor,
        glow_c: QColor,
        pulse: float,
    ):
        """Paint the compact, polished Orb form (~72px)."""
        dia = min(self.width(), self.height()) - 12.0
        radius = dia / 2.0

        # Outer aura
        glow_radius = radius * 1.35
        glow = QRadialGradient(cx, cy, glow_radius)
        glow_alpha = int(50 * pulse)
        glow.setColorAt(0.0, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), glow_alpha))
        glow.setColorAt(0.7, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), int(glow_alpha * 0.3)))
        glow.setColorAt(1.0, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

        # Outer shell ring with metallic/pearly gradient
        shell_grad = QLinearGradient(cx - radius, cy - radius, cx + radius, cy + radius)
        shell_grad.setColorAt(0.0, body_c.lighter(118))
        shell_grad.setColorAt(0.5, body_c)
        shell_grad.setColorAt(1.0, body_c.darker(125))

        p.setPen(QPen(details_c.lighter(125), 2.0))
        p.setBrush(shell_grad)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # Inner dark face disc
        inner_r = radius * 0.72
        inner_grad = QRadialGradient(cx, cy, inner_r)
        inner_grad.setColorAt(0.0, details_c)
        inner_grad.setColorAt(1.0, details_c.darker(130))

        p.setPen(QPen(details_c.darker(140), 1.5))
        p.setBrush(inner_grad)
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)


        # Orb Eyes
        blink_factor = 1.0
        if self._is_blinking:
            s = math.sin(self._blink_progress * math.pi)
            blink_factor = max(0.08, 1.0 - s * 0.92)

        eye_w = inner_r * 0.32 * self._eye_width
        eye_h = inner_r * 0.46 * self._eye_height * blink_factor
        spacing = inner_r * 0.42

        shift_x = self._gaze_x * (inner_r * 0.15)
        shift_y = self._gaze_y * (inner_r * 0.15)

        for ex in (cx - spacing + shift_x, cx + spacing + shift_x):
            ey = cy + shift_y
            # Halo
            halo = QRadialGradient(ex, ey, eye_w * 1.4)
            halo.setColorAt(0.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(140 * pulse)))
            halo.setColorAt(1.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(ex, ey), eye_w * 1.4, eye_w * 1.4)

            # Core
            eye_rect = QRectF(ex - eye_w / 2.0, ey - eye_h / 2.0, eye_w, eye_h)
            p.setBrush(eyes_c)
            p.drawRoundedRect(eye_rect, eye_w / 2.0, eye_h / 2.0)

            # Specular dot
            if blink_factor > 0.5:
                p.setBrush(QColor(255, 255, 255, 220))
                p.drawEllipse(QRectF(ex - eye_w * 0.25, ey - eye_h * 0.35, max(2.0, eye_w * 0.3), max(2.0, eye_h * 0.3)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.trigger_squish()
            self.clicked.emit()
            event.accept()


def render_mascot_image(size: int = 256, is_orb: bool = True) -> QImage:
    """Render the mascot orb or character with transparent background onto a QImage."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    mascot = SentiMascot()
    mascot.resize(size, size)
    mascot.set_orb(1.0 if is_orb else 0.0)
    mascot._timer.stop()

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    mascot.render_to_painter(p, size, size)
    p.end()

    return img
