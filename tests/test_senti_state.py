"""Unit tests for SENTI mood logic, state thresholds, hysteresis, history, and formatting."""

import unittest
from src.senti_state import (
    CPU_THRESHOLDS,
    RAM_THRESHOLDS,
    DISK_THRESHOLDS,
    TEMP_THRESHOLDS,
    STATUS_NORMAL,
    STATUS_WARNING,
    STATUS_CRITICAL,
    STATUS_UNAVAILABLE,
    MOOD_CALM,
    MOOD_WARNING,
    MOOD_CRITICAL,
    get_metric_status,
    evaluate_raw_mood,
    StateTracker,
    MetricHistory,
    format_uptime,
    format_gb,
    format_percent,
    format_temp,
)


class TestSentiState(unittest.TestCase):

    def test_threshold_values(self):
        self.assertEqual(CPU_THRESHOLDS, (65.0, 85.0))
        self.assertEqual(RAM_THRESHOLDS, (65.0, 85.0))
        self.assertEqual(DISK_THRESHOLDS, (90.0, 95.0))
        self.assertEqual(TEMP_THRESHOLDS, (75.0, 85.0))

    def test_get_metric_status(self):
        self.assertEqual(get_metric_status(None, 65, 85), STATUS_UNAVAILABLE)
        self.assertEqual(get_metric_status(30.0, 65, 85), STATUS_NORMAL)
        self.assertEqual(get_metric_status(65.0, 65, 85), STATUS_WARNING)
        self.assertEqual(get_metric_status(75.0, 65, 85), STATUS_WARNING)
        self.assertEqual(get_metric_status(85.0, 65, 85), STATUS_CRITICAL)
        self.assertEqual(get_metric_status(99.0, 65, 85), STATUS_CRITICAL)

    def test_evaluate_raw_mood(self):
        # All normal
        self.assertEqual(evaluate_raw_mood(30, 40, 50, 45), MOOD_CALM)
        # Missing values count as normal
        self.assertEqual(evaluate_raw_mood(None, None, None, None), MOOD_CALM)
        self.assertEqual(evaluate_raw_mood(30, None, 50, None), MOOD_CALM)

        # Warning triggers
        self.assertEqual(evaluate_raw_mood(66, 30, 30, 40), MOOD_WARNING)
        self.assertEqual(evaluate_raw_mood(30, 66, 30, 40), MOOD_WARNING)
        self.assertEqual(evaluate_raw_mood(30, 30, 91, 40), MOOD_WARNING)
        self.assertEqual(evaluate_raw_mood(30, 30, 30, 76), MOOD_WARNING)

        # Critical triggers
        self.assertEqual(evaluate_raw_mood(86, 30, 30, 40), MOOD_CRITICAL)
        self.assertEqual(evaluate_raw_mood(30, 86, 30, 40), MOOD_CRITICAL)
        self.assertEqual(evaluate_raw_mood(30, 30, 96, 40), MOOD_CRITICAL)
        self.assertEqual(evaluate_raw_mood(30, 30, 30, 86), MOOD_CRITICAL)

        # Disk 89 should NOT make SENTI worried (threshold is 90)
        self.assertEqual(evaluate_raw_mood(40, 40, 89, 40), MOOD_CALM)

    def test_tracker_moving_average_and_immediate_escalation(self):
        tracker = StateTracker(window_size=3, relax_delay=4)
        self.assertEqual(tracker.current_mood, MOOD_CALM)

        # 3 normal samples
        self.assertEqual(tracker.update(20, 20, 20, 30), MOOD_CALM)
        self.assertEqual(tracker.update(20, 20, 20, 30), MOOD_CALM)
        self.assertEqual(tracker.update(20, 20, 20, 30), MOOD_CALM)

        # Spike in CPU: (20 + 20 + 100) / 3 = 46.6% -> still calm
        self.assertEqual(tracker.update(100, 20, 20, 30), MOOD_CALM)
        # Second spike: (20 + 100 + 100) / 3 = 73.3% -> escalates IMMEDIATELY to warning!
        self.assertEqual(tracker.update(100, 20, 20, 30), MOOD_WARNING)

        # Third spike: (100 + 100 + 100) / 3 = 100% -> escalates IMMEDIATELY to critical!
        self.assertEqual(tracker.update(100, 20, 20, 30), MOOD_CRITICAL)

    def test_tracker_hysteresis_relaxation(self):
        tracker = StateTracker(window_size=3, relax_delay=4)

        # Put into critical state
        for _ in range(3):
            tracker.update(90, 20, 20, 30)
        self.assertEqual(tracker.current_mood, MOOD_CRITICAL)

        # Now load drops to 20%
        # Window size is 3, so:
        # Sample 1: (90+90+20)/3 = 66.6% -> avg is warning, not calm yet
        mood1 = tracker.update(20, 20, 20, 30)
        # Hysteresis: requires 4 consecutive samples indicating the lower state!
        self.assertEqual(mood1, MOOD_CRITICAL)

        # Sample 2: (90+20+20)/3 = 43.3% -> target is calm
        mood2 = tracker.update(20, 20, 20, 30)
        self.assertEqual(mood2, MOOD_CRITICAL)  # 1st calm sample

        # Sample 3: (20+20+20)/3 = 20% -> target is calm
        mood3 = tracker.update(20, 20, 20, 30)
        self.assertEqual(mood3, MOOD_CRITICAL)  # 2nd calm sample

        # Sample 4
        mood4 = tracker.update(20, 20, 20, 30)
        self.assertEqual(mood4, MOOD_CRITICAL)  # 3rd calm sample

        # Sample 5: 4th consecutive calm sample -> now relaxes!
        mood5 = tracker.update(20, 20, 20, 30)
        self.assertEqual(mood5, MOOD_CALM)

    def test_history_and_stats(self):
        history = MetricHistory(maxlen=900)
        base_time = 1000.0

        # Empty history stats
        curr, avg, peak = history.stats(60, now=base_time)
        self.assertIsNone(curr)
        self.assertIsNone(avg)
        self.assertIsNone(peak)

        # Append samples with None interspersed
        history.append(10.0, timestamp=base_time - 50)
        history.append(None, timestamp=base_time - 40)
        history.append(30.0, timestamp=base_time - 30)
        history.append(20.0, timestamp=base_time - 10)

        # Test within 60 second window
        curr, avg, peak = history.stats(60, now=base_time)
        self.assertEqual(curr, 20.0)
        self.assertAlmostEqual(avg, 20.0)  # (10 + 30 + 20) / 3 = 20
        self.assertEqual(peak, 30.0)

        # Test within 20 second window (only the 20.0 sample is inside)
        curr, avg, peak = history.stats(20, now=base_time)
        self.assertEqual(curr, 20.0)
        self.assertEqual(avg, 20.0)
        self.assertEqual(peak, 20.0)

    def test_formatting(self):
        self.assertEqual(format_uptime(0), "0h 0m")
        self.assertEqual(format_uptime(125), "0h 2m")
        self.assertEqual(format_uptime(3665), "1h 1m")
        self.assertEqual(format_uptime(90000), "1d 1h 0m")

        self.assertEqual(format_gb(None), "Unavailable")
        self.assertEqual(format_gb(15.42), "15.4 GB")

        self.assertEqual(format_percent(None), "Unavailable")
        self.assertEqual(format_percent(42.8), "43%")

        self.assertEqual(format_temp(None), "Unavailable")
        self.assertEqual(format_temp(62.4), "62 °C")


if __name__ == "__main__":
    unittest.main()
