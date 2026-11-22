"""Unit tests for settings management and Windows app registration."""

import unittest
from PySide6.QtGui import QColor

from src.senti_settings import (
    SentiSettings,
    get_start_menu_shortcut_path,
    is_windows_app_registered,
    register_windows_app,
    unregister_windows_app,
    PRESET_THEMES,
)


class TestSentiSettings(unittest.TestCase):

    def setUp(self):
        self.settings = SentiSettings()

    def test_theme_presets_application(self):
        for theme_name in PRESET_THEMES:
            success = self.settings.apply_preset_theme(theme_name)
            self.assertTrue(success)
            expected_eye = PRESET_THEMES[theme_name]["eyes"].lower()
            actual_eye = self.settings.get_color("eyes").name().lower()
            self.assertEqual(expected_eye, actual_eye)

    def test_color_reset_and_custom(self):
        self.settings.set_color("eyes", QColor("#ff00ff"))
        self.assertEqual(self.settings.get_color("eyes").name().lower(), "#ff00ff")
        self.settings.reset_colors()
        self.assertEqual(self.settings.get_color("eyes").name().lower(), "#00e5ff")

    def test_sound_toggle(self):
        cur = self.settings.is_sound_enabled()
        self.settings.set_sound_enabled(not cur)
        self.assertEqual(self.settings.is_sound_enabled(), not cur)
        self.settings.set_sound_enabled(cur)

    def test_windows_app_registration_lifecycle(self):
        shortcut_path = get_start_menu_shortcut_path()
        self.assertTrue(shortcut_path.endswith("SYS-SENTINEL.lnk"))

        # Test registration
        reg_ok = register_windows_app("1.0.0")
        self.assertTrue(reg_ok)
        self.assertTrue(is_windows_app_registered())

        # Test unregistration
        unreg_ok = unregister_windows_app()
        self.assertTrue(unreg_ok)
        self.assertFalse(is_windows_app_registered())

        # Re-register for user convenience
        register_windows_app("1.0.0")


if __name__ == "__main__":
    unittest.main()
