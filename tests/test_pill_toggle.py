"""Unit tests for pill toggle activation / deactivation and active pill green dot state."""

import unittest
import sys
from pathlib import Path

# Add src to sys.path so intra-package imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.senti_island import TopIslandWindow, TAB_CANONICAL
from src.senti_dashboard import SentiDashboardWindow


class TestPillToggleAndGreenDot(unittest.TestCase):

    def test_island_active_tab_tracking(self):
        island = TopIslandWindow()
        self.assertIsNone(island.get_active_tab())

        # Set active to CPU
        island.set_active_tab("CPU")
        self.assertEqual(island.get_active_tab(), "CPU")

        # Set active to RAM via alias
        island.set_active_tab("MEMORY")
        self.assertEqual(island.get_active_tab(), "RAM")

        # Set active to None (deactivated)
        island.set_active_tab(None)
        self.assertIsNone(island.get_active_tab())

        island.close()

    def test_dashboard_active_tab_and_closed_signal(self):
        dash = SentiDashboardWindow()
        closed_signals = []
        dash.closed.connect(lambda: closed_signals.append(True))

        dash.open_tab("CPU")
        self.assertEqual(dash.get_active_tab(), "CPU")

        dash.open_tab("GPU")
        self.assertEqual(dash.get_active_tab(), "GPU")

        # Close panel -> emits closed signal and resets active tab
        dash.close_panel()
        self.assertEqual(len(closed_signals), 1)
        self.assertIsNone(dash.get_active_tab())

        dash.close()

    def test_app_pill_toggle_integration(self):
        from src.senti_app import SentiApp
        app_ctrl = SentiApp()

        # Initially no tab active
        self.assertIsNone(app_ctrl.island.get_active_tab())
        self.assertFalse(app_ctrl.dashboard.isVisible())

        # 1. Click CPU pill -> Activates CPU
        app_ctrl.open_dashboard_tab("CPU")
        self.assertTrue(app_ctrl.dashboard.isVisible())
        self.assertEqual(app_ctrl.island.get_active_tab(), "CPU")
        self.assertEqual(app_ctrl.dashboard.get_active_tab(), "CPU")

        # 2. Click CPU pill again -> Deactivates CPU (closes dashboard)
        app_ctrl.open_dashboard_tab("CPU")
        self.assertIsNone(app_ctrl.island.get_active_tab())
        self.assertIsNone(app_ctrl.dashboard.get_active_tab())

        # 3. Click GPU pill -> Activates GPU
        app_ctrl.open_dashboard_tab("GPU")
        self.assertTrue(app_ctrl.dashboard.isVisible())
        self.assertEqual(app_ctrl.island.get_active_tab(), "GPU")
        self.assertEqual(app_ctrl.dashboard.get_active_tab(), "GPU")

        # 4. Click RAM pill -> Switches to RAM (moves active indicator)
        app_ctrl.open_dashboard_tab("RAM")
        self.assertTrue(app_ctrl.dashboard.isVisible())
        self.assertEqual(app_ctrl.island.get_active_tab(), "RAM")
        self.assertEqual(app_ctrl.dashboard.get_active_tab(), "RAM")

        # 5. Close dashboard via close button / close_panel -> Deactivates
        app_ctrl.dashboard.close_panel()
        self.assertIsNone(app_ctrl.island.get_active_tab())

        app_ctrl.companion.close()
        app_ctrl.island.close()
        app_ctrl.dashboard.close()


    def test_tab_canonical_mapping(self):
        self.assertEqual(TAB_CANONICAL["CPU"], "CPU")
        self.assertEqual(TAB_CANONICAL["RAM"], "RAM")
        self.assertEqual(TAB_CANONICAL["MEMORY"], "RAM")
        self.assertEqual(TAB_CANONICAL["GPU"], "GPU")
        self.assertEqual(TAB_CANONICAL["NET"], "NETWORK")
        self.assertEqual(TAB_CANONICAL["NETWORK"], "NETWORK")
        self.assertEqual(TAB_CANONICAL["DISK"], "STORAGE")
        self.assertEqual(TAB_CANONICAL["STORAGE"], "STORAGE")
        self.assertEqual(TAB_CANONICAL["TEMP"], "THERMALS")
        self.assertEqual(TAB_CANONICAL["THERMALS"], "THERMALS")
        self.assertEqual(TAB_CANONICAL["SYS"], "SYSTEM")
        self.assertEqual(TAB_CANONICAL["BAT"], "SYSTEM")
        self.assertEqual(TAB_CANONICAL["SETTINGS"], "SETTINGS")
        self.assertEqual(TAB_CANONICAL["SET"], "SETTINGS")


if __name__ == "__main__":
    unittest.main()
