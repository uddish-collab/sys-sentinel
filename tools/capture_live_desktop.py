"""Capture the live desktop screen to inspect running SENTI on desktop."""

import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
screenshots_dir = os.path.join(REPO_ROOT, "screenshots")
os.makedirs(screenshots_dir, exist_ok=True)
out_path = os.path.join(screenshots_dir, "live_desktop_senti.png")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication

app = QApplication.instance() or QApplication(sys.argv)
screen = QGuiApplication.primaryScreen()
if screen:
    pix = screen.grabWindow(0)
    pix.save(out_path)
    print(f"Captured desktop to {out_path} ({pix.width()}x{pix.height()})")
else:
    print("Error: primary screen not found")
