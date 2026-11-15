"""Shared UI components, theme styling, animated bars, switches, and transition helpers."""

from typing import Optional, Callable
from PySide6.QtCore import (
    Qt,
    QTimer,
    QRectF,
    Property,
    Signal,
    QEasingCurve,
    QPropertyAnimation,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QBrush,
    QPen,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsOpacityEffect,
)


DARK_THEME_QSS = """
QWidget#hudRoot, QWidget#controlRoot {
    background-color: #0b1020;
    border: 1px solid #1f2f4d;
    border-radius: 12px;
}

QTabWidget::pane {
    border: 1px solid #1f2f4d;
    border-radius: 8px;
    background: #0b1020;
    top: -1px;
}

QTabBar::tab {
    background: #10192e;
    color: #8c9dbd;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #1a2742;
    border-bottom: none;
    font-size: 13px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #172647;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-bottom: 1px solid #172647;
}

QTabBar::tab:hover:!selected {
    background: #142038;
    color: #cdd9ed;
}

QFrame.card {
    background-color: #111a30;
    border: 1px solid #1c2b4a;
    border-radius: 10px;
}

QPushButton.actionButton {
    background-color: #15223d;
    color: #eef4fc;
    border: 1px solid #283e66;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.actionButton:hover {
    background-color: #1b2d52;
    border-color: #00e5ff;
    color: #ffffff;
}

QPushButton.actionButton:pressed {
    background-color: #121e36;
}

QPushButton.closeButton {
    background-color: transparent;
    color: #8c9dbd;
    border: none;
    font-size: 16px;
    font-weight: bold;
    padding: 2px 6px;
}

QPushButton.closeButton:hover {
    color: #ff3b4a;
}

/* Notice: NO border-radius on QMenu to avoid Windows corner artifacts */
QMenu {
    background-color: #10192e;
    color: #eef4fc;
    border: 1px solid #283e66;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #1b2d52;
    color: #00e5ff;
}

QMenu::separator {
    height: 1px;
    background: #223354;
    margin: 4px 8px;
}
"""


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
            self._current_value += diff * 0.18
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


class ToggleSwitch(QWidget):
    """Animated iOS/Material-style toggle switch with smooth knob translation."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(46, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._checked = checked
        self._knob_pos = 1.0 if checked else 0.0

        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def get_knob_pos(self) -> float:
        return self._knob_pos

    def set_knob_pos(self, pos: float):
        self._knob_pos = pos
        self.update()

    knob_pos = Property(float, get_knob_pos, set_knob_pos)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._anim.stop()
            self._anim.setStartValue(self._knob_pos)
            self._anim.setEndValue(1.0 if checked else 0.0)
            self._anim.start()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            w, h = self.width(), self.height()
            radius = h / 2.0

            # Background track: blend from inactive #1c2b4a to active #00e5ff
            inactive_color = QColor("#1c2b4a")
            active_color = QColor("#0090a8")
            r = int(inactive_color.red() + (active_color.red() - inactive_color.red()) * self._knob_pos)
            g = int(inactive_color.green() + (active_color.green() - inactive_color.green()) * self._knob_pos)
            b = int(inactive_color.blue() + (active_color.blue() - inactive_color.blue()) * self._knob_pos)
            track_color = QColor(r, g, b)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(track_color)
            p.drawRoundedRect(0, 0, w, h, radius, radius)

            # Knob: white circle moving from left to right
            knob_margin = 3
            knob_dia = h - (knob_margin * 2)
            travel_distance = w - knob_dia - (knob_margin * 2)
            knob_x = knob_margin + (travel_distance * self._knob_pos)
            knob_y = knob_margin

            # Knob shadow / base
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QRectF(knob_x, knob_y, knob_dia, knob_dia))
        finally:
            p.end()


def animate_opacity(
    widget: QWidget,
    start: float,
    end: float,
    duration: int = 200,
    on_finished: Optional[Callable[[], None]] = None,
) -> QPropertyAnimation:
    """Fade a widget in or out smoothly using QGraphicsOpacityEffect."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    effect.setOpacity(start)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    if on_finished is not None:
        anim.finished.connect(on_finished)

    anim.start()
    return anim
