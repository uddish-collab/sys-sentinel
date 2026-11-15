"""Control window providing dedicated Live Graphs and Mascot Settings."""

from typing import Optional, Dict, Callable
from PySide6.QtCore import (
    Qt,
    Signal,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QFrame,
    QColorDialog,
    QScrollArea,
    QGraphicsOpacityEffect,
    QButtonGroup,
)

from senti_state import (
    CPU_THRESHOLDS,
    RAM_THRESHOLDS,
    DISK_THRESHOLDS,
    TEMP_THRESHOLDS,
    MOOD_CALM,
    MOOD_WARNING,
    MOOD_CRITICAL,
    MetricHistory,
)
from senti_graphs import LineGraph
from senti_settings import SentiSettings, DEFAULT_COLORS
from senti_mascot import SentiMascot
from senti_widgets import (
    DARK_THEME_QSS,
    ToggleSwitch,
)


class SentiControlWindow(QWidget):
    """Dedicated window containing 4 live graphs and mascot customization settings."""

    colors_changed = Signal()
    sound_toggled = Signal(bool)

    def __init__(
        self,
        settings: SentiSettings,
        history_map: Dict[str, MetricHistory],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.history_map = history_map

        self.setWindowTitle("SYS-SENTINEL — Graphs && Settings")
        self.setObjectName("controlRoot")
        self.setStyleSheet(DARK_THEME_QSS)
        self.resize(720, 680)
        self.setMinimumSize(640, 560)

        # Smooth window opacity
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)

        # Tab widget
        self.tabs = QTabWidget(self)
        self._init_graphs_tab()
        self._init_settings_tab()
        root_layout.addWidget(self.tabs)

    def _init_graphs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Controls row: Duration Selector Buttons
        ctrl_row = QHBoxLayout()
        lbl_range = QLabel("Time Range:")
        lbl_range.setStyleSheet("color: #8c9dbd; font-size: 12px; font-weight: 600;")
        ctrl_row.addWidget(lbl_range)

        self.range_btn_group = QButtonGroup(self)
        self.btn_1m = QPushButton("1 Minute")
        self.btn_5m = QPushButton("5 Minutes")
        self.btn_15m = QPushButton("15 Minutes")

        for i, (btn, dur) in enumerate([
            (self.btn_1m, 60.0),
            (self.btn_5m, 300.0),
            (self.btn_15m, 900.0),
        ]):
            btn.setProperty("class", "actionButton")
            btn.setCheckable(True)
            self.range_btn_group.addButton(btn, i)
            btn.clicked.connect(lambda checked=False, d=dur: self._on_range_changed(d))
            ctrl_row.addWidget(btn)

        self.btn_5m.setChecked(True)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Scroll area for the 4 line graphs
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        graphs_container = QWidget()
        graphs_layout = QVBoxLayout(graphs_container)
        graphs_layout.setContentsMargins(0, 0, 0, 0)
        graphs_layout.setSpacing(12)

        # Colors from settings
        c_glow = self.settings.get_color("glow")
        c_eyes = self.settings.get_color("eyes")

        self.graph_cpu = LineGraph(
            title="CPU UTILIZATION",
            unit="%",
            history=self.history_map["cpu"],
            warn_thresh=CPU_THRESHOLDS[0],
            crit_thresh=CPU_THRESHOLDS[1],
            y_max=100.0,
            line_color=c_glow.name(),
        )

        self.graph_ram = LineGraph(
            title="MEMORY UTILIZATION",
            unit="%",
            history=self.history_map["ram"],
            warn_thresh=RAM_THRESHOLDS[0],
            crit_thresh=RAM_THRESHOLDS[1],
            y_max=100.0,
            line_color=c_eyes.name(),
        )

        self.graph_disk = LineGraph(
            title="SYSTEM DRIVE UTILIZATION",
            unit="%",
            history=self.history_map["disk"],
            warn_thresh=DISK_THRESHOLDS[0],
            crit_thresh=DISK_THRESHOLDS[1],
            y_max=100.0,
            line_color="#4fc3f7",
        )

        self.graph_temp = LineGraph(
            title="TEMPERATURE",
            unit=" °C",
            history=self.history_map["temperature_c"],
            warn_thresh=TEMP_THRESHOLDS[0],
            crit_thresh=TEMP_THRESHOLDS[1],
            y_max=120.0,
            line_color="#ff8a65",
        )

        self.graphs = [self.graph_cpu, self.graph_ram, self.graph_disk, self.graph_temp]

        for g in self.graphs:
            graphs_layout.addWidget(g)

        scroll.setWidget(graphs_container)
        layout.addWidget(scroll)

        self.tabs.addTab(tab, "Live Graphs")

    def _init_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Top area: Color buttons (Left) + Mascot Live Preview (Right)
        top_split = QHBoxLayout()
        top_split.setSpacing(20)

        # Left Column: Color pickers + Sound toggle
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

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
            btn.setFixedSize(54, 26)
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

        left_col.addSpacing(10)

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

        left_col.addSpacing(6)

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
            ("Ctrl+Shift+S", "Show / Hide SENTI (Double-click)"),
            ("Ctrl+Shift+H", "Toggle HUD (Single-click)"),
            ("Ctrl+Shift+I", "Return to Island (Triple-click)"),
            ("Ctrl+Shift+O", "Shrink to Orb / Restore"),
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

        left_col.addWidget(shortcuts_frame)

        left_col.addStretch()
        top_split.addLayout(left_col, stretch=1)

        # Right Column: Mascot Live Preview
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        preview_card = QFrame()
        preview_card.setProperty("class", "card")
        p_card_layout = QVBoxLayout(preview_card)
        p_card_layout.setContentsMargins(12, 12, 12, 12)
        p_card_layout.setSpacing(8)

        p_title = QLabel("LIVE PREVIEW")
        p_title.setStyleSheet("color: #8c9dbd; font-size: 11px; font-weight: 700; text-align: center;")
        p_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_card_layout.addWidget(p_title)

        # Preview mascot widget
        self.preview_mascot = SentiMascot(self)
        self.preview_mascot.setFixedSize(180, 180)
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

        top_split.addLayout(right_col, stretch=1)
        layout.addLayout(top_split)

        self.tabs.addTab(tab, "Settings")

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
        # Non-native QColorDialog
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
                # Update graph line colors
                if name == "glow":
                    self.graph_cpu.set_line_color(selected)
                elif name == "eyes":
                    self.graph_ram.set_line_color(selected)
                self.colors_changed.emit()

    def _reset_colors(self):
        self.settings.reset_colors()
        self._refresh_color_swatches()
        self._update_preview_mascot_palette()
        self.graph_cpu.set_line_color(self.settings.get_color("glow"))
        self.graph_ram.set_line_color(self.settings.get_color("eyes"))
        self.colors_changed.emit()

    def _on_sound_toggled(self, checked: bool):
        self.settings.set_sound_enabled(checked)
        self.sound_toggled.emit(checked)

    def _on_range_changed(self, seconds: float):
        for g in self.graphs:
            g.set_duration(seconds)

    def update_graphs(self):
        """Repaint graphs on timer tick if visible."""
        if self.isVisible():
            for g in self.graphs:
                g.update()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
