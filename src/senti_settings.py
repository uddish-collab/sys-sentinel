"""Settings management for SYS-SENTINEL using QSettings."""

from typing import Dict, Any, Optional
from PySide6.QtCore import QSettings, QPoint
from PySide6.QtGui import QColor, QGuiApplication


DEFAULT_COLORS: Dict[str, str] = {
    "body": "#f4f1ea",       # Pearl white
    "details": "#14213d",    # Midnight blue
    "eyes": "#00e5ff",       # Electric cyan
    "glow": "#00e5ff",       # Electric cyan
}


class SentiSettings:
    """Encapsulates QSettings for SYS-SENTINEL."""

    def __init__(self):
        self._settings = QSettings("SYS-SENTINEL", "SENTI")

    def get_color(self, name: str) -> QColor:
        hex_val = str(self._settings.value(f"colors/{name}", DEFAULT_COLORS.get(name, "#ffffff")))
        return QColor(hex_val)

    def set_color(self, name: str, color: QColor):
        self._settings.setValue(f"colors/{name}", color.name())

    def reset_colors(self):
        for key, val in DEFAULT_COLORS.items():
            self._settings.setValue(f"colors/{key}", val)

    def is_sound_enabled(self) -> bool:
        val = self._settings.value("sound/enabled", False)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    def set_sound_enabled(self, enabled: bool):
        self._settings.setValue("sound/enabled", bool(enabled))

    def get_window_pos(self) -> Optional[QPoint]:
        x = self._settings.value("window/x", None)
        y = self._settings.value("window/y", None)
        if x is not None and y is not None:
            try:
                return QPoint(int(x), int(y))
            except (ValueError, TypeError):
                return None
        return None

    def set_window_pos(self, pos: QPoint):
        self._settings.setValue("window/x", int(pos.x()))
        self._settings.setValue("window/y", int(pos.y()))

    def get_orb_state(self) -> bool:
        val = self._settings.value("window/is_orb", False)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    def set_orb_state(self, is_orb: bool):
        self._settings.setValue("window/is_orb", bool(is_orb))

    def get_docked_state(self) -> bool:
        val = self._settings.value("island/is_docked", True)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    def set_docked_state(self, docked: bool):
        self._settings.setValue("island/is_docked", bool(docked))

    def get_island_pos(self) -> Optional[QPoint]:
        x = self._settings.value("island/x", None)
        y = self._settings.value("island/y", None)
        if x is not None and y is not None:
            try:
                return QPoint(int(x), int(y))
            except (ValueError, TypeError):
                return None
        return None

    def set_island_pos(self, pos: QPoint):
        self._settings.setValue("island/x", int(pos.x()))
        self._settings.setValue("island/y", int(pos.y()))


def get_default_island_pos(island_w: int, island_h: int = 52) -> QPoint:
    """Return top center position on primary screen."""
    screens = QGuiApplication.screens()
    if not screens:
        return QPoint(200, 10)
    primary = QGuiApplication.primaryScreen()
    geo = primary.availableGeometry()
    x = geo.left() + int((geo.width() - island_w) / 2)
    y = geo.top() + 10
    return QPoint(x, y)


def get_safe_initial_pos(saved_pos: Optional[QPoint], width: int, height: int) -> QPoint:
    """Return saved_pos if it's within a visible screen, else bottom-right of primary screen."""
    screens = QGuiApplication.screens()
    if not screens:
        return QPoint(100, 100)

    primary = QGuiApplication.primaryScreen()
    primary_geo = primary.availableGeometry()

    if saved_pos is not None:
        # Check if at least partially on any screen
        point_visible = False
        for s in screens:
            if s.geometry().contains(saved_pos):
                point_visible = True
                break
        if point_visible:
            return saved_pos

    # Fallback: bottom-right with margin
    margin = 30
    x = primary_geo.right() - width - margin
    y = primary_geo.bottom() - height - margin
    return QPoint(max(primary_geo.left(), x), max(primary_geo.top(), y))
