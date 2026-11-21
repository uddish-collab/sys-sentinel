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

    # Island with docked SENTI (8 subsystem pills)
    from senti_island import TopIslandWindow
    island = TopIslandWindow()
    island._pill_scales = [1.0] * 8
    island._pill_alphas = [1.0] * 8
    island.update_telemetry({
        "cpu": 38.0,
        "ram": 54.0,
        "disk": 68.0,
        "temperature_c": 42.0,
        "system_drive": "C:",
        "gpu_load": 15.0,
        "net_recv_kb_s": 148.0,
        "ping_ms": 18.0,
        "process_count": 184,
        "battery": 92.0,
        "uptime_seconds": 18420,
    })
    docked_senti = SentiMascot(island)
    docked_senti.resize(80, 80)
    dock_pos = island.get_dock_target_pos(80)
    docked_senti.move(dock_pos.x() - island.x(), dock_pos.y() - island.y())
    docked_senti._timer.stop()
    island.show()
    pix_island = island.grab()
    island.hide()
    pix_island.save(os.path.join(output_dir, "island_docked.png"))
    print("Saved: island_docked.png")

    # 3. Capture Settings Window
    settings = SentiSettings()
    settings.reset_colors()

    ctrl = SentiControlWindow(settings)
    ctrl.show()
    pix_settings = ctrl.grab()
    ctrl.hide()
    pix_settings.save(os.path.join(output_dir, "settings.png"))
    print("Saved: settings.png")

    # 4. Capture Dedicated Telemetry Dashboard (showing only dedicated tab with no other tabs)
    from senti_dashboard import SentiDashboardWindow
    from system_monitor import get_system_info
    dash = SentiDashboardWindow()
    dash.update_telemetry(get_system_info())

    # Capture CPU dedicated view
    dash.open_tab("CPU")
    dash.grab().save(os.path.join(output_dir, "dashboard_cpu.png"))
    print("Saved: dashboard_cpu.png")

    # Capture Memory dedicated view
    dash.open_tab("RAM")
    dash.grab().save(os.path.join(output_dir, "dashboard_memory.png"))
    print("Saved: dashboard_memory.png")

    # Capture Storage dedicated view
    dash.open_tab("STORAGE")
    dash.grab().save(os.path.join(output_dir, "dashboard_storage.png"))
    print("Saved: dashboard_storage.png")

    # Capture Thermals dedicated view
    dash.open_tab("THERMALS")
    dash.grab().save(os.path.join(output_dir, "dashboard_thermals.png"))
    print("Saved: dashboard_thermals.png")

    # Capture GPU dedicated view
    dash.open_tab("GPU")
    dash.grab().save(os.path.join(output_dir, "dashboard_gpu.png"))
    print("Saved: dashboard_gpu.png")

    # Capture Network dedicated view
    dash.open_tab("NETWORK")
    dash.grab().save(os.path.join(output_dir, "dashboard_network.png"))
    print("Saved: dashboard_network.png")

    dash.hide()


if __name__ == "__main__":
    capture_all()
