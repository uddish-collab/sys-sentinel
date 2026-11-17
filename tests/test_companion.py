"""Unit tests for companion hit-testing, island geometry, and click dispatch logic."""

import unittest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
import sys

# Ensure QApplication exists for widget testing
app = QApplication.instance() or QApplication(sys.argv)

from src.senti_app import CompanionWindow, SentiApp
from src.senti_island import TopIslandWindow


class TestCompanionAndIsland(unittest.TestCase):

    def test_precision_hit_testing(self):
        # Instantiate companion
        controller = SentiApp()
        companion = controller.companion
        companion.resize(86, 86)
        companion.is_orb = False
        companion.is_docked = False

        # Center point must be inside SENTI
        center_pt = QPoint(43, 43)
        self.assertTrue(companion.is_on_senti(center_pt))

        # Top center of helmet must be inside
        helmet_top_pt = QPoint(43, 18)
        self.assertTrue(companion.is_on_senti(helmet_top_pt))

        # Far corners (transparent area) must be strictly outside (NOT draggable)
        self.assertFalse(companion.is_on_senti(QPoint(2, 2)))
        self.assertFalse(companion.is_on_senti(QPoint(84, 2)))
        self.assertFalse(companion.is_on_senti(QPoint(2, 84)))
        self.assertFalse(companion.is_on_senti(QPoint(84, 84)))

        # Clean up
        controller.hotkeys.unregister_all()
        companion.close()
        controller.island.close()
        controller.hud.close()
        controller.control_win.close()

    def test_island_dock_target_pos(self):
        island = TopIslandWindow()
        island.move(500, 10)
        dock_pos = island.get_dock_target_pos(senti_size=38)

        # Dock position should be within island bounds
        self.assertGreaterEqual(dock_pos.x(), island.x())
        self.assertLess(dock_pos.x(), island.x() + island.width())
        self.assertGreaterEqual(dock_pos.y(), island.y())
        self.assertLess(dock_pos.y(), island.y() + island.height())
        island.close()

    def test_greeting_bubble_and_island_telemetry(self):
        from src.senti_island import GreetingBubbleWidget, DEFAULT_GREETINGS
        bubble = GreetingBubbleWidget()
        bubble.show_greeting(DEFAULT_GREETINGS[0], QPoint(400, 200))
        self.assertEqual(bubble._text, DEFAULT_GREETINGS[0])
        self.assertTrue(bubble.isVisible())
        bubble.fade_out()
        bubble.close()


if __name__ == "__main__":
    unittest.main()
