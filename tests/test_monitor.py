
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

    def test_usage_bar_zero(self):
        bar = get_bar(0)
        self.assertEqual(bar.count("━"), 20)

    def test_usage_bar_maximum(self):
        bar = get_bar(100)
        self.assertEqual(bar.count("━"), 20)

    def test_usage_bar_above_maximum(self):
        bar = get_bar(150)
        self.assertEqual(bar.count("━"), 20)

    def test_usage_bar_below_zero(self):
        bar = get_bar(-10)
        self.assertEqual(bar.count("━"), 20)


if __name__ == "__main__":
    unittest.main()
