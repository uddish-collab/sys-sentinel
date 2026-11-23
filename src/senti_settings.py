"""Settings management for Sentinel using QSettings."""

import sys
import os
from typing import Dict, Optional
from PySide6.QtCore import QSettings, QPoint
from PySide6.QtGui import QColor, QGuiApplication

try:
    import winreg
except ImportError:
    winreg = None


DEFAULT_COLORS: Dict[str, str] = {
    "body": "#f4f1ea",       # Pearl white
    "details": "#14213d",    # Midnight blue
    "eyes": "#00e5ff",       # Electric cyan
    "glow": "#00e5ff",       # Electric cyan
}

PRESET_THEMES: Dict[str, Dict[str, str]] = {
    "Cyberpunk Cyan": {
        "body": "#f4f1ea",
        "details": "#14213d",
        "eyes": "#00e5ff",
        "glow": "#00e5ff",
    },
    "Stealth Obsidian": {
        "body": "#181b22",
        "details": "#07080a",
        "eyes": "#00e5ff",
        "glow": "#00e5ff",
    },
    "Matrix Emerald": {
        "body": "#121a14",
        "details": "#060e08",
        "eyes": "#22c55e",
        "glow": "#10b981",
    },
    "Solar Amber": {
        "body": "#201712",
        "details": "#0c0805",
        "eyes": "#f5a524",
        "glow": "#ff7a00",
    },
    "Synthwave Neon": {
        "body": "#1a1226",
        "details": "#0c0614",
        "eyes": "#f43f5e",
        "glow": "#a855f7",
    },
}


class SentiSettings:
    """Encapsulates QSettings for Sentinel."""

    def __init__(self):
        self._settings = QSettings("Sentinel", "SENTI")

    def get_color(self, name: str) -> QColor:
        hex_val = str(self._settings.value(f"colors/{name}", DEFAULT_COLORS.get(name, "#ffffff")))
        return QColor(hex_val)

    def set_color(self, name: str, color: QColor):
        self._settings.setValue(f"colors/{name}", color.name())

    def reset_colors(self):
        for key, val in DEFAULT_COLORS.items():
            self._settings.setValue(f"colors/{key}", val)

    def apply_preset_theme(self, theme_name: str) -> bool:
        if theme_name in PRESET_THEMES:
            for key, val in PRESET_THEMES[theme_name].items():
                self._settings.setValue(f"colors/{key}", val)
            return True
        return False

    def is_sound_enabled(self) -> bool:
        val = self._settings.value("sound/enabled", True)
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

    def is_autostart_enabled(self) -> bool:
        if winreg is None:
            return False
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "Sentinel"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, app_name)
                return bool(val)
        except Exception:
            return False

    def set_autostart_enabled(self, enabled: bool) -> bool:
        if winreg is None:
            return False
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "Sentinel"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    if getattr(sys, "frozen", False):
                        exe_path = f'"{sys.executable}"'
                    else:
                        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "senti_app.py"))
                        exe_path = f'"{sys.executable}" "{main_py}"'
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
            return True
        except Exception:
            return False

    def sync(self):
        self._settings.sync()


def get_start_menu_shortcut_path() -> str:
    """Return the absolute path to the Start Menu shortcut for SYS-SENTINEL."""
    app_data = os.environ.get("APPDATA", "")
    if not app_data:
        return ""
    return os.path.join(app_data, "Microsoft", "Windows", "Start Menu", "Programs", "SYS-SENTINEL.lnk")


def is_windows_app_registered() -> bool:
    """Check if SYS-SENTINEL is registered in Windows Add/Remove Programs and Start Menu."""
    if winreg is None:
        return False
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SYS-SENTINEL"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "DisplayName")
            return bool(val)
    except Exception:
        return False


def register_windows_app(version: str = "1.0.0") -> bool:
    """Register SYS-SENTINEL in Windows Start Menu and Add/Remove Programs (Uninstall registry)."""
    if winreg is None:
        return False

    exe_path = os.path.abspath(sys.executable)

    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SYS-SENTINEL"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "SYS-SENTINEL")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Uddish")
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
            if getattr(sys, "frozen", False):
                uninst_cmd = f'"{exe_path}" --uninstall'
            else:
                main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "senti_app.py"))
                uninst_cmd = f'"{exe_path}" "{main_py}" --uninstall'
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninst_cmd)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, os.path.dirname(exe_path))
            winreg.SetValueEx(key, "HelpLink", 0, winreg.REG_SZ, "https://github.com/uddish-collab/sys-sentinel")
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)

        # Create Start Menu shortcut so Windows Search lists it as an installed app with full tile
        shortcut_path = get_start_menu_shortcut_path()
        if shortcut_path and os.path.exists(os.path.dirname(shortcut_path)):
            escaped_shortcut = shortcut_path.replace("'", "''")
            escaped_exe = exe_path.replace("'", "''")
            escaped_dir = os.path.dirname(exe_path).replace("'", "''")
            import subprocess
            if getattr(sys, "frozen", False):
                ps_script = (
                    f"$ws = New-Object -ComObject WScript.Shell; "
                    f"$s = $ws.CreateShortcut('{escaped_shortcut}'); "
                    f"$s.TargetPath = '{escaped_exe}'; "
                    f"$s.WorkingDirectory = '{escaped_dir}'; "
                    f"$s.Save()"
                )
            else:
                main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "senti_app.py")).replace("'", "''")
                ps_script = (
                    f"$ws = New-Object -ComObject WScript.Shell; "
                    f"$s = $ws.CreateShortcut('{escaped_shortcut}'); "
                    f"$s.TargetPath = '{escaped_exe}'; "
                    f"$s.Arguments = '\"{main_py}\"'; "
                    f"$s.WorkingDirectory = '{escaped_dir}'; "
                    f"$s.Save()"
                )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5,
            )
        return True
    except Exception:
        return False


def unregister_windows_app() -> bool:
    """Remove SYS-SENTINEL from Windows Start Menu and Add/Remove Programs."""
    success = True
    if winreg is not None:
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SYS-SENTINEL"
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path)
        except FileNotFoundError:
            pass
        except Exception:
            success = False

    shortcut_path = get_start_menu_shortcut_path()
    if shortcut_path and os.path.exists(shortcut_path):
        try:
            os.remove(shortcut_path)
        except Exception:
            success = False

    return success


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
