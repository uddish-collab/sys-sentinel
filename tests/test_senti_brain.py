"""Unit tests for SentiBrain deterministic Stark/JARVIS/Ultron conversational engine."""

import unittest
from src.senti_brain import SentiBrain


class TestSentiBrain(unittest.TestCase):

    def setUp(self):
        self.brain = SentiBrain()
        self.sample_telemetry = {
            "cpu": 15.0,
            "ram": 52.0,
            "ram_used_gb": 8.3,
            "ram_total_gb": 16.0,
            "temperature_c": 45.0,
            "gpu_load": 22.0,
            "gpu_name": "NVIDIA GeForce RTX 3060",
            "ping_ms": 16.5,
            "net_recv_kb_s": 240.0,
            "net_sent_kb_s": 50.0,
            "disk": 65.0,
            "disk_free_gb": 180.0,
            "disk_total_gb": 512.0,
            "system_drive": "C:",
            "battery": 88.0,
            "battery_plugged": True,
            "uptime_seconds": 7200,
        }

    def test_creator_lore(self):
        reply, mood = self.brain.respond("who created you?")
        self.assertIn("uddish-collab", reply)
        self.assertEqual(mood, "wink")

    def test_senti_identity(self):
        reply, mood = self.brain.respond("who are you")
        self.assertIn("SENTI", reply)
        self.assertEqual(mood, "stark")

    def test_cpu_calm_and_critical(self):
        # Calm CPU
        reply, mood = self.brain.respond("how is my cpu doing?", self.sample_telemetry)
        self.assertIn("15.0%", reply)
        self.assertEqual(mood, "calm")

        # Critical CPU
        hot_telemetry = dict(self.sample_telemetry, cpu=92.5)
        reply, mood = self.brain.respond("cpu load", hot_telemetry)
        self.assertIn("92.5%", reply)
        self.assertEqual(mood, "alert")

    def test_ram_query(self):
        reply, mood = self.brain.respond("how much memory is free?", self.sample_telemetry)
        self.assertIn("8.3 GB", reply)
        self.assertEqual(mood, "calm")

    def test_thermal_query(self):
        reply, mood = self.brain.respond("is my laptop hot?", self.sample_telemetry)
        self.assertIn("45.0°C", reply)

    def test_network_query(self):
        reply, mood = self.brain.respond("check my ping", self.sample_telemetry)
        self.assertIn("16.5 ms", reply)

    def test_storage_query(self):
        reply, mood = self.brain.respond("how much storage space is left?", self.sample_telemetry)
        self.assertIn("180.0 GB free", reply)

    def test_uptime_query(self):
        reply, mood = self.brain.respond("what is my system uptime?", self.sample_telemetry)
        self.assertIn("2h 0m", reply)

    def test_greetings_and_thanks(self):
        reply, mood = self.brain.respond("hey there")
        self.assertTrue(len(reply) > 5)

        reply, mood = self.brain.respond("thanks senti")
        self.assertTrue(len(reply) > 5)

    def test_help_and_fallback(self):
        reply, mood = self.brain.respond("help")
        self.assertIn("CPU", reply)

        reply, mood = self.brain.respond("xyz arbitrary babble 1234")
        self.assertTrue(len(reply) > 10)


if __name__ == "__main__":
    unittest.main()
