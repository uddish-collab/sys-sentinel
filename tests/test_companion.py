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
        companion.close()
        controller.island.close()
        controller.dashboard.close()
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

    def test_single_tap_hides_companion(self):
        controller = SentiApp()
        companion = controller.companion
        companion.is_docked = False
        companion.show()

        # Simulate 1 tap dispatch
        companion._click_count = 1
        companion._dispatch_clicks()

        # Should initiate fade hide
        self.assertEqual(companion._click_count, 0)
        companion.close()
        controller.island.close()
        controller.dashboard.close()
        controller.control_win.close()

    def test_double_tap_returns_to_island(self):
        controller = SentiApp()
        companion = controller.companion
        companion.is_docked = False
        companion.show()

        # Simulate 2 taps dispatch
        companion._click_count = 2
        companion._dispatch_clicks()

        # Should be docked back into the island
        self.assertTrue(companion.is_docked)
        companion.close()
        controller.island.close()
        controller.dashboard.close()
        controller.control_win.close()

    def test_island_click_triggers_funny_expression_and_sound(self):
        controller = SentiApp()
        companion = controller.companion
        companion.is_docked = True

        # Test triggering funny expression on mascot
        sound1 = companion.mascot.trigger_funny_expression()
        self.assertIn(sound1, ["dizzy", "pop", "wink", "annoyed", "love"])
        self.assertIsNotNone(companion.mascot._funny_expression)
        self.assertGreater(companion.mascot._funny_time_remaining, 0.0)

        # Cycle through all expressions
        expressions_seen = [companion.mascot._funny_expression]
        sounds_seen = [sound1]
        for _ in range(4):
            snd = companion.mascot.trigger_funny_expression()
            sounds_seen.append(snd)
            expressions_seen.append(companion.mascot._funny_expression)

        self.assertEqual(len(set(expressions_seen)), 5)
        self.assertEqual(len(set(sounds_seen)), 5)

        # Reset expression
        companion.mascot.reset_funny_expression()
        self.assertIsNone(companion.mascot._funny_expression)
        self.assertEqual(companion.mascot._funny_time_remaining, 0.0)

        companion.close()
        controller.island.close()
        controller.dashboard.close()
        controller.control_win.close()


if __name__ == "__main__":
    unittest.main()
