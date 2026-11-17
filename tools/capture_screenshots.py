"""Capture high-resolution screenshots of SENTI companion, HUD, graphs, and settings for visual verification."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication
from senti_mascot import SentiMascot, render_mascot_image
from senti_hud import SentiHud
from senti_control import SentiControlWindow
from senti_settings import SentiSettings
from senti_state import (
    MetricHistory,
    MOOD_CALM,
    MOOD_WARNING,
    MOOD_CRITICAL,
)
from system_monitor import get_system_info


def capture_all():
    app = QApplication.instance() or QApplication(sys.argv)
    output_dir = os.path.join(REPO_ROOT, "screenshots")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Capture Companion Mascot in all 3 states (new compact size)
    for mood, name in [
        (MOOD_CALM, "companion_calm.png"),
        (MOOD_WARNING, "companion_warning.png"),
        (MOOD_CRITICAL, "companion_critical.png"),
    ]:
        mascot = SentiMascot()
        mascot.resize(72, 72)
        mascot.set_orb(0.0)
        mascot.set_mood(mood)
        # Force one step of instant target convergence for screenshot
        mascot._eye_width = mascot._target_eye_width
        mascot._eye_height = mascot._target_eye_height
        mascot._brow_angle = mascot._target_brow_angle
        mascot._mouth_curve = mascot._target_mouth_curve
        mascot._tint_amount = mascot._target_tint_amount
        mascot._timer.stop()

        mascot.show()
        pix = mascot.grab()
        mascot.hide()
        pix.save(os.path.join(output_dir, name))
        print(f"Saved: {name}")

    # Orb state (new compact size)
    mascot_orb = SentiMascot()
    mascot_orb.resize(44, 44)
    mascot_orb.set_orb(1.0)
    mascot_orb._timer.stop()
    mascot_orb.show()
    pix_orb = mascot_orb.grab()
    mascot_orb.hide()
    pix_orb.save(os.path.join(output_dir, "companion_orb.png"))
    print("Saved: companion_orb.png")

    # Island with docked SENTI
    from senti_island import TopIslandWindow, GreetingBubbleWidget
    island = TopIslandWindow()
    island.update_telemetry({
        "cpu": 38.0,
        "ram": 54.0,
        "disk": 68.0,
        "temperature_c": 42.0,
        "system_drive": "C:",
    })
    docked_senti = SentiMascot(island)
    docked_senti.resize(72, 72)
    docked_senti.move(42, 56)
    docked_senti._timer.stop()
    island.show()
    pix_island = island.grab()
    island.hide()
    pix_island.save(os.path.join(output_dir, "island_docked.png"))
    print("Saved: island_docked.png")

    # Greeting bubble
    bubble = GreetingBubbleWidget()
    bubble._text = "Hello, Operator!"
    bubble._opacity_effect.setOpacity(1.0)
    bubble._fade_anim.stop()
    bubble._dismiss_timer.stop()
    bubble.show()
    pix_bubble = bubble.grab()
    bubble.hide()
    pix_bubble.save(os.path.join(output_dir, "greeting_bubble.png"))
    print("Saved: greeting_bubble.png")

    # 2. Capture HUD
    hud = SentiHud()
    sample_data = {
        "cpu": 38.0,
        "ram": 54.0,
        "ram_used_gb": 8.6,
        "ram_total_gb": 15.9,
        "disk": 68.0,
        "disk_used_gb": 320.5,
        "disk_free_gb": 150.2,
        "disk_total_gb": 470.7,
        "system_drive": "C:\\",
        "temperature_c": None,  # Test honest None / Unavailable display
        "battery": 85.0,
        "battery_plugged": True,
        "hostname": "SENTINEL-RIG",
        "os": "Windows 10 (Build 19045)",
        "processor": "Intel(R) Core(TM) i7-11800H @ 2.30GHz",
        "logical_cores": 16,
        "uptime_seconds": 18420,
    }
    hud.update_data(sample_data)
    hud.show()
    pix_hud = hud.grab()
    hud.hide()
    pix_hud.save(os.path.join(output_dir, "hud.png"))
    print("Saved: hud.png")

    # 3. Capture Control Window: Graphs tab & Settings tab
    settings = SentiSettings()
    settings.reset_colors()
    import time
    now = time.time()
    hist_map = {
        "cpu": MetricHistory(900),
        "ram": MetricHistory(900),
        "disk": MetricHistory(900),
        "temperature_c": MetricHistory(900),
    }
    # Populate mock historical data for realistic graph rendering
    import math
    for i in range(120):
        t = now - (120 - i)
        hist_map["cpu"].append(35.0 + 20.0 * math.sin(i / 10.0), timestamp=t)
        hist_map["ram"].append(50.0 + 5.0 * math.cos(i / 15.0), timestamp=t)
        hist_map["disk"].append(68.0, timestamp=t)
        # Temperature has no sensor data (tests honest message)

    ctrl = SentiControlWindow(settings, hist_map)
    ctrl.tabs.setCurrentIndex(0)  # Graphs tab
    ctrl.show()
    pix_graphs = ctrl.grab()
    pix_graphs.save(os.path.join(output_dir, "graphs.png"))
    print("Saved: graphs.png")

    ctrl.tabs.setCurrentIndex(1)  # Settings tab
    pix_settings = ctrl.grab()
    ctrl.hide()
    pix_settings.save(os.path.join(output_dir, "settings.png"))
    print("Saved: settings.png")


if __name__ == "__main__":
    capture_all()
