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

        # Funny expression state & particle systems (for island click interactions)
        self._funny_expression: Optional[str] = None
        self._funny_time_remaining: float = 0.0
        self._funny_idx: int = 0
        self._head_tilt: float = 0.0
        self._target_head_tilt: float = 0.0
        self._left_gaze_offset_x: float = 0.0
        self._right_gaze_offset_x: float = 0.0
        self._left_gaze_offset_y: float = 0.0
        self._right_gaze_offset_y: float = 0.0
        self._blush_amount: float = 0.0
        self._target_blush: float = 0.0
        self._particles: List[Dict[str, Any]] = []
        self._lightning_arcs: List[List[QPointF]] = []

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

    def reset_funny_expression(self):
        """Restore normal face expression after a funny interaction."""
        self._funny_expression = None
        self._funny_time_remaining = 0.0
        self._target_head_tilt = 0.0
        self._target_blush = 0.0
        self._left_gaze_offset_x = 0.0
        self._right_gaze_offset_x = 0.0
        self._left_gaze_offset_y = 0.0
        self._right_gaze_offset_y = 0.0
        self._particles.clear()
        self._lightning_arcs.clear()
        self._apply_mood_targets()
        self.update()

    def trigger_funny_expression(self) -> Optional[str]:
        """Trigger a hilarious face reaction when tapped inside the island dock.
        
        Features a strict 2.0-second lockout gate: subsequent clicks during
        an active reaction are safely ignored so Senti stays in the current state.
        Returns the matching sound effect name, or None if locked out.
        """
        if self._funny_time_remaining > 0:
            return None

        expressions = ["shock", "annoyed", "wink", "love", "derp"]
        expr = expressions[self._funny_idx % len(expressions)]
        self._funny_idx += 1

        self._funny_expression = expr
        self._funny_time_remaining = 2.0  # Exactly 2.0 seconds
        self._particles.clear()
        self._lightning_arcs.clear()

        sound_name = "pop"

        if expr == "shock":
            # 1. Shock: Softened neon electric yellow aura, lightning plasma arcs, bug-eyes
            self._target_eye_width = 1.60
            self._target_eye_height = 1.55
            self._target_brow_angle = 0.45
            self._target_head_tilt = -2.0
            self._left_gaze_offset_x = 0.0
            self._right_gaze_offset_x = 0.0
            self._left_gaze_offset_y = -0.25
            self._right_gaze_offset_y = -0.25
            self._target_wink_amount = 0.0
            self._target_blush = 0.0
            self._squish_scale = 0.76
            sound_name = "pop"

        elif expr == "annoyed":
            # 2. Annoyed: Crimson red smolder, rising smoke wisps, drooping side-eye
            self._target_eye_width = 1.25
            self._target_eye_height = 0.38
            self._target_brow_angle = -0.25
            self._target_head_tilt = -7.0
            self._left_gaze_offset_x = -0.85
            self._right_gaze_offset_x = -0.85
            self._left_gaze_offset_y = 0.08
            self._right_gaze_offset_y = 0.08
            self._target_wink_amount = 0.0
            self._target_blush = 0.0
            self._squish_scale = 0.92
            sound_name = "annoyed"

        elif expr == "wink":
            # 3. Wink: 3D fluttering party confetti ribbons, winking right eye, paw wave
            self._target_eye_width = 1.25
            self._target_eye_height = 1.15
            self._target_brow_angle = 0.20
            self._target_head_tilt = 6.0
            self._left_gaze_offset_x = 0.20
            self._right_gaze_offset_x = 0.20
            self._left_gaze_offset_y = 0.0
            self._right_gaze_offset_y = 0.0
            self._target_wink_amount = 1.0
            self._target_blush = 0.0
            self._squish_scale = 0.85
            self.trigger_greeting_wave(duration_s=1.6)

            # Spawn 26 multi-colored fluttering confetti ribbons
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            confetti_colors = [
                QColor("#38bdf8"), QColor("#f43f5e"), QColor("#facc15"),
                QColor("#a855f7"), QColor("#34d399")
            ]
            for _ in range(26):
                self._particles.append({
                    "type": "confetti",
                    "x": cx + random.uniform(-22.0, 22.0),
                    "y": cy - random.uniform(-4.0, 10.0),
                    "vx": random.uniform(-2.6, 2.6),
                    "vy": random.uniform(-4.8, -2.2),
                    "rot": random.uniform(0.0, 360.0),
                    "vrot": random.uniform(-10.0, 10.0),
                    "w": random.uniform(4.5, 7.5),
                    "h": random.uniform(3.0, 5.0),
                    "color": random.choice(confetti_colors),
                    "life": 1.0,
                })
            sound_name = "wink"

        elif expr == "love":
            # 4. Love: Floating red hearts on sine-wave trails, soft cheek blush, anime arcs
            self._target_eye_width = 1.30
            self._target_eye_height = 0.70
            self._target_brow_angle = 0.30
            self._target_head_tilt = 4.0
            self._left_gaze_offset_x = 0.0
            self._right_gaze_offset_x = 0.0
            self._left_gaze_offset_y = 0.0
            self._right_gaze_offset_y = 0.0
            self._target_wink_amount = 0.0
            self._target_blush = 1.0
            self._squish_scale = 0.82
            sound_name = "love"

        elif expr == "derp":
            # 5. Goofy / Derp: 3D inclined orbiting cartoon stars, cross-eyed gaze, head tilt
            self._target_eye_width = 1.15
            self._target_eye_height = 0.95
            self._target_brow_angle = -0.30
            self._target_head_tilt = 12.0
            self._left_gaze_offset_x = 0.90   # left eye looks right
            self._right_gaze_offset_x = -0.90  # right eye looks left (cross-eyed!)
            self._left_gaze_offset_y = 0.15
            self._right_gaze_offset_y = -0.15
            self._target_wink_amount = 0.0
            self._target_blush = 0.0
            self._squish_scale = 0.82
            sound_name = "dizzy"

        self.update()
        return sound_name

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

        # Smooth exponential easing for expression parameters (snappy, responsive)
        alpha = 0.28
        self._eye_width += (self._target_eye_width - self._eye_width) * alpha
        self._eye_height += (self._target_eye_height - self._eye_height) * alpha
        self._brow_angle += (self._target_brow_angle - self._brow_angle) * alpha
        self._mouth_curve += (self._target_mouth_curve - self._mouth_curve) * alpha
        self._pulse_speed += (self._target_pulse_speed - self._pulse_speed) * alpha
        self._shake_amount += (self._target_shake_amount - self._shake_amount) * alpha
        self._tint_amount += (self._target_tint_amount - self._tint_amount) * alpha

        # Gaze and expressive wink easing (instant, fluid tracking)
        self._gaze_x += (self._target_gaze_x - self._gaze_x) * 0.40
        self._gaze_y += (self._target_gaze_y - self._gaze_y) * 0.40
        self._wink_amount += (self._target_wink_amount - self._wink_amount) * 0.40
        self._head_tilt += (self._target_head_tilt - self._head_tilt) * 0.35
        self._blush_amount += (self._target_blush - self._blush_amount) * 0.30

        # Funny expression timer (strict 2.0s duration)
        if self._funny_time_remaining > 0:
            self._funny_time_remaining -= dt
            if self._funny_time_remaining <= 0:
                self.reset_funny_expression()
            else:
                self._update_funny_particles(dt)

        # Waving hand timer
        if self._wave_time_remaining > 0:
            self._wave_time_remaining -= dt
            if self._wave_time_remaining <= 0:
                self._target_wave_amount = 0.0
        self._wave_amount += (self._target_wave_amount - self._wave_amount) * 0.32

        # Squish spring back
        self._squish_scale += (1.0 - self._squish_scale) * 0.35

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

    def _update_funny_particles(self, dt: float):
        """Update physics-based particle systems for active funny expressions."""
        cx = self.width() / 2.0
        cy = self.height() / 2.0

        # 1. Shock: Procedural high-voltage lightning plasma arcs
        if self._funny_expression == "shock":
            if random.random() < 0.75:
                angle = random.uniform(0.0, math.pi * 2.0)
                r_helmet = random.uniform(22.0, 36.0)
                sx = cx + math.cos(angle) * r_helmet
                sy = cy + math.sin(angle) * (r_helmet * 0.72)
                pts = [QPointF(sx, sy)]
                curr_x, curr_y = sx, sy
                for _ in range(random.randint(3, 5)):
                    curr_x += random.uniform(-10.0, 10.0)
                    curr_y += random.uniform(-10.0, 10.0)
                    pts.append(QPointF(curr_x, curr_y))
                self._lightning_arcs = [pts]
            else:
                self._lightning_arcs.clear()

        # 2. Annoyed: Rising steam / smoke wisps and drifting angry red embers
        elif self._funny_expression == "annoyed":
            self._lightning_arcs.clear()
            if random.random() < 0.38 and len(self._particles) < 22:
                self._particles.append({
                    "type": "smoke",
                    "x": cx + random.uniform(-16.0, 16.0),
                    "y": cy - 14.0,
                    "vx": random.uniform(-0.4, 0.4),
                    "vy": random.uniform(-1.2, -0.6),
                    "radius": random.uniform(3.0, 5.0),
                    "alpha": 0.65,
                })
            if random.random() < 0.32 and len(self._particles) < 28:
                self._particles.append({
                    "type": "ember",
                    "x": cx + random.uniform(-18.0, 18.0),
                    "y": cy - 10.0,
                    "vx": random.uniform(-0.6, 0.6),
                    "vy": random.uniform(-1.5, -0.7),
                    "radius": random.uniform(1.2, 2.4),
                    "alpha": 0.95,
                    "color": QColor("#ef4444") if random.random() < 0.70 else QColor("#f97316"),
                })

        # 3. Love: Floating bezier hearts drifting into thin air along sine-wave trails
        elif self._funny_expression == "love":
            self._lightning_arcs.clear()
            if random.random() < 0.28 and len(self._particles) < 18:
                spawn_x = cx + random.uniform(-18.0, 18.0)
                self._particles.append({
                    "type": "heart",
                    "x": spawn_x,
                    "base_x": spawn_x,
                    "y": cy - 6.0,
                    "vy": random.uniform(-1.3, -0.7),
                    "size": random.uniform(7.0, 11.0),
                    "alpha": 1.0,
                    "sway_phase": random.uniform(0.0, math.pi * 2.0),
                    "sway_freq": random.uniform(3.0, 5.5),
                    "sway_amp": random.uniform(1.2, 2.4),
                    "color": QColor("#e11d48") if random.random() < 0.65 else QColor("#fb7185"),
                })

        # Update and step all active particles
        for i in range(len(self._particles) - 1, -1, -1):
            p = self._particles[i]
            if p["type"] == "confetti":
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["vy"] += 0.18  # gravity
                p["vx"] *= 0.98  # air drag
                p["rot"] += p["vrot"]
                p["life"] -= dt
                if p["life"] <= 0.0 or p["y"] > self.height() + 10:
                    self._particles.pop(i)
            elif p["type"] == "smoke":
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["radius"] += dt * 4.5
                p["alpha"] -= dt * 0.45
                if p["alpha"] <= 0.0:
                    self._particles.pop(i)
            elif p["type"] == "heart":
                p["y"] += p["vy"]
                p["sway_phase"] += dt * p["sway_freq"]
                p["x"] = p["base_x"] + math.sin(p["sway_phase"]) * p["sway_amp"]
                p["alpha"] -= dt * 0.48
                if p["alpha"] <= 0.0 or p["y"] < -10:
                    self._particles.pop(i)
            elif p["type"] == "ember":
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["alpha"] -= dt * 0.65
                p["radius"] = max(0.5, p["radius"] - dt * 0.5)
                if p["alpha"] <= 0.0 or p["y"] < -10:
                    self._particles.pop(i)

    # --- Tint Blending Helper ---

    def _get_effective_colors(self) -> Tuple[QColor, QColor, QColor, QColor]:
        """Blend lighting tint into eye and glow colors at paint time without writing to settings."""
        # 1. Funny Expression Overrides (Always blueish eyes + expression-specific auras)
        if self._funny_expression:
            effective_eyes = QColor("#00e5ff")  # ALWAYS BLUEISH ACROSS ALL THEMES!

            if self._funny_expression == "shock":
                # Electric vibrant golden-yellow lightning aura
                effective_glow = QColor(250, 204, 21, 235)
            elif self._funny_expression == "annoyed":
                # Intense angry fiery crimson red smolder aura
                effective_glow = QColor(239, 68, 68, 240)
            elif self._funny_expression == "love":
                # Warm blooming romantic rose-pink
                effective_glow = QColor(244, 63, 94, 230)
            elif self._funny_expression == "wink":
                # Electric celebratory sky-cyan
                effective_glow = QColor(56, 189, 248, 225)
            elif self._funny_expression == "derp":
                # Cosmic cartoon purple
                effective_glow = QColor(168, 85, 247, 225)
            else:
                effective_glow = self.color_glow

            return self.color_body, self.color_details, effective_eyes, effective_glow
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

        # 1. Back-layer particles (back half of 3D perspective orbiting dizzy stars)
        if self._funny_expression == "derp" and self._orb < 0.5:
            self._paint_orbiting_stars(p, cx, cy + bob, in_front=False)

        # Center with squish and shake
        p.save()
        p.translate(cx + shake_x, cy + bob + shake_y)
        if abs(self._head_tilt) > 0.1:
            p.rotate(self._head_tilt)
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

        # 2. Front-layer particles & procedural overlays (front stars, lightning, hearts, confetti, smoke)
        if self._orb < 0.5:
            self._paint_front_particles(p, cx, cy + bob)

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
        if w <= 86:
            bw = max(40.0, min(w * 0.70, 54.0))
            bh = max(34.0, min(h * 0.60, 46.0))
        else:
            bw = w * 0.78
            bh = h * 0.68
        bx = cx - bw / 2.0
        by = cy - bh / 2.0 + (h * 0.03)
        body_rect = QRectF(bx, by, bw, bh)
        corner_r = bw * 0.36

        # 1. Minimal Body-Contour Emotion Glow (Active ONLY during reactions, tightly hugs squircle body)
        if self._funny_expression:
            p.save()
            p.setBrush(Qt.BrushStyle.NoBrush)
            glow_passes = [
                (4.5, 1.2, 35),
                (3.0, 1.2, 75),
                (1.8, 1.2, 130),
                (0.8, 1.0, 190),
            ]
            for expand, width, alpha in glow_passes:
                col = QColor(glow_c)
                col.setAlpha(alpha)
                p.setPen(QPen(col, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                r = body_rect.adjusted(-expand, -expand, expand, expand)
                cr = corner_r + expand * 0.45
                p.drawRoundedRect(r, cr, cr)
            p.restore()

        # 2. Dynamic Theme Helmet Shell
        shell_grad = QLinearGradient(bx, by, bx, by + bh)
        shell_grad.setColorAt(0.0, body_c)
        bot_c = body_c.darker(118) if body_c.lightness() > 90 else body_c.lighter(130)
        shell_grad.setColorAt(1.0, bot_c)
        if self._funny_expression:
            border_c = QColor(glow_c.red(), glow_c.green(), glow_c.blue(), 140)
        elif body_c.lightness() > 90:
            border_c = QColor(255, 255, 255, 45)
        else:
            border_c = QColor(255, 255, 255, 25)
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

        # Cheek Blush (for Love or shy expressions)
        if self._blush_amount > 0.02:
            blush_w = max(5.0, vw * 0.16)
            blush_h = max(2.5, vh * 0.16)
            blush_y = vy + vh * 0.70
            blush_alpha = int(145 * self._blush_amount)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(244, 63, 94, blush_alpha))
            p.drawEllipse(QPointF(vx + vw * 0.16, blush_y), blush_w, blush_h)
            p.drawEllipse(QPointF(vx + vw * 0.84, blush_y), blush_w, blush_h)

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

        left_shift_x = shift_x + self._left_gaze_offset_x * (visor_w * 0.12)
        left_shift_y = shift_y + self._left_gaze_offset_y * (visor_h * 0.12)
        right_shift_x = shift_x + self._right_gaze_offset_x * (visor_w * 0.12)
        right_shift_y = shift_y + self._right_gaze_offset_y * (visor_h * 0.12)

        left_eye_x = cx - eye_spacing + left_shift_x
        right_eye_x = cx + eye_spacing + right_shift_x
        left_eye_y = eye_center_y + left_shift_y
        right_eye_y = eye_center_y + right_shift_y

        # Joyful Anime Happy Eyes (^ _ ^)
        if self._funny_expression == "love":
            arc_w = max(6.0, eye_w * 1.30)
            arc_h = max(5.0, base_h * 0.70)
            p.setPen(QPen(eyes_c, max(2.2, eye_w * 0.35), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)

            left_arc = QPainterPath()
            left_arc.moveTo(left_eye_x - arc_w / 2.0, left_eye_y + arc_h * 0.30)
            left_arc.quadTo(left_eye_x, left_eye_y - arc_h * 0.65, left_eye_x + arc_w / 2.0, left_eye_y + arc_h * 0.30)
            p.drawPath(left_arc)

            right_arc = QPainterPath()
            right_arc.moveTo(right_eye_x - arc_w / 2.0, right_eye_y + arc_h * 0.30)
            right_arc.quadTo(right_eye_x, right_eye_y - arc_h * 0.65, right_eye_x + arc_w / 2.0, right_eye_y + arc_h * 0.30)
            p.drawPath(right_arc)
            return

        # Soft halo glow behind eyes
        halo_r = max(eye_w, base_h) * (1.75 if self._funny_expression else 1.4)
        glow_alpha = int((105 if self._funny_expression else 55) * pulse)
        for ex, ey in ((left_eye_x, left_eye_y), (right_eye_x, right_eye_y)):
            halo = QRadialGradient(ex, ey, halo_r)
            halo.setColorAt(0.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), glow_alpha))
            halo.setColorAt(0.65, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), int(glow_alpha * 0.3)))
            halo.setColorAt(1.0, QColor(eyes_c.red(), eyes_c.green(), eyes_c.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(ex, ey), halo_r, halo_r)

        # Solid Glowing Pill Eyes
        p.setBrush(eyes_c)
        er = eye_w / 2.0

        # Left eye
        left_eye_rect = QRectF(left_eye_x - er, left_eye_y - eye_h / 2.0, eye_w, eye_h)
        p.drawRoundedRect(left_eye_rect, er, er)
        if blink_factor > 0.6:
            spec_r = max(1.0, eye_w * 0.22)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(left_eye_x - er * 0.3, left_eye_y - eye_h * 0.25), spec_r, spec_r)
            p.setBrush(eyes_c)

        # Right eye (handles normal blink and playful wink)
        right_blink = blink_factor * max(0.12, 1.0 - self._wink_amount * 0.88)
        right_eye_h = max(1.8, base_h * right_blink)
        right_eye_rect = QRectF(right_eye_x - er, right_eye_y - right_eye_h / 2.0, eye_w, right_eye_h)
        p.drawRoundedRect(right_eye_rect, er, min(er, right_eye_h / 2.0))
        if right_blink > 0.6:
            spec_r = max(1.0, eye_w * 0.22)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(right_eye_x - er * 0.3, right_eye_y - right_eye_h * 0.25), spec_r, spec_r)
            p.setBrush(eyes_c)

        # Sharp anime angry eyebrows for annoyed expression
        if self._funny_expression == "annoyed":
            p.setPen(QPen(QColor("#ef4444"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(left_eye_x - er * 0.9, left_eye_y - eye_h * 0.90), QPointF(left_eye_x + er * 0.9, left_eye_y - eye_h * 0.40))
            p.drawLine(QPointF(right_eye_x - er * 0.9, right_eye_y - eye_h * 0.40), QPointF(right_eye_x + er * 0.9, right_eye_y - eye_h * 0.90))

    def _paint_orbiting_stars(self, p: QPainter, cx: float, cy: float, in_front: bool):
        """Paint 3D inclined perspective orbiting cartoon stars (behind or in front of helmet)."""
        p.save()
        theta_base = self._phase * 5.0
        rx = 26.0
        ry = 8.5
        head_y = cy - 16.0  # Orbit centered above the ceramic helmet

        # 3 stars spaced evenly by 120 degrees
        for i in range(3):
            angle = theta_base + (i * 2.0 * math.pi / 3.0)
            sin_val = math.sin(angle)
            cos_val = math.cos(angle)
            is_front = (sin_val >= 0.0)
            if is_front != in_front:
                continue

            star_x = cx + cos_val * rx
            star_y = head_y + sin_val * ry

            # Depth perspective scale (0.70 at far back to 1.15 in front)
            depth = 0.70 + 0.45 * ((sin_val + 1.0) / 2.0)
            r_out = 5.6 * depth
            r_in = 2.4 * depth

            self._draw_star_shape(p, star_x, star_y, r_out, r_in, QColor("#fbbf24"))

            # Tiny spark glow behind each star
            spark_grad = QRadialGradient(star_x, star_y, r_out * 1.5)
            spark_grad.setColorAt(0.0, QColor(254, 240, 138, int(160 * depth)))
            spark_grad.setColorAt(1.0, QColor(254, 240, 138, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(spark_grad)
            p.drawEllipse(QPointF(star_x, star_y), r_out * 1.5, r_out * 1.5)

        p.restore()

    def _paint_front_particles(self, p: QPainter, cx: float, cy: float):
        """Paint front-facing dynamic VFX particles, lightning plasma, confetti, and floating hearts."""
        # 1. Front half of orbiting stars for derp
        if self._funny_expression == "derp":
            self._paint_orbiting_stars(p, cx, cy, in_front=True)

        # 2. Procedural electric lightning plasma arcs for shock
        if self._funny_expression == "shock" and self._lightning_arcs:
            p.save()
            for arc in self._lightning_arcs:
                if len(arc) > 1:
                    path = QPainterPath(arc[0])
                    for pt in arc[1:]:
                        path.lineTo(pt)
                    # Outer electric neon yellow aura
                    p.setPen(QPen(QColor(250, 204, 21, 180), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    p.drawPath(path)
                    # Inner intense white-hot core
                    p.setPen(QPen(QColor(255, 255, 255, 240), 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    p.drawPath(path)
            p.restore()

        # 3. Dynamic active particles
        for p_data in self._particles:
            ptype = p_data.get("type")

            if ptype == "confetti":
                p.save()
                p.translate(p_data["x"], p_data["y"])
                p.rotate(p_data["rot"])
                # 3D tumbling ribbon effect via vertical perspective scale
                scale_y = math.cos(p_data["rot"] * 0.08)
                p.scale(1.0, scale_y)
                alpha = int(255 * min(1.0, max(0.0, p_data["life"] / 0.5)))
                col = QColor(p_data["color"])
                col.setAlpha(alpha)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRect(QRectF(-p_data["w"] / 2.0, -p_data["h"] / 2.0, p_data["w"], p_data["h"]))
                p.restore()

            elif ptype == "smoke":
                rad = p_data["radius"]
                alpha = int(255 * max(0.0, min(1.0, p_data["alpha"])))
                if alpha > 0:
                    grad = QRadialGradient(p_data["x"], p_data["y"], rad)
                    grad.setColorAt(0.0, QColor(220, 220, 230, alpha))
                    grad.setColorAt(0.6, QColor(180, 180, 195, int(alpha * 0.5)))
                    grad.setColorAt(1.0, QColor(140, 140, 160, 0))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(grad)
                    p.drawEllipse(QPointF(p_data["x"], p_data["y"]), rad, rad)

            elif ptype == "heart":
                alpha = max(0.0, min(1.0, p_data["alpha"]))
                if alpha > 0.01:
                    self._draw_heart_shape(p, p_data["x"], p_data["y"], p_data["size"], p_data["color"], alpha)

            elif ptype == "ember":
                alpha = int(255 * max(0.0, min(1.0, p_data["alpha"])))
                if alpha > 0:
                    p.save()
                    c = QColor(p_data["color"])
                    c.setAlpha(alpha)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(c)
                    p.drawEllipse(QPointF(p_data["x"], p_data["y"]), p_data["radius"], p_data["radius"])
                    p.restore()

        # 4. Annoyed: Pulsing anime anger vein symbols (💢) popping at the temple
        if self._funny_expression == "annoyed":
            bw = max(40.0, min(self.width() * 0.70, 54.0))
            bh = max(34.0, min(self.height() * 0.60, 46.0))
            bx = cx - bw / 2.0
            by = cy - bh / 2.0 + (self.height() * 0.03)

            # Rapid irritated pulse
            vein_pulse = 1.0 + 0.22 * math.sin(self._phase * 18.0)
            self._draw_anger_vein_symbol(p, bx + bw * 0.86, by + 4.0, 7.5 * vein_pulse, alpha=1.0)

            # Smaller secondary angry pop mark
            vein_pulse_sub = 1.0 + 0.18 * math.cos(self._phase * 14.0)
            self._draw_anger_vein_symbol(p, bx + bw * 0.96, by + 13.0, 5.0 * vein_pulse_sub, alpha=0.85)

    def _draw_anger_vein_symbol(self, p: QPainter, cx: float, cy: float, size: float, alpha: float):
        """Draw iconic comic / anime anger vein symbol (💢) centered at (cx, cy)."""
        p.save()
        p.translate(cx, cy)

        # Glow halo behind the anger vein
        glow = QRadialGradient(0, 0, size * 1.6)
        glow.setColorAt(0.0, QColor(239, 68, 68, int(180 * alpha)))
        glow.setColorAt(0.7, QColor(220, 38, 38, int(70 * alpha)))
        glow.setColorAt(1.0, QColor(220, 38, 38, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), size * 1.6, size * 1.6)

        r = size
        pen_w = max(1.4, size * 0.26)
        vein_color = QColor("#f87171")  # Bright crimson red
        vein_color.setAlpha(int(255 * alpha))
        p.setPen(QPen(vein_color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # 4 outward-curved arcs forming 💢
        # Top arc
        path_ht = QPainterPath()
        path_ht.moveTo(-r, -r * 0.35)
        path_ht.quadTo(0, -r * 0.85, r, -r * 0.35)
        p.drawPath(path_ht)

        # Bottom arc
        path_hb = QPainterPath()
        path_hb.moveTo(-r, r * 0.35)
        path_hb.quadTo(0, r * 0.85, r, r * 0.35)
        p.drawPath(path_hb)

        # Vertical left arc
        path_vl = QPainterPath()
        path_vl.moveTo(-r * 0.35, -r)
        path_vl.quadTo(-r * 0.85, 0, -r * 0.35, r)
        p.drawPath(path_vl)

        # Vertical right arc
        path_vr = QPainterPath()
        path_vr.moveTo(r * 0.35, -r)
        path_vr.quadTo(r * 0.85, 0, r * 0.35, r)
        p.drawPath(path_vr)

        p.restore()

    def _draw_star_shape(self, p: QPainter, cx: float, cy: float, r_out: float, r_in: float, color: QColor):
        """Draw a 5-pointed star centered at (cx, cy)."""
        path = QPainterPath()
        pts = 5
        angle_step = math.pi / pts
        curr_angle = -math.pi / 2.0
        for i in range(pts * 2):
            r = r_out if i % 2 == 0 else r_in
            px = cx + math.cos(curr_angle) * r
            py = cy + math.sin(curr_angle) * r
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
            curr_angle += angle_step
        path.closeSubpath()
        p.setPen(QPen(QColor(255, 255, 255, 180), 0.8))
        p.setBrush(color)
        p.drawPath(path)

    def _draw_heart_shape(self, p: QPainter, cx: float, cy: float, size: float, color: QColor, alpha: float):
        """Draw a smooth cubic bezier heart centered at (cx, cy)."""
        p.save()
        p.translate(cx, cy)
        s = size / 16.0
        p.scale(s, s)
        path = QPainterPath()
        path.moveTo(0, 2)
        path.cubicTo(-5, -6, -10, 0, 0, 9)
        path.cubicTo(10, 0, 5, -6, 0, 2)
        c = QColor(color)
        c.setAlpha(int(255 * alpha))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawPath(path)
        p.restore()

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
        dia = min(self.width(), self.height()) * 0.90
        radius = dia / 2.0

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
