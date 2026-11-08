import unittest

from src.monitor import get_bar, get_status


class TestSysSentinel(unittest.TestCase):

    def test_normal_status(self):
        self.assertIn("NORMAL", get_status(30, 85))

    def test_warning_status(self):
        self.assertIn("WARNING", get_status(70, 85))

    def test_critical_status(self):
        self.assertIn("CRITICAL", get_status(90, 85))

    def test_usage_bar(self):
        bar = get_bar(50)
        self.assertIn("━", bar)


if __name__ == "__main__":
    unittest.main()
