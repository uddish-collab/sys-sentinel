"""Unit tests for temperature parsing, validation, bounds, and fallback logic."""

import unittest
from src.system_monitor import parse_temperature_output


class TestTemperatureParsing(unittest.TestCase):

    def test_parse_kelvin_valid(self):
        # 315 K = 41.85 °C
        output = """
        Temperature
        -----------
                315
        """
        temp = parse_temperature_output(output, mode="kelvin")
        self.assertIsNotNone(temp)
        self.assertAlmostEqual(temp, 41.85, places=2)

    def test_parse_kelvin_multiple_readings_takes_hottest(self):
        # 310 K (36.85 °C) and 325 K (51.85 °C)
        output = """
        Temperature
        -----------
                310
                325
        """
        temp = parse_temperature_output(output, mode="kelvin")
        self.assertIsNotNone(temp)
        self.assertAlmostEqual(temp, 51.85, places=2)

    def test_parse_tenths_valid(self):
        # 3202 tenths of Kelvin = 320.2 K = 47.05 °C
        output = """
        CurrentTemperature
        ------------------
                      3202
        """
        temp = parse_temperature_output(output, mode="tenths")
        self.assertIsNotNone(temp)
        self.assertAlmostEqual(temp, 47.05, places=2)

    def test_parse_rejects_sub_zero_or_freezing(self):
        # 273 K = -0.15 °C (<= 0 °C is not sane, e.g. ACPI dummy value 273)
        output = """
        Temperature
        -----------
                273
        """
        temp = parse_temperature_output(output, mode="kelvin")
        self.assertIsNone(temp)

    def test_parse_rejects_boiling_or_hardware_error_values(self):
        # 450 K = 176.85 °C (> 125 °C is invalid/erroneous)
        output = """
        Temperature
        -----------
                450
        """
        temp = parse_temperature_output(output, mode="kelvin")
        self.assertIsNone(temp)

    def test_parse_empty_or_malformed(self):
        self.assertIsNone(parse_temperature_output("", mode="kelvin"))
        self.assertIsNone(parse_temperature_output("Error: Not Found", mode="kelvin"))
        self.assertIsNone(parse_temperature_output("----", mode="tenths"))


if __name__ == "__main__":
    unittest.main()
