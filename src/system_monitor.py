"""System hardware monitoring and background temperature reader for SYS-SENTINEL.

Handles Windows 10/11 telemetry safely without blocking the UI.
"""

import os
import re
import socket
import subprocess
import sys
import threading
import time
from typing import Optional, List, Dict, Any

import psutil

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore


# Sane temperature bounds in Celsius
MIN_SANE_TEMP_C = 1.0
MAX_SANE_TEMP_C = 125.0


def parse_temperature_output(output: str, mode: str = "kelvin") -> Optional[float]:
    """Parse raw PowerShell CIM output and return the highest sane Celsius value, or None.
    
    Modes:
      - 'kelvin': Integer/float in Kelvin (e.g., 310 K -> 36.85 °C)
      - 'tenths': Integer/float in tenths of a Kelvin (e.g., 3102 -> 37.05 °C)
    """
    if not output or not output.strip():
        return None

    # Find all numeric tokens in the output
    tokens = re.findall(r"\b\d+(?:\.\d+)?\b", output)
    sane_celsius_readings: List[float] = []

    for tok in tokens:
        try:
            val = float(tok)
        except ValueError:
            continue

        if mode == "kelvin":
            temp_c = val - 273.15
        elif mode == "tenths":
            temp_c = (val / 10.0) - 273.15
        else:
            temp_c = val

        if MIN_SANE_TEMP_C <= temp_c <= MAX_SANE_TEMP_C:
            sane_celsius_readings.append(temp_c)

    if sane_celsius_readings:
        return max(sane_celsius_readings)

    return None


class TemperatureMonitor:
    """Background thread that queries Windows ACPI / Thermal Zone sensors.
    
    - Polls every 5s, backing off to 60s after 3 consecutive failures.
    - Caches the last valid temperature for up to 20 seconds.
    - Rejects nonsensical readings outside 1-125 °C.
    - Runs completely off the Qt main thread.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last_temp: Optional[float] = None
        self._last_time: float = 0.0
        self._failure_count: int = 0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="SentiTemperatureMonitor",
                daemon=True,
            )
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def get_temperature(self) -> Optional[float]:
        """Return the last valid temperature if fresher than 20 seconds, else None."""
        with self._lock:
            if self._last_temp is not None:
                if (time.time() - self._last_time) <= 20.0:
                    return self._last_temp
            return None

    def _query_powershell(self, command: str) -> Optional[str]:
        """Execute a PowerShell command silently with a strict timeout and no window."""
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=4.0,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                return result.stdout
        except (subprocess.TimeoutExpired, OSError, Exception):
            pass

        return None

    def _poll_once(self) -> Optional[float]:
        # Try primary query: Win32_PerfFormattedData_Counters_ThermalZoneInformation (Kelvin)
        cmd_primary = (
            "Get-CimInstance -ClassName Win32_PerfFormattedData_Counters_ThermalZoneInformation "
            "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty Temperature"
        )
        out = self._query_powershell(cmd_primary)
        temp = parse_temperature_output(out, mode="kelvin") if out else None

        if temp is not None:
            return temp

        # Fallback query: root/wmi MSAcpi_ThermalZoneTemperature (tenths of Kelvin)
        cmd_fallback = (
            "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
            "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty CurrentTemperature"
        )
        out_fallback = self._query_powershell(cmd_fallback)
        if out_fallback:
            temp = parse_temperature_output(out_fallback, mode="tenths")
            if temp is not None:
                return temp

        return None

    def _worker_loop(self):
        while not self._stop_event.is_set():
            reading = self._poll_once()

            if reading is not None:
                with self._lock:
                    self._last_temp = reading
                    self._last_time = time.time()
                    self._failure_count = 0
                sleep_time = 5.0
            else:
                with self._lock:
                    self._failure_count += 1
                    failures = self._failure_count
                sleep_time = 60.0 if failures >= 3 else 5.0

            # Wait in small intervals so we can exit cleanly
            steps = int(sleep_time * 2)
            for _ in range(steps):
                if self._stop_event.is_set():
                    break
                time.sleep(0.5)


# Global singleton instance of TemperatureMonitor
_temp_monitor: Optional[TemperatureMonitor] = None


def get_temperature_monitor() -> TemperatureMonitor:
    global _temp_monitor
    if _temp_monitor is None:
        _temp_monitor = TemperatureMonitor()
        _temp_monitor.start()
    return _temp_monitor


def get_processor_name() -> str:
    """Read readable CPU name from Windows registry, falling back to platform/processor."""
    if sys.platform == "win32" and winreg:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            if val and val.strip():
                return val.strip()
        except OSError:
            pass

    import platform
    proc = platform.processor()
    return proc if proc else "Unknown CPU"


def get_os_display_name() -> str:
    """Determine OS version: Windows 11 if build >= 22000, else Windows 10."""
    if sys.platform == "win32":
        try:
            win_ver = sys.getwindowsversion()
            build = getattr(win_ver, "build", 0)
            if build >= 22000:
                return f"Windows 11 (Build {build})"
            return f"Windows 10 (Build {build})"
        except Exception:
            pass
    import platform
    return f"{platform.system()} {platform.release()}"


def get_system_drive() -> str:
    """Return the system drive root, e.g. 'C:\\', dynamically derived from %SystemDrive%."""
    sys_drive = os.environ.get("SystemDrive")
    if sys_drive:
        return sys_drive if sys_drive.endswith("\\") else f"{sys_drive}\\"
    return "C:\\"


def get_system_info(temp_monitor: Optional[TemperatureMonitor] = None) -> Dict[str, Any]:
    """Capture a comprehensive live snapshot of system metrics.
    
    Any failed metric safely becomes None (never crashes or shows fake 0).
    """
    snapshot: Dict[str, Any] = {
        "cpu": None,
        "ram": None,
        "ram_used_gb": None,
        "ram_total_gb": None,
        "disk": None,
        "disk_used_gb": None,
        "disk_free_gb": None,
        "disk_total_gb": None,
        "system_drive": get_system_drive(),
        "temperature_c": None,
        "battery": None,
        "battery_plugged": None,
        "hostname": "Unknown",
        "os": get_os_display_name(),
        "processor": get_processor_name(),
        "logical_cores": 0,
        "uptime_seconds": 0,
    }

    # CPU
    try:
        cpu_val = psutil.cpu_percent(interval=None)
        snapshot["cpu"] = float(cpu_val)
    except Exception:
        snapshot["cpu"] = None

    # RAM
    try:
        mem = psutil.virtual_memory()
        snapshot["ram"] = float(mem.percent)
        snapshot["ram_used_gb"] = mem.used / (1024 ** 3)
        snapshot["ram_total_gb"] = mem.total / (1024 ** 3)
    except Exception:
        pass

    # Disk (System Drive)
    try:
        drive_path = snapshot["system_drive"]
        disk = psutil.disk_usage(drive_path)
        snapshot["disk"] = float(disk.percent)
        snapshot["disk_used_gb"] = disk.used / (1024 ** 3)
        snapshot["disk_free_gb"] = disk.free / (1024 ** 3)
        snapshot["disk_total_gb"] = disk.total / (1024 ** 3)
    except Exception:
        pass

    # Temperature
    if temp_monitor is None:
        try:
            temp_monitor = get_temperature_monitor()
        except Exception:
            temp_monitor = None

    if temp_monitor:
        snapshot["temperature_c"] = temp_monitor.get_temperature()

    # Battery
    try:
        battery = psutil.sensors_battery()
        if battery:
            snapshot["battery"] = float(battery.percent)
            snapshot["battery_plugged"] = bool(battery.power_plugged)
    except Exception:
        pass

    # Hostname
    try:
        snapshot["hostname"] = socket.gethostname()
    except Exception:
        pass

    # Cores
    try:
        snapshot["logical_cores"] = psutil.cpu_count(logical=True) or 0
    except Exception:
        pass

    # Uptime
    try:
        boot = psutil.boot_time()
        snapshot["uptime_seconds"] = max(0, int(time.time() - boot))
    except Exception:
        pass

    return snapshot
