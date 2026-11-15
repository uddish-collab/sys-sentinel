"""Global keyboard shortcut manager for Windows using RegisterHotKey.

Allows performing SENTI companion actions system-wide even when the window
does not accept or hold keyboard focus.
"""

import sys
from typing import Dict, Callable, Optional

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
else:
    user32 = None  # type: ignore

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication


# Windows API constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


class WindowsHotKeyFilter(QAbstractNativeEventFilter):
    """Intercepts WM_HOTKEY Windows messages and executes associated actions."""

    def __init__(self, callbacks: Dict[int, Callable[[], None]]):
        super().__init__()
        self.callbacks = callbacks

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG") and message:
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    hotkey_id = msg.wParam
                    if hotkey_id in self.callbacks:
                        # Invoke callback safely
                        self.callbacks[hotkey_id]()
                        return True, 0
            except Exception:
                pass
        return False, 0


class GlobalHotKeyManager:
    """Registers and manages global hotkeys for the SYS-SENTINEL desktop companion."""

    def __init__(self):
        self._callbacks: Dict[int, Callable[[], None]] = {}
        self._filter: Optional[WindowsHotKeyFilter] = None
        self._next_id = 100
        self._registered_ids = []

    def register_hotkey(
        self,
        modifiers: int,
        vk_code: int,
        callback: Callable[[], None],
    ) -> Optional[int]:
        """Register a global hotkey with Windows."""
        if not user32:
            return None

        hotkey_id = self._next_id
        self._next_id += 1

        # Use MOD_NOREPEAT to prevent auto-repeating on key hold
        success = user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, vk_code)
        if success:
            self._callbacks[hotkey_id] = callback
            self._registered_ids.append(hotkey_id)
            return hotkey_id
        return None

    def start(self, app: QApplication):
        """Install native event filter on the QApplication."""
        if user32 and not self._filter:
            self._filter = WindowsHotKeyFilter(self._callbacks)
            app.installNativeEventFilter(self._filter)

    def unregister_all(self):
        """Cleanly unregister all hotkeys from Windows."""
        if user32:
            for hid in self._registered_ids:
                try:
                    user32.UnregisterHotKey(None, hid)
                except Exception:
                    pass
            self._registered_ids.clear()
            self._callbacks.clear()
