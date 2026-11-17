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
    get_top_processes,
    get_active_connections,
    get_system_info,
)


class TestDashboardAndSubsystems(unittest.TestCase):

    def test_dashboard_instantiation_and_tabs(self):
        dash = SentiDashboardWindow()
        self.assertEqual(dash.tabs.count(), 8)
        
        # Test direct tab switching
        dash.open_tab("CPU")
        self.assertEqual(dash.tabs.currentIndex(), 0)
        
        dash.open_tab("RAM")
        self.assertEqual(dash.tabs.currentIndex(), 1)
        
        dash.open_tab("STORAGE")
        self.assertEqual(dash.tabs.currentIndex(), 2)
        
        dash.open_tab("THERMALS")
        self.assertEqual(dash.tabs.currentIndex(), 3)

        dash.open_tab("GPU")
        self.assertEqual(dash.tabs.currentIndex(), 4)

        dash.open_tab("NETWORK")
        self.assertEqual(dash.tabs.currentIndex(), 5)

        dash.open_tab("PROCESSES")
        self.assertEqual(dash.tabs.currentIndex(), 6)

        dash.open_tab("SYSTEM")
        self.assertEqual(dash.tabs.currentIndex(), 7)

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

        procs = get_top_processes(limit=5)
        self.assertIsInstance(procs, list)
        self.assertLessEqual(len(procs), 5)

        conns = get_active_connections(limit=5)
        self.assertIsInstance(conns, list)

    def test_island_pill_hit_testing(self):
        island = TopIslandWindow()
        # Pill 1: CPU (col1_x: 350..484, row1_y: 34..62)
        self.assertEqual(island._hit_test(QPoint(380, 48)), "pill_cpu")
        # Pill 2: RAM (col2_x: 488..622, row1_y: 34..62)
        self.assertEqual(island._hit_test(QPoint(520, 48)), "pill_ram")
        # Pill 3: DISK (col1_x: 350..484, row2_y: 74..102)
        self.assertEqual(island._hit_test(QPoint(380, 88)), "pill_disk")
        # Pill 4: TEMP (col2_x: 488..622, row2_y: 74..102)
        self.assertEqual(island._hit_test(QPoint(520, 88)), "pill_temp")
        island.close()


if __name__ == "__main__":
    unittest.main()
