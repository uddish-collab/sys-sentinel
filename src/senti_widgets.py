"""Shared UI components and animated progress bars for Sentinel."""

from typing import Optional
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import QWidget


class SmoothBar(QWidget):
    """Modern progress bar with smoothed animation and status-driven colors."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setMinimumWidth(80)

        self._current_value: float = 0.0
        self._target_value: float = 0.0
        self._status: str = "NORMAL"

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)  # ~60 fps
        self._anim_timer.timeout.connect(self._step_animation)

    def set_value(self, value: Optional[float], status: str = "NORMAL"):
        self._status = status
        if value is None:
            self._target_value = 0.0
            self._current_value = 0.0
        else:
            val = max(0.0, min(100.0, float(value)))
            if self._current_value == 0.0:
                self._current_value = val
            self._target_value = val

        if not self._anim_timer.isActive() and abs(self._target_value - self._current_value) > 0.2:
            self._anim_timer.start()
        self.update()

    def _step_animation(self):
        diff = self._target_value - self._current_value
        if abs(diff) < 0.2:
            self._current_value = self._target_value
            self._anim_timer.stop()
        else:
            self._current_value += diff * 0.38
        self.update()

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect = self.rect()
            h = rect.height()
            radius = h / 2.0

            # Background track
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#152038"))
            p.drawRoundedRect(rect, radius, radius)

            # Bar fill
            if self._current_value > 0.0:
                fill_w = (rect.width() * self._current_value) / 100.0
                fill_w = max(fill_w, h)  # Ensure rounded ends render well
                fill_rect = QRectF(rect.x(), rect.y(), fill_w, h)

                # Determine colors based on status
                if self._status == "CRITICAL":
                    c1, c2 = QColor("#ff3b4a"), QColor("#ff6b78")
                elif self._status == "WARNING":
                    c1, c2 = QColor("#ffb020"), QColor("#ffd060")
                elif self._status in ("UNAVAILABLE", "CHECKING"):
                    c1, c2 = QColor("#4a5870"), QColor("#687894")
                else:
                    c1, c2 = QColor("#00bcd4"), QColor("#00e5ff")

                grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
                grad.setColorAt(0.0, c1)
                grad.setColorAt(1.0, c2)

                p.setBrush(grad)
                p.drawRoundedRect(fill_rect, radius, radius)
        finally:
            p.end()
