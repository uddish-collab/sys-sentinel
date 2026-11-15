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

        # Base custom colors (provided by settings/controller)
        self.color_body = QColor("#f4f1ea")
        self.color_details = QColor("#14213d")
        self.color_eyes = QColor("#00e5ff")
        self.color_glow = QColor("#00e5ff")

        # 60 fps animation timer
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_animation_frame)
        self._timer.start()

        self._apply_mood_targets()

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

    def trigger_greeting_wave(self):
        """Startup friendly hi/hello hand waving animation."""
        self._wave_active = True
        self._wave_progress = 0.0
        self._target_mouth_curve = 1.0  # Big happy smile
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
        """Paint the full, rich SENTI mascot character."""
        # Body bounds
        bw = w * 0.68
        bh = h * 0.62
        bx = cx - bw / 2.0
        by = cy - bh / 2.0 + (h * 0.05)
        body_rect = QRectF(bx, by, bw, bh)

        # 1. Outer Glow Aura
        glow_radius = max(bw, bh) * 0.62
        glow_grad = QRadialGradient(cx, by + bh * 0.5, glow_radius)
        glow_alpha = int(45 * pulse)
        c_glow_outer = QColor(glow_c.red(), glow_c.green(), glow_c.blue(), glow_alpha)
        glow_grad.setColorAt(0.0, c_glow_outer)
        glow_grad.setColorAt(0.65, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), int(glow_alpha * 0.3)))
        glow_grad.setColorAt(1.0, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow_grad)
        p.drawEllipse(QPointF(cx, by + bh * 0.5), glow_radius, glow_radius)

        # 2. Antenna with pulsing beacon tip
        antenna_stalk_h = max(7.0, h * 0.10)
        antenna_top_y = by - antenna_stalk_h
        stalk_w = max(1.8, w * 0.024)
        p.setPen(QPen(details_c, stalk_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx, by + 3), QPointF(cx, antenna_top_y))

        # Antenna tip beacon
        tip_radius = max(2.6, h * 0.035)
        tip_glow = QRadialGradient(cx, antenna_top_y, tip_radius * 2.0)
        tip_glow.setColorAt(0.0, eyes_c)
        tip_glow.setColorAt(0.7, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(180 * pulse)))
        tip_glow.setColorAt(1.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tip_glow)
        p.drawEllipse(QPointF(cx, antenna_top_y), tip_radius * 2.0, tip_radius * 2.0)
        p.setBrush(eyes_c)
        p.drawEllipse(QPointF(cx, antenna_top_y), tip_radius, tip_radius)

        # 3. Ear Pods with light strips
        ear_w = max(6.0, w * 0.075)
        ear_h = max(12.0, h * 0.16)
        ear_y = by + bh * 0.40
        ear_r = max(2.5, ear_w * 0.4)
        # Left pod
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(details_c)
        p.drawRoundedRect(QRectF(bx - ear_w + 2, ear_y, ear_w, ear_h), ear_r, ear_r)
        # Right pod
        p.drawRoundedRect(QRectF(bx + bw - 2, ear_y, ear_w, ear_h), ear_r, ear_r)
        # Ear pod illuminated light strips
        strip_w = max(1.2, w * 0.015)
        strip_pen = QPen(eyes_c, strip_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(strip_pen)
        p.drawLine(QPointF(bx - ear_w / 2.0 + 1, ear_y + 3), QPointF(bx - ear_w / 2.0 + 1, ear_y + ear_h - 3))
        p.drawLine(QPointF(bx + bw + ear_w / 2.0 - 1, ear_y + 3), QPointF(bx + bw + ear_w / 2.0 - 1, ear_y + ear_h - 3))

        # 4. Pearl-Shelled Helmet Head
        corner_r = bw * 0.38
        shell_grad = QLinearGradient(bx, by, bx + bw, by + bh)
        shell_grad.setColorAt(0.0, body_c.lighter(116))
        shell_grad.setColorAt(0.45, body_c)
        shell_grad.setColorAt(1.0, body_c.darker(122))

        p.setPen(QPen(details_c.lighter(125), 2.5))
        p.setBrush(shell_grad)
        p.drawRoundedRect(body_rect, corner_r, corner_r)

        # Specular highlight on shell (top-left glossy reflection)
        spec_grad = QRadialGradient(bx + bw * 0.32, by + bh * 0.22, bw * 0.35)
        spec_grad.setColorAt(0.0, QColor(255, 255, 255, 140))
        spec_grad.setColorAt(0.5, QColor(255, 255, 255, 40))
        spec_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(spec_grad)
        p.drawEllipse(QPointF(bx + bw * 0.32, by + bh * 0.22), bw * 0.32, bh * 0.24)

        # Bottom shading / ambient occlusion on shell
        bottom_shadow = QLinearGradient(bx, by + bh * 0.70, bx, by + bh)
        bottom_shadow.setColorAt(0.0, QColor(10, 15, 30, 0))
        bottom_shadow.setColorAt(1.0, QColor(10, 15, 30, 60))
        p.setBrush(bottom_shadow)
        p.drawRoundedRect(body_rect, corner_r, corner_r)

        # 5. Glass Face Plate (Dark visor display)
        face_w = bw * 0.74
        face_h = bh * 0.52
        face_x = cx - face_w / 2.0
        face_y = by + bh * 0.28
        face_rect = QRectF(face_x, face_y, face_w, face_h)
        face_corner = face_w * 0.25

        face_grad = QLinearGradient(face_x, face_y, face_x + face_w, face_y + face_h)
        face_grad.setColorAt(0.0, details_c.darker(120))
        face_grad.setColorAt(0.5, details_c)
        face_grad.setColorAt(1.0, details_c.darker(130))

        p.setPen(QPen(details_c.darker(140), 1.5))
        p.setBrush(face_grad)
        p.drawRoundedRect(face_rect, face_corner, face_corner)

        # Glass sheen reflection on face plate
        p.save()
        sheen_path = QPainterPath()
        sheen_path.addRoundedRect(face_rect, face_corner, face_corner)
        p.setClipPath(sheen_path)
        sheen_grad = QLinearGradient(face_x, face_y, face_x + face_w * 0.8, face_y + face_h * 0.7)
        sheen_grad.setColorAt(0.0, QColor(255, 255, 255, 35))
        sheen_grad.setColorAt(0.4, QColor(255, 255, 255, 10))
        sheen_grad.setColorAt(0.42, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sheen_grad)
        p.drawRect(face_rect)
        p.restore()

        # 6. Glowing Eyes, Brows, and Mouth
        self._paint_facial_features(p, cx, face_y + face_h * 0.42, face_w, face_h, eyes_c, details_c, pulse)

        # 7. Sweat drop if in critical state
        if self._mood == MOOD_CRITICAL and self._sweat_progress > 0.05:
            drop_x = face_x + face_w - 9.0
            drop_y = face_y + 12.0 + self._sweat_progress * (face_h - 22.0)
            drop_alpha = int(220 * (1.0 - self._sweat_progress * 0.7))
            drop_color = QColor(0, 229, 255, drop_alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(drop_color)
            p.drawEllipse(QPointF(drop_x, drop_y), 3.0, 4.2)

    def _paint_facial_features(
        self,
        p: QPainter,
        cx: float,
        eye_center_y: float,
        face_w: float,
        face_h: float,
        eyes_c: QColor,
        details_c: QColor,
        pulse: float,
    ):
        del details_c
        # Blink height factor: dips smoothly to 0.1 during blink
        blink_factor = 1.0
        if self._is_blinking:
            # Sinusoidal blink curve (0 -> 1 -> 0)
            s = math.sin(self._blink_progress * math.pi)
            blink_factor = max(0.08, 1.0 - s * 0.92)

        # Eye sizing
        base_eye_w = face_w * 0.17 * self._eye_width
        base_eye_h = face_h * 0.32 * self._eye_height * blink_factor
        eye_spacing = face_w * 0.28

        left_eye_x = cx - eye_spacing
        right_eye_x = cx + eye_spacing

        # Draw eyes with halo glow
        for ex in (left_eye_x, right_eye_x):
            # Eye outer halo
            halo_r = max(base_eye_w, base_eye_h) * 1.5
            halo = QRadialGradient(ex, eye_center_y, halo_r)
            halo.setColorAt(0.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(130 * pulse)))
            halo.setColorAt(0.6, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(40 * pulse)))
            halo.setColorAt(1.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(ex, eye_center_y), halo_r, halo_r)

            # Eye pill/ellipse core
            eye_rect = QRectF(ex - base_eye_w / 2.0, eye_center_y - base_eye_h / 2.0, base_eye_w, base_eye_h)
            p.setBrush(eyes_c)
            p.drawRoundedRect(eye_rect, base_eye_w / 2.0, base_eye_h / 2.0)

            # Specular pupil dot if eye is open
            if blink_factor > 0.5:
                spec_w = max(2.0, base_eye_w * 0.3)
                spec_h = max(2.0, base_eye_h * 0.3)
                p.setBrush(QColor(255, 255, 255, 220))
                p.drawEllipse(QRectF(ex - base_eye_w * 0.25, eye_center_y - base_eye_h * 0.35, spec_w, spec_h))

        # Brows
        brow_len = base_eye_w * 1.25
        brow_y = eye_center_y - base_eye_h * 0.85 - 2.0
        brow_pen = QPen(eyes_c, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(brow_pen)

        if self._brow_angle > 0.05:
            # Angled worried brows: inner corners raised
            slant = brow_len * self._brow_angle * 0.5
            # Left brow: outer left is lower, inner right is higher
            p.drawLine(QPointF(left_eye_x - brow_len / 2.0, brow_y + slant),
                       QPointF(left_eye_x + brow_len / 2.0, brow_y - slant))
            # Right brow: inner left is higher, outer right is lower
            p.drawLine(QPointF(right_eye_x - brow_len / 2.0, brow_y - slant),
                       QPointF(right_eye_x + brow_len / 2.0, brow_y + slant))
        else:
            # Gentle neutral brows
            p.drawLine(QPointF(left_eye_x - brow_len / 2.0, brow_y),
                       QPointF(left_eye_x + brow_len / 2.0, brow_y))
            p.drawLine(QPointF(right_eye_x - brow_len / 2.0, brow_y),
                       QPointF(right_eye_x + brow_len / 2.0, brow_y))

        # Mouth
        mouth_y = eye_center_y + base_eye_h * 0.72 + 6.0
        mouth_w = face_w * 0.22
        mouth_pen = QPen(eyes_c, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(mouth_pen)

        if abs(self._mouth_curve) < 0.15:
            # Flat uneasy mouth
            p.drawLine(QPointF(cx - mouth_w / 2.0, mouth_y), QPointF(cx + mouth_w / 2.0, mouth_y))
        elif self._mouth_curve > 0.0:
            # Smile arc (curve downwards at bottom)
            mouth_rect = QRectF(cx - mouth_w / 2.0, mouth_y - 4, mouth_w, mouth_w * 0.55 * self._mouth_curve)
            p.drawArc(mouth_rect, 205 * 16, 130 * 16)
        else:
            # Frown arc (curve upwards)
            frown_depth = mouth_w * 0.55 * abs(self._mouth_curve)
            mouth_rect = QRectF(cx - mouth_w / 2.0, mouth_y, mouth_w, frown_depth)
            p.drawArc(mouth_rect, 25 * 16, 130 * 16)

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

        # Glass reflection sweep on orb face disc
        p.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(QPointF(cx, cy), inner_r, inner_r)
        p.setClipPath(clip_path)

        refl_grad = QLinearGradient(cx - inner_r, cy - inner_r, cx + inner_r * 0.5, cy + inner_r * 0.5)
        refl_grad.setColorAt(0.0, QColor(255, 255, 255, 45))
        refl_grad.setColorAt(0.5, QColor(255, 255, 255, 12))
        refl_grad.setColorAt(0.52, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(refl_grad)
        p.drawRect(QRectF(cx - inner_r, cy - inner_r, inner_r * 2.0, inner_r * 2.0))
        p.restore()

        # Orb Eyes
        blink_factor = 1.0
        if self._is_blinking:
            s = math.sin(self._blink_progress * math.pi)
            blink_factor = max(0.08, 1.0 - s * 0.92)

        eye_w = inner_r * 0.32 * self._eye_width
        eye_h = inner_r * 0.46 * self._eye_height * blink_factor
        spacing = inner_r * 0.42

        for ex in (cx - spacing, cx + spacing):
            # Halo
            halo = QRadialGradient(ex, cy, eye_w * 1.4)
            halo.setColorAt(0.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(140 * pulse)))
            halo.setColorAt(1.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(ex, cy), eye_w * 1.4, eye_w * 1.4)

            # Core
            eye_rect = QRectF(ex - eye_w / 2.0, cy - eye_h / 2.0, eye_w, eye_h)
            p.setBrush(eyes_c)
            p.drawRoundedRect(eye_rect, eye_w / 2.0, eye_h / 2.0)

            # Specular dot
            if blink_factor > 0.5:
                p.setBrush(QColor(255, 255, 255, 220))
                p.drawEllipse(QRectF(ex - eye_w * 0.25, cy - eye_h * 0.35, max(2.0, eye_w * 0.3), max(2.0, eye_h * 0.3)))

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
