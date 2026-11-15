"""Unit tests for system_monitor snapshot structure and resilience."""

import unittest
from unittest.mock import patch
from src.system_monitor import get_system_info, get_system_drive, get_os_display_name


class TestSystemMonitor(unittest.TestCase):

    def test_system_info_keys_present(self):
        info = get_system_info()
        expected_keys = [
            "cpu",
            "ram",
            "ram_used_gb",
            "ram_total_gb",
            "disk",
            "disk_used_gb",
            "disk_free_gb",
            "disk_total_gb",
            "system_drive",
            "temperature_c",
            "battery",
            "battery_plugged",
            "hostname",
            "os",
            "processor",
            "logical_cores",
            "uptime_seconds",
        ]
        for key in expected_keys:
            self.assertIn(key, info, f"Missing key: {key}")

        # Logical cores and uptime should be positive ints
        self.assertGreater(info["logical_cores"], 0)
        self.assertGreaterEqual(info["uptime_seconds"], 0)
        self.assertTrue(info["system_drive"].endswith("\\"))

    def test_system_drive_dynamic(self):
        with patch.dict("os.environ", {"SystemDrive": "D:"}):
            self.assertEqual(get_system_drive(), "D:\\")

    def test_os_display_name_windows10_vs_11(self):
        class MockWinVer:
            build = 22621
        with patch("sys.getwindowsversion", return_value=MockWinVer()):
            name = get_os_display_name()
            self.assertIn("Windows 11", name)

        class MockWinVer10:
            build = 19045
        with patch("sys.getwindowsversion", return_value=MockWinVer10()):
            name = get_os_display_name()
            self.assertIn("Windows 10", name)

    def test_resilience_when_psutil_raises_exception(self):
        with patch("psutil.virtual_memory", side_effect=OSError("Access denied")), \
             patch("psutil.disk_usage", side_effect=OSError("Drive unmounted")):
            info = get_system_info()
            # Must not crash, failed values must become None
            self.assertIsNone(info["ram"])
            self.assertIsNone(info["ram_used_gb"])
            self.assertIsNone(info["disk"])
            self.assertIsNone(info["disk_used_gb"])


if __name__ == "__main__":
    unittest.main()
