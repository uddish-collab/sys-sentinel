"""Dedicated Settings window for Sentinel mascot, themes, and configuration."""

from typing import Optional, Dict
from PySide6.QtCore import (
    Qt,
    Signal,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QColorDialog,
    QGraphicsOpacityEffect,
)

from senti_state import (
    MOOD_CALM,
    MOOD_WARNING,
    MOOD_CRITICAL,
)
from senti_settings import SentiSettings, DEFAULT_COLORS, PRESET_THEMES
from senti_mascot import SentiMascot
from senti_widgets import (
    DARK_THEME_QSS,
    ToggleSwitch,
)


class SentiControlWindow(QWidget):
    """Dedicated settings and customization window for Sentinel."""

    colors_changed = Signal()
    sound_toggled = Signal(bool)

    def __init__(
        self,
        settings: SentiSettings,
        history_map: Optional[Dict] = None,
        parent: Optional[QWidget] = None,
    ):
        del history_map  # Retained for signature compatibility
        super().__init__(parent)
        self.settings = settings

        self.setWindowTitle("Sentinel — Settings")
        self.setObjectName("controlRoot")
        self.setStyleSheet(DARK_THEME_QSS)
        self.resize(600, 470)
        self.setMinimumSize(560, 440)

        # Smooth window opacity
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(14)

        # Top area: Themes & Palette (Left) + Mascot Live Preview (Right)
        top_split = QHBoxLayout()
        top_split.setSpacing(20)

        # Left Column: Preset themes, Color pickers, and Sound switch
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        theme_title = QLabel("PRESET THEMES")
        theme_title.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        left_col.addWidget(theme_title)

        theme_layout = QGridLayout()
        theme_layout.setSpacing(6)
        col_idx = 0
        row_idx = 0
        for theme_name in PRESET_THEMES:
            t_btn = QPushButton(theme_name)
            t_btn.setProperty("class", "actionButton")
            t_btn.setStyleSheet("padding: 5px 8px; font-size: 11px; text-align: center;")
            t_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            t_btn.clicked.connect(lambda checked=False, tn=theme_name: self._apply_preset_theme(tn))
            theme_layout.addWidget(t_btn, row_idx, col_idx)
            col_idx += 1
            if col_idx > 1:
                col_idx = 0
                row_idx += 1
        left_col.addLayout(theme_layout)
        left_col.addSpacing(6)

        color_title = QLabel("PALETTE CUSTOMIZATION")
        color_title.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        left_col.addWidget(color_title)

        self.color_swatches: Dict[str, QPushButton] = {}
        color_items = [
            ("body", "Body / Shell (Primary)"),
            ("details", "Details / Visor (Secondary)"),
            ("eyes", "Eyes (Illumination)"),
            ("glow", "Aura Glow"),
        ]

        for key, label in color_items:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #cdd9ed; font-size: 12px;")
            row.addWidget(lbl)
            row.addStretch()

            btn = QPushButton()
            btn.setFixedSize(54, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, k=key: self._choose_color(k))
            self.color_swatches[key] = btn
            row.addWidget(btn)
            left_col.addLayout(row)

        self._refresh_color_swatches()

        # Restore defaults button
        btn_reset = QPushButton("Restore default colours")
        btn_reset.setProperty("class", "actionButton")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_colors)
        left_col.addWidget(btn_reset)

        left_col.addSpacing(8)

        # Sound Toggle row
        sound_row = QHBoxLayout()
        sound_lbl = QLabel("Interaction Sounds")
        sound_lbl.setStyleSheet("color: #cdd9ed; font-size: 12px; font-weight: 600;")
        sound_row.addWidget(sound_lbl)
        sound_row.addStretch()

        self.sound_switch = ToggleSwitch(checked=self.settings.is_sound_enabled(), parent=self)
        self.sound_switch.toggled.connect(self._on_sound_toggled)
        sound_row.addWidget(self.sound_switch)
        left_col.addLayout(sound_row)

        left_col.addStretch()
        top_split.addLayout(left_col, stretch=1)

        # Right Column: Mascot Live Preview + Shortcuts
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        preview_card = QFrame()
        preview_card.setProperty("class", "card")
        p_card_layout = QVBoxLayout(preview_card)
        p_card_layout.setContentsMargins(12, 10, 12, 10)
        p_card_layout.setSpacing(6)

        p_title = QLabel("LIVE PREVIEW")
        p_title.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 700; text-align: center;")
        p_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_card_layout.addWidget(p_title)

        # Preview mascot widget
        self.preview_mascot = SentiMascot(self)
        self.preview_mascot.setFixedSize(160, 160)
        self._update_preview_mascot_palette()
        p_card_layout.addWidget(self.preview_mascot, alignment=Qt.AlignmentFlag.AlignCenter)

        # Preview mood buttons
        btn_row = QHBoxLayout()
        self.btn_calm = QPushButton("Calm")
        self.btn_warn = QPushButton("Warning")
        self.btn_crit = QPushButton("Critical")

        for b, mood in [
            (self.btn_calm, MOOD_CALM),
            (self.btn_warn, MOOD_WARNING),
            (self.btn_crit, MOOD_CRITICAL),
        ]:
            b.setProperty("class", "actionButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked=False, m=mood: self.preview_mascot.set_mood(m))
            btn_row.addWidget(b)

        p_card_layout.addLayout(btn_row)
        right_col.addWidget(preview_card)

        # Global Shortcuts Info Card
        shortcuts_frame = QFrame()
        shortcuts_frame.setProperty("class", "card")
        sc_layout = QVBoxLayout(shortcuts_frame)
        sc_layout.setContentsMargins(10, 8, 10, 8)
        sc_layout.setSpacing(4)

        sc_title = QLabel("KEYBOARD SHORTCUTS")
        sc_title.setStyleSheet("color: #00e5ff; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        sc_layout.addWidget(sc_title)

        for key_str, action_str in [
            ("Ctrl+Shift+S", "Show / Hide SENTI"),
            ("Ctrl+Shift+H", "Toggle Telemetry HUD"),
            ("Ctrl+Shift+I", "Return to Island Dock"),
            ("Ctrl+Shift+O", "Toggle Orb Mode"),
        ]:
            r = QHBoxLayout()
            k_lbl = QLabel(key_str)
            k_lbl.setStyleSheet("color: #00e5ff; background: #0c182b; border: 1px solid #1a3052; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;")
            a_lbl = QLabel(action_str)
            a_lbl.setStyleSheet("color: #8c9dbd; font-size: 11px;")
            r.addWidget(k_lbl)
            r.addWidget(a_lbl)
            r.addStretch()
            sc_layout.addLayout(r)

        right_col.addWidget(shortcuts_frame)
        top_split.addLayout(right_col, stretch=1)
        root_layout.addLayout(top_split)

    def _refresh_color_swatches(self):
        for key, btn in self.color_swatches.items():
            c = self.settings.get_color(key)
            text_color = "#111a30" if key == "body" else "#ffffff"
            btn.setText(c.name().upper())
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.name()};
                    color: {text_color};
                    border: 1px solid #ffffff;
                    border-radius: 4px;
                    font-size: 9px;
                    font-weight: bold;
                }}
            """)

    def _update_preview_mascot_palette(self):
        self.preview_mascot.set_palette_colors(
            self.settings.get_color("body"),
            self.settings.get_color("details"),
            self.settings.get_color("eyes"),
            self.settings.get_color("glow"),
        )

    def _choose_color(self, name: str):
        current_c = self.settings.get_color(name)
        dialog = QColorDialog(current_c, self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setWindowTitle(f"Choose {name.capitalize()} Colour")

        if dialog.exec():
            selected = dialog.selectedColor()
            if selected.isValid():
                self.settings.set_color(name, selected)
                self._refresh_color_swatches()
                self._update_preview_mascot_palette()
                self.colors_changed.emit()

    def _apply_preset_theme(self, theme_name: str):
        self.settings.apply_preset_theme(theme_name)
        self._refresh_color_swatches()
        self._update_preview_mascot_palette()
        self.colors_changed.emit()

    def _reset_colors(self):
        self.settings.reset_colors()
        self._refresh_color_swatches()
        self._update_preview_mascot_palette()
        self.colors_changed.emit()

    def _on_sound_toggled(self, checked: bool):
        self.settings.set_sound_enabled(checked)
        self.sound_toggled.emit(checked)

    def update_graphs(self):
        """No-op stub for backward compatibility."""
        pass

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
