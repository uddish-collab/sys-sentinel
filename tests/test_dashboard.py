"""Unit tests for SentiDashboardWindow, dedicated tabs, and advanced telemetry functions."""

import unittest
import sys
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists
app = QApplication.instance() or QApplication(sys.argv)

from src.senti_dashboard import SentiDashboardWindow, MiniSparkline
from src.senti_island import TopIslandWindow
from src.system_monitor import (
    get_cpu_cores,
    get_cpu_frequency,
    get_cpu_activity_stats,
    get_detailed_ram_info,
    get_detailed_disk_info,
    get_detailed_net_info,
    get_detailed_gpu_info,
    get_active_connections,
    get_system_info,
)


class TestDashboardAndSubsystems(unittest.TestCase):

    def test_dashboard_instantiation_and_tabs(self):
        dash = SentiDashboardWindow()
        self.assertEqual(dash.tabs.count(), 8)
        # Verify that tab bar is hidden so only the dedicated active tab appears
        self.assertFalse(dash.tabs.tabBar().isVisible())
        
        # Test direct tab switching (Aligned 1:1 with Island layout)
        # Row 1: CPU, RAM, GPU, NETWORK
        dash.open_tab("CPU")
        self.assertEqual(dash.tabs.currentIndex(), 0)
        self.assertIn("CPU", dash.lbl_title.text())
        
        dash.open_tab("RAM")
        self.assertEqual(dash.tabs.currentIndex(), 1)
        self.assertIn("MEMORY", dash.lbl_title.text())

        dash.open_tab("GPU")
        self.assertEqual(dash.tabs.currentIndex(), 2)
        self.assertIn("GPU", dash.lbl_title.text())

        dash.open_tab("NETWORK")
        self.assertEqual(dash.tabs.currentIndex(), 3)
        self.assertIn("NETWORK", dash.lbl_title.text())

        # Row 2: STORAGE, THERMALS, SYSTEM, SETTINGS
        dash.open_tab("STORAGE")
        self.assertEqual(dash.tabs.currentIndex(), 4)
        self.assertIn("STORAGE", dash.lbl_title.text())
        
        dash.open_tab("THERMALS")
        self.assertEqual(dash.tabs.currentIndex(), 5)
        self.assertIn("THERMAL", dash.lbl_title.text())

        dash.open_tab("SYSTEM")
        self.assertEqual(dash.tabs.currentIndex(), 6)
        self.assertIn("SYSTEM", dash.lbl_title.text())

        dash.open_tab("SETTINGS")
        self.assertEqual(dash.tabs.currentIndex(), 7)
        self.assertIn("SETTINGS", dash.lbl_title.text())

        dash.close()

    def test_dashboard_telemetry_update(self):
        dash = SentiDashboardWindow()
        info = get_system_info()
        dash.update_telemetry(info)
        
        # Check that UI labels were updated
        self.assertIn("%", dash.lbl_cpu_main.text())
        self.assertIn("%", dash.lbl_ram_main.text())
        dash.close()

    def test_sparkline_rolling_buffer(self):
        from PySide6.QtGui import QColor
        spark = MiniSparkline(QColor("#22c55e"), "%")
        for i in range(75):  # exceeds maxlen=60
            spark.add_sample(float(i))
        self.assertEqual(len(spark.history), 60)
        self.assertEqual(spark.history[-1], 74.0)

    def test_subsystem_telemetry_functions(self):
        cores = get_cpu_cores()
        self.assertIsInstance(cores, list)

        freq = get_cpu_frequency()
        if freq is not None:
            self.assertGreater(freq, 0)

        c_stats = get_cpu_activity_stats()
        self.assertIn("process_count", c_stats)

        ram = get_detailed_ram_info()
        self.assertIn("total_gb", ram)
        self.assertGreater(ram["total_gb"], 0)

        disk = get_detailed_disk_info()
        self.assertIn("partitions", disk)
        self.assertIn("read_mb_s", disk)

        net = get_detailed_net_info()
        self.assertIn("recv_kb_s", net)
        self.assertIn("sent_kb_s", net)

        gpu = get_detailed_gpu_info()
        self.assertIn("name", gpu)

        conns = get_active_connections(limit=5)
        self.assertIsInstance(conns, list)

    def test_island_pill_hit_testing(self):
        island = TopIslandWindow()
        self.assertEqual(island.width(), 706)

        # Row 1 (y: 26..62)
        # Pill 1: CPU (col1_x: 166..290)
        self.assertEqual(island._hit_test(QPoint(228, 44)), "pill_cpu")
        # Pill 2: RAM (col2_x: 298..422)
        self.assertEqual(island._hit_test(QPoint(360, 44)), "pill_ram")
        # Pill 3: GPU (col3_x: 430..554)
        self.assertEqual(island._hit_test(QPoint(492, 44)), "pill_gpu")
        # Pill 4: NET (col4_x: 562..686)
        self.assertEqual(island._hit_test(QPoint(624, 44)), "pill_net")

        # Row 2 (y: 68..104, 4 pills in 4x2 matrix)
        # Pill 5: DISK (col1_x: 166..290)
        self.assertEqual(island._hit_test(QPoint(228, 86)), "pill_disk")
        # Pill 6: TEMP (col2_x: 298..422)
        self.assertEqual(island._hit_test(QPoint(360, 86)), "pill_temp")
        # Pill 7: SYS (col3_x: 430..554)
        self.assertEqual(island._hit_test(QPoint(492, 86)), "pill_sys")
        # Pill 8: SET (col4_x: 562..686)
        self.assertEqual(island._hit_test(QPoint(624, 86)), "pill_set")
        island.close()

    def test_comm_link_chat_flush_on_close(self):
        dash = SentiDashboardWindow()
        dash.open_tab("SETTINGS")

        # Simulate user writing into chat
        dash.chat_log.append("<span>User test message</span>")
        dash.comm_prompt_input.setText("Unsent draft")

        # Close panel should flush chat
        dash.close_panel()
        self.assertNotIn("User test message", dash.chat_log.toPlainText())
        self.assertEqual(dash.comm_prompt_input.text(), "")
        dash.close()


if __name__ == "__main__":
    unittest.main()
