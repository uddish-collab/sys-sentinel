"""Automatic in-app updater for SYS-SENTINEL.

Connects to GitHub Releases API to check for updates, download new binaries,
and seamlessly apply updates and restart the application without manual downloads.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from typing import Optional, Dict, Any, Tuple, Callable

from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QFrame,
    QApplication,
    QWidget,
)

GITHUB_REPO = "uddish-collab/sys-sentinel"
DEFAULT_USER_AGENT = "Sys-Sentinel-Updater/1.0"


def parse_semver(version_str: str) -> Tuple[int, ...]:
    """Parse semver string like 'v1.0.1' or '1.2.3' into a comparable tuple of ints."""
    clean = re.sub(r"^[vV]", "", version_str.strip())
    # Extract only numeric components
    parts = []
    for piece in clean.split("."):
        match = re.match(r"^(\d+)", piece)
        if match:
            parts.append(int(match.group(1)))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_for_updates_sync(current_version: str, repo: str = GITHUB_REPO) -> Optional[Dict[str, Any]]:
    """Query GitHub Releases API to find if a newer release exists."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))

        tag_name = data.get("tag_name", "")
        if not tag_name:
            return None

        remote_ver = parse_semver(tag_name)
        curr_ver = parse_semver(current_version)

        if remote_ver <= curr_ver:
            return None

        # Look for the portable standalone executable or setup asset
        assets = data.get("assets", [])
        chosen_asset = None
        for a in assets:
            aname = a.get("name", "").lower()
            if aname == "senti.exe":
                chosen_asset = a
                break

        if not chosen_asset:
            for a in assets:
                aname = a.get("name", "").lower()
                if aname.endswith(".exe"):
                    chosen_asset = a
                    break

        if not chosen_asset:
            return None

        return {
            "version": tag_name,
            "title": data.get("name", tag_name),
            "notes": data.get("body", "No release notes provided."),
            "asset_name": chosen_asset.get("name", "SENTI.exe"),
            "download_url": chosen_asset.get("browser_download_url"),
            "size": chosen_asset.get("size", 0),
        }
    except Exception:
        return None


def download_file_stream(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
) -> bool:
    """Download a file with chunked streaming and progress reporting."""
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 65536

            with open(dest_path, "wb") as f:
                while True:
                    if cancel_flag and cancel_flag():
                        return False
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        return True
    except Exception:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        return False


def apply_update_and_restart(downloaded_file: str) -> bool:
    """Replace current executable with downloaded update and restart application."""
    if not os.path.isfile(downloaded_file):
        return False

    is_frozen = getattr(sys, "frozen", False)
    if not is_frozen:
        # Development mode fallback
        return True

    target_exe = os.path.abspath(sys.executable)
    pid = os.getpid()
    bat_path = os.path.join(tempfile.gettempdir(), f"senti_update_{pid}.bat")

    # Clean Windows self-updater script that waits for current process to exit
    bat_content = f"""@echo off
set "TARGET={target_exe}"
set "SOURCE={downloaded_file}"
set "PID={pid}"

:wait_loop
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

:copy_loop
copy /Y "%SOURCE%" "%TARGET%" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto copy_loop
)

del "%SOURCE%" >nul 2>&1
start "" "%TARGET%"
del "%~f0" >nul 2>&1
"""

    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Launch detached updater script without command window
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=flags)

        # Exit current instance
        app = QApplication.instance()
        if app:
            app.quit()
        else:
            sys.exit(0)
        return True
    except Exception:
        return False


class UpdateWorker(QObject):
    """Background worker for checking updates and downloading files."""

    check_finished = Signal(object)  # dict or None
    progress = Signal(int, int)      # downloaded, total
    download_finished = Signal(bool, str)  # success, file_path

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version
        self._cancel_download = False

    def run_check(self):
        info = check_for_updates_sync(self.current_version)
        self.check_finished.emit(info)

    def run_download(self, url: str):
        self._cancel_download = False
        dest = os.path.join(tempfile.gettempdir(), "senti_update_payload.exe")
        ok = download_file_stream(
            url,
            dest,
            progress_callback=lambda d, t: self.progress.emit(d, t),
            cancel_flag=lambda: self._cancel_download,
        )
        self.download_finished.emit(ok, dest)

    def cancel(self):
        self._cancel_download = True


class UpdateDialog(QDialog):
    """Minimalist, professional dark-themed update dialog matching Senti's design language."""

    def __init__(self, update_info: Dict[str, Any], current_version: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.update_info = update_info
        self.current_version = current_version
        self._download_worker: Optional[UpdateWorker] = None
        self._downloaded_file: Optional[str] = None

        self.setWindowTitle("SYS-SENTINEL // UPDATE")
        self.setFixedSize(400, 260)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Outer Container Frame
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #090b10;
                border: 1px solid #1a2230;
                border-radius: 8px;
            }
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        # Title Row
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        dot_lbl = QLabel("●")
        dot_lbl.setStyleSheet("color: #38bdf8; font-size: 9px; border: none; background: transparent;")
        top_row.addWidget(dot_lbl)

        title_lbl = QLabel("SYS-SENTINEL UPDATE")
        title_lbl.setStyleSheet("color: #e2e8f0; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; border: none; background: transparent;")
        top_row.addWidget(title_lbl)

        top_row.addStretch()

        # Minimalist Version Badge
        raw_target = self.update_info.get("version", "")
        target_ver = raw_target if raw_target.startswith("v") else f"v{raw_target}"
        curr_ver = f"v{self.current_version}" if not self.current_version.startswith("v") else self.current_version
        ver_pill = QLabel(f"{curr_ver}  →  {target_ver}")
        ver_pill.setStyleSheet("""
            background: #0e1626;
            color: #38bdf8;
            font-family: 'Consolas', monospace;
            font-size: 9px;
            font-weight: 600;
            padding: 2px 8px;
            border: 1px solid #1e293b;
            border-radius: 4px;
        """)
        top_row.addWidget(ver_pill)
        lay.addLayout(top_row)

        # Hairline Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #141a24; border: none;")
        lay.addWidget(div)

        # Notes Label
        lbl_notes = QLabel("RELEASE NOTES")
        lbl_notes.setStyleSheet("color: #64748b; font-size: 8.5px; font-weight: 700; letter-spacing: 0.6px; border: none; background: transparent;")
        lay.addWidget(lbl_notes)

        # Release Notes Text Box
        notes_box = QTextEdit()
        notes_box.setReadOnly(True)
        notes_box.setFixedHeight(85)
        notes_box.setPlainText(self.update_info.get("notes", "Performance optimizations and stability improvements."))
        notes_box.setStyleSheet("""
            QTextEdit {
                background: #07080c;
                color: #94a3b8;
                font-size: 10px;
                border: 1px solid #141a24;
                border-radius: 4px;
                padding: 6px;
                font-family: 'Consolas', 'Segoe UI', sans-serif;
                line-height: 135%;
            }
        """)
        lay.addWidget(notes_box)

        # Progress Bar (hidden until downloading)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #111622;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 2px;
            }
        """)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        # Status text
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 9.5px; font-family: 'Consolas', monospace; border: none; background: transparent;")
        self.lbl_status.setVisible(False)
        lay.addWidget(self.lbl_status)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_cancel = QPushButton("LATER")
        self.btn_cancel.setFixedHeight(24)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #0d1017;
                color: #64748b;
                font-size: 9.5px;
                font-weight: 700;
                letter-spacing: 0.5px;
                border: 1px solid #1a202c;
                border-radius: 4px;
                padding: 0px 12px;
            }
            QPushButton:hover {
                background: #121722;
                color: #cbd5e1;
                border: 1px solid #2d3748;
            }
            QPushButton:pressed {
                background: #080a0f;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        btn_row.addStretch()

        self.btn_update = QPushButton("UPDATE NOW")
        self.btn_update.setFixedHeight(24)
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background: #0c2130;
                color: #38bdf8;
                font-size: 9.5px;
                font-weight: 700;
                letter-spacing: 0.5px;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 0px 14px;
            }
            QPushButton:hover {
                background: #0f2b3f;
                color: #7dd3fc;
                border: 1px solid #38bdf8;
            }
            QPushButton:pressed {
                background: #071520;
            }
        """)
        self.btn_update.clicked.connect(self._start_download)
        btn_row.addWidget(self.btn_update)

        lay.addLayout(btn_row)
        main_layout.addWidget(frame)

    def _start_download(self):
        self.btn_update.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Connecting to server...")

        self._download_worker = UpdateWorker(self.current_version)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.download_finished.connect(self._on_download_finished)

        url = self.update_info["download_url"]
        threading.Thread(target=self._download_worker.run_download, args=(url,), daemon=True).start()

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            mb_down = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.lbl_status.setText(f"Downloading update: {mb_down:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
        else:
            mb_down = downloaded / (1024 * 1024)
            self.lbl_status.setText(f"Downloading update: {mb_down:.1f} MB...")

    def _on_download_finished(self, success: bool, file_path: str):
        if not success:
            self.lbl_status.setText("❌ Download failed. Please try again later.")
            self.btn_update.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            return

        self._downloaded_file = file_path
        self.lbl_status.setText("✅ Download complete! Restarting SYS-SENTINEL...")
        self.progress_bar.setValue(100)

        # Allow 1 second for user to see the success state, then apply update
        QTimer.singleShot(1200, self._apply_and_close)

    def _apply_and_close(self):
        if self._downloaded_file:
            apply_update_and_restart(self._downloaded_file)
        self.accept()


class UpToDateDialog(QDialog):
    """Minimalist dark-themed notification indicating the app is already on the latest version."""

    def __init__(self, current_version: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_version = current_version
        self.setWindowTitle("SYS-SENTINEL // STATUS")
        self.setFixedSize(340, 150)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #090b10;
                border: 1px solid #1a2230;
                border-radius: 8px;
            }
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        # Header
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        dot_lbl = QLabel("●")
        dot_lbl.setStyleSheet("color: #22c55e; font-size: 9px; border: none; background: transparent;")
        top_row.addWidget(dot_lbl)

        title_lbl = QLabel("SYS-SENTINEL UP TO DATE")
        title_lbl.setStyleSheet("color: #e2e8f0; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; border: none; background: transparent;")
        top_row.addWidget(title_lbl)
        top_row.addStretch()
        lay.addLayout(top_row)

        # Hairline Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #141a24; border: none;")
        lay.addWidget(div)

        # Message
        msg_lbl = QLabel(f"Version v{self.current_version} is the latest release.\nNo updates are needed at this time.")
        msg_lbl.setStyleSheet("color: #94a3b8; font-size: 9.5px; border: none; background: transparent; line-height: 135%;")
        lay.addWidget(msg_lbl)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.setFixedHeight(22)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet("""
            QPushButton {
                background: #0d1017;
                color: #64748b;
                font-size: 9.5px;
                font-weight: 700;
                border: 1px solid #1a202c;
                border-radius: 3px;
                padding: 0px 16px;
            }
            QPushButton:hover {
                background: #121722;
                color: #cbd5e1;
                border: 1px solid #2d3748;
            }
        """)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

        main_layout.addWidget(frame)

