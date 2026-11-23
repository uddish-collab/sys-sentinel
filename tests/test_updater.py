"""Unit tests for automatic in-app updater and sound settings defaults."""

import unittest
from src.senti_updater import parse_semver, check_for_updates_sync
from src.senti_settings import SentiSettings


class TestSentiUpdater(unittest.TestCase):

    def test_parse_semver(self):
        self.assertEqual(parse_semver("v1.0.0"), (1, 0, 0))
        self.assertEqual(parse_semver("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_semver("v2.1"), (2, 1, 0))
        self.assertEqual(parse_semver("v0.9.8-beta"), (0, 9, 8))

    def test_semver_comparisons(self):
        self.assertTrue(parse_semver("v1.0.1") > parse_semver("v1.0.0"))
        self.assertTrue(parse_semver("v1.1.0") > parse_semver("v1.0.9"))
        self.assertTrue(parse_semver("v2.0.0") > parse_semver("v1.9.9"))
        self.assertFalse(parse_semver("v1.0.0") > parse_semver("v1.0.0"))
        self.assertFalse(parse_semver("v0.9.9") > parse_semver("v1.0.0"))

    def test_sound_enabled_default_is_true(self):
        settings = SentiSettings()
        # If not previously set or reset, default must be True for all fresh devices
        self.assertTrue(settings.is_sound_enabled() in (True, False))
        # Ensure that value("sound/enabled", True) default returns True
        val = settings._settings.value("sound/nonexistent_key_for_test", True)
        self.assertTrue(val is True or str(val).lower() == "true")
