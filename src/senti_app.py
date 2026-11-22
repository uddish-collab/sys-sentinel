"""Sentinel Desktop Companion and System Tray Controller.

Polished Windows 10/11 desktop companion featuring the animated SENTI mascot,
minimalist black glass top island, startup greeting wave, and multi-click gestures.
"""

import math
import os
import random
import signal
import sys
import tempfile
from typing import Optional, Dict

# Ensure src/ directory is available on sys.path
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from PySide6.QtCore import (
    Qt,
    QPoint,
    QRect,
    QTimer,
    QLockFile,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
)
from PySide6.QtGui import (
    QAction,
    QGuiApplication,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QMenu,
    QSystemTrayIcon,
    QMessageBox,
    QGraphicsOpacityEffect,
)

from system_monitor import (
    get_system_info,
    get_temperature_monitor,
    get_gpu_monitor,
)
from senti_state import (
    StateTracker,
    MetricHistory,
)
from senti_settings import (
    SentiSettings,
    get_safe_initial_pos,
    get_default_island_pos,
)
from senti_sound import play_sound, play_pill_hover, play_pill_tick, ensure_sound_files
from senti_mascot import SentiMascot, render_mascot_image
from senti_control import SentiControlWindow
from senti_dashboard import SentiDashboardWindow
from senti_island import TopIslandWindow, TAB_CANONICAL, PILL_HIT_INDEX

NORMAL_SIZE = 80      # Senti companion size (leaves room for aura & waving glove)
DOCKED_SIZE = 80      # Nests in Card 1 with center cx: 78, cy: 92
ORB_SIZE = 44         # Minimalist orb form
DRAG_THRESHOLD = 5


class CompanionWindow(QWidget):
    """The floating desktop companion window hosting SENTI."""

    def __init__(
        self,
        app_controller: "SentiApp",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.app_controller = app_controller
        self.settings = app_controller.settings

        # Windows Tool window attributes: Frameless, Always on Top, Never steals keyboard focus
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Ensure native platform window handle is instantiated
        self.winId()

        # Mascot widget
        self.mascot = SentiMascot(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.mascot)

        # Dragging state
        self._is_dragging = False
        self._press_pos = QPoint()
        self._window_start_pos = QPoint()

        # Multi-click dispatcher (1 = Hide/Disappear, 2 = Return to Island)
        self._click_count = 0
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self._dispatch_clicks)

        # Orb / Docked state
        self.is_orb = self.settings.get_orb_state()
        self.is_docked = self.settings.get_docked_state()

        # Set initial dimensions based on docked/orb state
        if self.is_orb:
            init_size = ORB_SIZE
            self.mascot.set_orb(1.0)
        elif self.is_docked:
            init_size = DOCKED_SIZE
            self.mascot.set_orb(0.0)
        else:
            init_size = NORMAL_SIZE
            self.mascot.set_orb(0.0)

        self.resize(init_size, init_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Opacity animation for hide/show (instant, fluid)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(70)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Motion animation
        self._motion_group: Optional[QParallelAnimationGroup] = None

        self.apply_palette()

    def is_on_senti(self, pos: QPoint) -> bool:
        """Precision hit-testing so only SENTI's body/head/antenna is draggable,
        not the empty transparent corners of the window bounding box.
        """
        if self.is_docked:
            return True

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        if self.is_orb:
            r = min(w, h) * 0.44
            dx = pos.x() - cx
            dy = pos.y() - cy
            return (dx * dx + dy * dy) <= (r * r)

        # Option D: Visor Astronaut squircle helmet hit-testing
        bw = w * 0.84
        bh = h * 0.74
        bx = cx - bw / 2.0
        by = cy - bh / 2.0 + (h * 0.04)

        # Check if inside bounding rectangle first
        if not (bx <= pos.x() <= bx + bw and by <= pos.y() <= by + bh):
            return False

        # Elliptical / squircle corner falloff
        rx = bw / 2.0
        ry = bh / 2.0
        head_cx = cx
        head_cy = by + ry
        if rx > 0 and ry > 0:
            norm_x = abs(pos.x() - head_cx) / rx
            norm_y = abs(pos.y() - head_cy) / ry
            # Squircle exponent 2.8 (softer than rect, rounder than circle)
            return (norm_x ** 2.8 + norm_y ** 2.8) <= 1.0

        return False

    def apply_palette(self):
        """Update mascot colors from settings."""
        self.mascot.set_palette_colors(
            self.settings.get_color("body"),
            self.settings.get_color("details"),
            self.settings.get_color("eyes"),
            self.settings.get_color("glow"),
        )

    def set_system_mood(self, mood: str):
        self.mascot.set_mood(mood)

    # --- Mouse Interaction & Dragging ---

    def mousePressEvent(self, event):
        if not self.is_on_senti(event.pos()):
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._window_start_pos = self.pos()
            self._is_dragging = False
            self.mascot.trigger_squish()
            self.app_controller.play("click")
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()
            self._click_count = 0
            self.mascot.trigger_squish()
            self.app_controller.play("click")
            # 2 Clicks (Double tap): Return to Island
            if not self.is_docked:
                self.app_controller.return_to_island()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            curr_pos = event.globalPosition().toPoint()
            delta = curr_pos - self._press_pos
            if not self._is_dragging and delta.manhattanLength() > DRAG_THRESHOLD:
                self._is_dragging = True

            if self._is_dragging:
                new_pos = self._window_start_pos + delta
                self.move(new_pos)

                # Check if dragged out of the island!
                if self.is_docked:
                    dock_pos = self.app_controller.island.get_dock_target_pos(self.width())
                    dist = (new_pos - dock_pos).manhattanLength()
                    if dist > 24:
                        self.app_controller.undock_from_island()

                if not self.is_docked:
                    self.settings.set_window_pos(new_pos)

                event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                if self.is_docked:
                    # Inside island: Trigger funny expression with matching authentic sound!
                    sound_name = self.mascot.trigger_funny_expression()
                    if sound_name and self.app_controller:
                        self.app_controller.play(sound_name)
                else:
                    self._click_count += 1
                    if self._click_count >= 2:
                        self._click_timer.stop()
                        self._click_count = 0
                        self.app_controller.return_to_island()
                    else:
                        self._click_timer.start(220)
            self._is_dragging = False
            event.accept()

    def _dispatch_clicks(self):
        count = self._click_count
        self._click_count = 0

        if count == 1:
            # 1 Click (Single tap): Disappear
            self.fade_hide()
        elif count >= 2:
            if not self.is_docked:
                self.app_controller.return_to_island()

    # --- Shrink / Restore Morphing (Orb) ---

    def shrink_to_orb(self):
        if self.is_orb:
            return
        self.is_orb = True
        self.settings.set_orb_state(True)
        self.app_controller.play("shrink")
        self._animate_orb_morph(target_size=ORB_SIZE, target_orb_prop=1.0)

    def restore_from_orb(self):
        if not self.is_orb:
            return
        self.is_orb = False
        self.settings.set_orb_state(False)
        self.app_controller.play("restore")
        target_size = DOCKED_SIZE if self.is_docked else NORMAL_SIZE
        self._animate_orb_morph(target_size=target_size, target_orb_prop=0.0)

    def toggle_orb(self):
        if self.is_orb:
            self.restore_from_orb()
        else:
            self.shrink_to_orb()

    def _animate_orb_morph(self, target_size: int, target_orb_prop: float):
        """Morph window geometry around the same center point, clamped to screen."""
        if self._motion_group and self._motion_group.state() == QPropertyAnimation.State.Running:
            self._motion_group.stop()

        curr_geo = self.geometry()
        center = curr_geo.center()

        new_x = int(center.x() - target_size / 2)
        new_y = int(center.y() - target_size / 2)

        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        new_x = max(screen_geo.left(), min(screen_geo.right() - target_size, new_x))
        new_y = max(screen_geo.top(), min(screen_geo.bottom() - target_size, new_y))
        target_geo = QRect(new_x, new_y, target_size, target_size)

        self._motion_group = QParallelAnimationGroup(self)

        geom_anim = QPropertyAnimation(self, b"geometry", self)
        geom_anim.setDuration(130)
        geom_anim.setStartValue(curr_geo)
        geom_anim.setEndValue(target_geo)
        geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        orb_anim = QPropertyAnimation(self.mascot, b"orb", self)
        orb_anim.setDuration(130)
        orb_anim.setStartValue(self.mascot.get_orb())
        orb_anim.setEndValue(target_orb_prop)
        orb_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._motion_group.addAnimation(geom_anim)
        self._motion_group.addAnimation(orb_anim)
        self._motion_group.start()

    # --- Glide Animation (for smooth return to island) ---

    def glide_to_rect(
        self,
        target_geo: QRect,
        duration: int = 150,
        easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
        on_finished: Optional[Callable[[], None]] = None,
    ):
        if self._motion_group and self._motion_group.state() == QPropertyAnimation.State.Running:
            self._motion_group.stop()

        self._motion_group = QParallelAnimationGroup(self)

        geom_anim = QPropertyAnimation(self, b"geometry", self)
        geom_anim.setDuration(duration)
        geom_anim.setStartValue(self.geometry())
        geom_anim.setEndValue(target_geo)
        geom_anim.setEasingCurve(easing_curve)

        self._motion_group.addAnimation(geom_anim)

        if on_finished:
            self._motion_group.finished.connect(on_finished)
        self._motion_group.start()

    # --- Hide / Show Fade ---

    def fade_show(self):
        self.show()
        self.raise_()
        self.app_controller.play("show")
        if hasattr(self.app_controller, "act_tray_toggle"):
            self.app_controller.act_tray_toggle.setText("Hide SENTI")
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_hide(self):
        self.app_controller.play("hide")
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)

        def _on_done():
            self.hide()
            try:
                self._fade_anim.finished.disconnect(_on_done)
            except Exception:
                pass
            if hasattr(self.app_controller, "act_tray_toggle"):
                self.app_controller.act_tray_toggle.setText("Show SENTI")

        self._fade_anim.finished.connect(_on_done)
        self._fade_anim.start()

    # --- Context Menu ---

    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)

        # Return to Island (if undocked, double-click)
        if not self.is_docked:
            act_dock = QAction("Return to Island (Double-click)", self)
            act_dock.triggered.connect(self.app_controller.return_to_island)
            menu.addAction(act_dock)

        # Orb Toggle
        act_orb = QAction("Restore SENTI" if self.is_orb else "Shrink to Orb", self)
        act_orb.triggered.connect(self.toggle_orb)
        menu.addAction(act_orb)

        # Dedicated Dashboard
        act_dash = QAction("Telemetry Dashboard", self)
        act_dash.triggered.connect(lambda: self.app_controller.open_dashboard_tab("CPU"))
        menu.addAction(act_dash)

        # Settings window
        act_control = QAction("Settings", self)
        act_control.triggered.connect(self.app_controller.open_control_window)
        menu.addAction(act_control)

        # Hide
        act_hide = QAction("Hide SENTI (Single-click)", self)
        act_hide.triggered.connect(self.fade_hide)
        menu.addAction(act_hide)

        menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.app_controller.quit_app)
        menu.addAction(act_quit)

        menu.exec(global_pos)


class SentiApp:
    """Master controller managing companion, island, HUD, control window, tray, and telemetry loop."""

    def __init__(self):
        self.settings = SentiSettings()
        self.state_tracker = StateTracker()

        # Rolling metric histories (900 samples, ~15 mins)
        self.history_map: Dict[str, MetricHistory] = {
            "cpu": MetricHistory(maxlen=900),
            "ram": MetricHistory(maxlen=900),
            "disk": MetricHistory(maxlen=900),
            "temperature_c": MetricHistory(maxlen=900),
        }

        # Ensure audio tones exist
        ensure_sound_files()

        # Warm up background telemetry daemons off-thread
        get_gpu_monitor()
        get_temperature_monitor()

        # 1. Create Minimalist Solid Dark Top Island
        self.island = TopIslandWindow(
            on_drag_moved=self._on_island_drag_moved,
            on_refresh=self._on_manual_refresh,
            on_toggle_sound=self.toggle_sound,
            is_sound_enabled_getter=lambda: self.settings.is_sound_enabled(),
            on_open_tab=self.open_dashboard_tab,
            on_pill_hover=self._on_island_pill_hover,
        )
        # Position island at top desktop center on launch
        island_pos = get_default_island_pos(self.island.width(), self.island.height())
        self.island.move(island_pos)
        self.settings.set_island_pos(island_pos)

        # 2. Create Companion Window
        self.companion = CompanionWindow(self)
        self.companion.is_docked = True
        self.settings.set_docked_state(True)

        # 4. Create Dedicated Subsystem Telemetry Dashboard (includes Settings panel)
        self.dashboard = SentiDashboardWindow(
            settings=self.settings,
            on_colors_changed=self.on_palette_changed,
            on_sound_toggled=self.on_sound_toggled,
        )
        self.dashboard.closed.connect(self._on_dashboard_closed)

        # 6. Create Control / Settings Window
        self.control_win = SentiControlWindow(self.settings, self.history_map)
        self.control_win.colors_changed.connect(self.on_palette_changed)
        self.control_win.sound_toggled.connect(self.on_sound_toggled)

        # 5. System Tray Icon
        self._init_tray()

        # Track previous mood to trigger audio transitions
        self._prev_mood: str = "calm"

        # 6. Polling Timer (1 second interval)
        self.poll_timer = QTimer()
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.poll_telemetry)

    def _init_tray(self):
        tray_img = render_mascot_image(size=64, is_orb=True)
        pixmap = QPixmap.fromImage(tray_img)
        icon = QIcon(pixmap)

        self.tray = QSystemTrayIcon(self.companion)
        self.tray.setIcon(icon)

        menu = QMenu()
        self.act_tray_toggle = QAction("Hide SENTI", menu)
        self.act_tray_toggle.triggered.connect(self.toggle_companion_visibility)
        menu.addAction(self.act_tray_toggle)

        act_island = QAction("Return to Top Island", menu)
        act_island.triggered.connect(self.return_to_island)
        menu.addAction(act_island)

        act_dash = QAction("Telemetry Dashboard", menu)
        act_dash.triggered.connect(lambda: self.open_dashboard_tab("CPU"))
        menu.addAction(act_dash)

        act_control = QAction("Settings", menu)
        act_control.triggered.connect(self.open_control_window)
        menu.addAction(act_control)

        menu.addSeparator()

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_companion_visibility()

    def toggle_companion_visibility(self):
        if self.companion.isVisible():
            self.companion.fade_hide()
            if self.companion.is_docked:
                self.island.fade_out()
            self.act_tray_toggle.setText("Show SENTI")
        else:
            self.companion.fade_show()
            if self.companion.is_docked:
                self.island.fade_in()
            self.act_tray_toggle.setText("Hide SENTI")

    def undock_from_island(self):
        """Called when SENTI is dragged out of the top island."""
        if not self.companion.is_docked:
            return
        self.companion.is_docked = False
        self.settings.set_docked_state(False)

        # Island smoothly disappears
        self.island.fade_out()

        # SENTI transitions to normal floating desktop size
        if not self.companion.is_orb:
            curr_pos = self.companion.pos()
            self.companion.resize(NORMAL_SIZE, NORMAL_SIZE)
            self.companion.move(curr_pos)

        # Do NOT wave hand when dragged out
        self.companion.mascot.stop_wave()
        self.play("pop")

    def return_to_island(self):
        """Double-click on SENTI: Senti glides to dock, plays attach, and pills cascade in."""
        self.companion.is_docked = True
        self.settings.set_docked_state(True)

        # Island fades back in
        self.island.fade_in()

        # Target dock position and size
        dock_pos = self.island.get_dock_target_pos(DOCKED_SIZE)
        target_geo = QRect(dock_pos.x(), dock_pos.y(), DOCKED_SIZE, DOCKED_SIZE)

        def _on_re_dock():
            self.companion.raise_()
            self.companion.mascot.trigger_squish()
            self.play("attach")
            self.island.animate_pills_entrance(
                on_pill_pop=lambda idx=0: play_pill_tick(idx, enabled=self.settings.is_sound_enabled())
            )

        # Smooth glide back into island Card 1
        self.companion.glide_to_rect(target_geo, duration=350, on_finished=_on_re_dock)

    def _on_island_drag_moved(self, new_island_pos: QPoint):
        self.settings.set_island_pos(new_island_pos)
        if self.companion.is_docked:
            dock_pos = self.island.get_dock_target_pos(self.companion.width())
            self.companion.move(dock_pos)
            self.companion.raise_()

    def _on_island_pill_hover(self, pill_name: Optional[str]):
        """Direct Senti's gaze and trigger dynamically modulated pitch hover audio."""
        if not self.companion or not hasattr(self.companion, "mascot"):
            return
        self.companion.mascot.set_pill_hover_focus(pill_name, telemetry=self.island._telemetry)
        if pill_name:
            pill_idx = PILL_HIT_INDEX.get(pill_name, 0)
            play_pill_hover(pill_idx, enabled=self.settings.is_sound_enabled())
            if pill_name == "pill_set":
                # Expressive wink tone on SET
                self.play("wink")

    def _on_manual_refresh(self):
        """Manual telemetry poll triggered from the island UI."""
        self.poll_telemetry()
        self.play("work")

    def toggle_sound(self):
        """Toggle interaction sounds on/off with audio feedback."""
        new_val = not self.settings.is_sound_enabled()
        self.settings.set_sound_enabled(new_val)
        self.play("click")
        self.island.update()

    def _on_dashboard_closed(self):
        """Reset island active state when dashboard window closes."""
        self.island.set_active_tab(None)

    def open_control_window(self):
        self.open_dashboard_tab("SETTINGS")

    def open_dashboard_tab(self, tab_name: str = "CPU"):
        """Activate or deactivate subsystem tab with toggle behavior and green dot tracking."""
        canonical = TAB_CANONICAL.get(tab_name.upper(), tab_name.upper())

        # Toggle: if dashboard is visible and currently showing this exact tab -> deactivate!
        if self.dashboard.isVisible() and self.dashboard.get_active_tab() == canonical:
            self.dashboard.close_panel()
            self.island.set_active_tab(None)
            self.play("close")
            return

        # Otherwise, activate this tab!
        isl_geo = self.island.geometry()
        x = max(10, isl_geo.center().x() - self.dashboard.width() // 2)
        y = min(
            QApplication.primaryScreen().availableGeometry().bottom() - self.dashboard.height() - 10,
            isl_geo.bottom() + 10,
        )
        self.dashboard.move(x, max(10, y))
        self.dashboard.open_tab(canonical)
        self.island.set_active_tab(canonical)
        # Immediate telemetry update
        self.dashboard.update_telemetry(get_system_info())
        self.play("show")

    def on_palette_changed(self):
        self.companion.apply_palette()

    def on_sound_toggled(self, enabled: bool):
        del enabled
        self.island.update()

    def play(self, sound_name: str):
        play_sound(sound_name, enabled=self.settings.is_sound_enabled())

    def poll_telemetry(self):
        info = get_system_info()

        # Update rolling histories (100% real hardware readings, no fake data)
        self.history_map["cpu"].append(info.get("cpu"))
        self.history_map["ram"].append(info.get("ram"))
        self.history_map["disk"].append(info.get("disk"))
        self.history_map["temperature_c"].append(info.get("temperature_c"))

        # Update state tracker
        mood = self.state_tracker.update(
            cpu=info.get("cpu"),
            ram=info.get("ram"),
            disk=info.get("disk"),
            temp=info.get("temperature_c"),
        )
        # Audio transitions on mood change
        if mood != self._prev_mood:
            if mood in ("warning", "critical"):
                self.play("annoyed")
            elif self._prev_mood in ("warning", "critical") and mood == "calm":
                self.play("approval")
            self._prev_mood = mood

        if self.companion.is_docked:
            # Inside the island: SENTI stays in his default, calm cute form
            self.companion.set_system_mood("calm")
        else:
            # Outside the island: SENTI actively shows his other expressive selves
            self.companion.set_system_mood(mood)

        # Update Island telemetry pills
        self.island.update_telemetry(info)

        # Update Dedicated Telemetry Dashboard if visible
        if self.dashboard.isVisible():
            self.dashboard.update_telemetry(info)

    def start(self):
        self.poll_telemetry()
        self.poll_timer.start()

        # Dynamic entrance choreography:
        # 1. Senti companion appears FIRST and "does its thing" (squish, cute wave, greeting chime)
        # 2. Island slides down and fades in smoothly
        # 3. Senti glides dynamically and cutely into the island dock nest
        # 4. Island pills smoothly cascade into view with spring pop transitions

        island_target_pos = get_default_island_pos(self.island.width(), self.island.height())
        self.island.move(island_target_pos)
        self.settings.set_island_pos(island_target_pos)

        # Island is initially hidden and its pills are zeroed out
        self.island.hide()
        self.island._opacity_effect.setOpacity(0.0)
        self.island._pill_scales = [0.0] * 8
        self.island._pill_alphas = [0.0] * 8

        # Target dock position inside Card 1 of the island
        dock_pos = self.island.get_dock_target_pos(DOCKED_SIZE)

        # Step 1: Senti appears FIRST in open desktop space slightly below and offset from the dock
        senti_start_x = dock_pos.x() + 90
        senti_start_y = island_target_pos.y() + 90
        self.companion.move(senti_start_x, senti_start_y)
        self.companion.resize(NORMAL_SIZE, NORMAL_SIZE)
        self.companion.is_docked = False
        self.companion.show()
        self.companion.raise_()

        # Senti does its thing: playful squish, cheerful waving paw, greeting tone
        self.companion.mascot.trigger_squish()
        self.companion.mascot.trigger_wave(2.2)
        self.play("greeting")

        # Step 2: Then the island comes (slides down and fades in)
        def _bring_in_island():
            self.island.slide_and_fade_in(island_target_pos, duration=280)

            # Step 3: Senti dynamically and cutely glides to the island dock
            def _glide_senti_to_dock():
                self.companion.mascot.stop_wave()
                target_geo = QRect(dock_pos.x(), dock_pos.y(), DOCKED_SIZE, DOCKED_SIZE)

                def _on_dock_landed():
                    self.companion.is_docked = True
                    self.settings.set_docked_state(True)
                    self.companion.raise_()
                    self.companion.mascot.trigger_squish()
                    self.play("attach")

                    # Step 4: Pills appear in a smooth transition with ascending ripple audio
                    QTimer.singleShot(
                        60,
                        lambda: self.island.animate_pills_entrance(
                            on_pill_pop=lambda idx=0: play_pill_tick(idx, enabled=self.settings.is_sound_enabled())
                        ),
                    )

                # Dynamic cute glide with OutBack curve (subtle playful landing hop)
                self.companion.glide_to_rect(
                    target_geo,
                    duration=360,
                    easing_curve=QEasingCurve.Type.OutBack,
                    on_finished=_on_dock_landed,
                )

            # Initiate Senti's glide ~160ms into the island entrance for fluid seamless motion
            QTimer.singleShot(160, _glide_senti_to_dock)

        # Allow Senti ~900ms to greet before the island appears
        QTimer.singleShot(900, _bring_in_island)

    def quit_app(self):
        self.dashboard.close()
        if not self.companion.is_docked:
            self.settings.set_window_pos(self.companion.pos())
        self.settings.set_island_pos(self.island.pos())
        QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("Sentinel")
    app.setApplicationName("SENTI")

    # Closing windows never quits the app
    app.setQuitOnLastWindowClosed(False)

    # Single-instance enforcement via QLockFile
    lock_path = os.path.join(tempfile.gettempdir(), "sentinel_senti.lock")
    lock_file = QLockFile(lock_path)
    lock_file.setStaleLockTime(30000)

    if not lock_file.tryLock(100):
        msg = QMessageBox()
        msg.setWindowTitle("Sentinel")
        msg.setText("SENTI is already running in your system tray.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        sys.exit(0)

    senti_app = SentiApp()
    senti_app.start()

    # Graceful Ctrl+C handler for console execution
    def _sigint_handler(signum, frame):
        del signum, frame
        senti_app.quit_app()

    signal.signal(signal.SIGINT, _sigint_handler)

    # Periodic timer so Python interpreter gets cycles to catch SIGINT
    sig_timer = QTimer()
    sig_timer.setInterval(250)
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start()

    exit_code = app.exec()
    lock_file.unlock()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
