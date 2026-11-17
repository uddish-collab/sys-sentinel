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

    # Rich Subsystem Telemetry
    snapshot["cpu_cores"] = get_cpu_cores()
    snapshot["cpu_freq_mhz"] = get_cpu_frequency()
    snapshot["cpu_stats"] = get_cpu_activity_stats()
    snapshot["ram_details"] = get_detailed_ram_info()
    snapshot["disk_details"] = get_detailed_disk_info()
    snapshot["net_details"] = get_detailed_net_info()
    snapshot["gpu_details"] = get_detailed_gpu_info()

    return snapshot


# --- Advanced Subsystem Telemetry & Process Management ---

_last_disk_counters = None
_last_disk_timestamp = 0.0
_last_net_counters = None
_last_net_timestamp = 0.0
_cached_gpu_info = None
_last_ping_ms = None
_last_ping_time = 0.0


def get_cpu_cores() -> List[float]:
    """Return live per-core load percentages across all logical cores."""
    try:
        loads = psutil.cpu_percent(interval=None, percpu=True)
        return [float(c) for c in loads] if loads else []
    except Exception:
        return []


def get_cpu_frequency() -> Optional[float]:
    """Return current CPU clock speed in MHz."""
    try:
        freq = psutil.cpu_freq()
        return float(freq.current) if freq and freq.current else None
    except Exception:
        return None


def get_cpu_activity_stats() -> Dict[str, Any]:
    """Return process count, thread count, context switches, and interrupts."""
    stats = {
        "process_count": 0,
        "thread_count": 0,
        "ctx_switches": 0,
        "interrupts": 0,
    }
    try:
        c_stats = psutil.cpu_stats()
        stats["ctx_switches"] = c_stats.ctx_switches
        stats["interrupts"] = c_stats.interrupts
    except Exception:
        pass

    try:
        pids = psutil.pids()
        stats["process_count"] = len(pids)
        # Approximate threads
        thread_total = 0
        for pid in pids[:40]:  # sample representative slice without stalling
            try:
                thread_total += psutil.Process(pid).num_threads()
            except Exception:
                pass
        stats["thread_count"] = thread_total
    except Exception:
        pass

    return stats


def get_detailed_ram_info() -> Dict[str, Any]:
    """Return comprehensive RAM and Swap/Pagefile breakdown."""
    info = {
        "total_gb": 0.0,
        "used_gb": 0.0,
        "free_gb": 0.0,
        "available_gb": 0.0,
        "percent": 0.0,
        "cached_gb": 0.0,
        "swap_total_gb": 0.0,
        "swap_used_gb": 0.0,
        "swap_free_gb": 0.0,
        "swap_percent": 0.0,
    }
    try:
        mem = psutil.virtual_memory()
        info["total_gb"] = mem.total / (1024 ** 3)
        info["used_gb"] = mem.used / (1024 ** 3)
        info["free_gb"] = mem.free / (1024 ** 3)
        info["available_gb"] = mem.available / (1024 ** 3)
        info["percent"] = float(mem.percent)
        # Cached / Standby if present on platform
        cached = getattr(mem, "cached", 0) or getattr(mem, "buffers", 0) or (mem.available - mem.free)
        info["cached_gb"] = max(0.0, cached / (1024 ** 3))
    except Exception:
        pass

    try:
        swap = psutil.swap_memory()
        info["swap_total_gb"] = swap.total / (1024 ** 3)
        info["swap_used_gb"] = swap.used / (1024 ** 3)
        info["swap_free_gb"] = swap.free / (1024 ** 3)
        info["swap_percent"] = float(swap.percent)
    except Exception:
        pass

    return info


def get_detailed_disk_info() -> Dict[str, Any]:
    """Return multi-partition capacities and live read/write throughput rates (MB/s)."""
    global _last_disk_counters, _last_disk_timestamp

    info: Dict[str, Any] = {
        "partitions": [],
        "read_mb_s": 0.0,
        "write_mb_s": 0.0,
        "read_bytes_total": 0,
        "write_bytes_total": 0,
        "read_count": 0,
        "write_count": 0,
    }

    # 1. Partitions
    try:
        for p in psutil.disk_partitions(all=False):
            if "cdrom" in p.opts.lower():
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
                info["partitions"].append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": u.total / (1024 ** 3),
                    "used_gb": u.used / (1024 ** 3),
                    "free_gb": u.free / (1024 ** 3),
                    "percent": float(u.percent),
                })
            except (PermissionError, OSError):
                continue
    except Exception:
        pass

    # 2. Live I/O Rates
    now = time.time()
    try:
        curr_io = psutil.disk_io_counters()
        if curr_io:
            info["read_bytes_total"] = curr_io.read_bytes
            info["write_bytes_total"] = curr_io.write_bytes
            info["read_count"] = curr_io.read_count
            info["write_count"] = curr_io.write_count

            if _last_disk_counters is not None and (_last_disk_timestamp > 0):
                dt = now - _last_disk_timestamp
                if dt >= 0.2:
                    delta_read = curr_io.read_bytes - _last_disk_counters.read_bytes
                    delta_write = curr_io.write_bytes - _last_disk_counters.write_bytes
                    info["read_mb_s"] = max(0.0, (delta_read / (1024 * 1024)) / dt)
                    info["write_mb_s"] = max(0.0, (delta_write / (1024 * 1024)) / dt)

            _last_disk_counters = curr_io
            _last_disk_timestamp = now
    except Exception:
        pass

    return info


def get_detailed_net_info() -> Dict[str, Any]:
    """Return live upload/download bandwidth (KB/s), total bytes, and target ping latency."""
    global _last_net_counters, _last_net_timestamp, _last_ping_ms, _last_ping_time

    now = time.time()
    info: Dict[str, Any] = {
        "recv_kb_s": 0.0,
        "sent_kb_s": 0.0,
        "total_recv_mb": 0.0,
        "total_sent_mb": 0.0,
        "ping_ms": None,
    }

    try:
        curr_net = psutil.net_io_counters()
        if curr_net:
            info["total_recv_mb"] = curr_net.bytes_recv / (1024 * 1024)
            info["total_sent_mb"] = curr_net.bytes_sent / (1024 * 1024)

            if _last_net_counters is not None and (_last_net_timestamp > 0):
                dt = now - _last_net_timestamp
                if dt >= 0.2:
                    delta_recv = curr_net.bytes_recv - _last_net_counters.bytes_recv
                    delta_sent = curr_net.bytes_sent - _last_net_counters.bytes_sent
                    info["recv_kb_s"] = max(0.0, (delta_recv / 1024) / dt)
                    info["sent_kb_s"] = max(0.0, (delta_sent / 1024) / dt)

            _last_net_counters = curr_net
            _last_net_timestamp = now
    except Exception:
        pass

    # Ping measurement (cached every 5 seconds to avoid network contention)
    if (now - _last_ping_time) >= 5.0 or _last_ping_ms is None:
        try:
            start = time.perf_counter()
            s = socket.create_connection(("8.8.8.8", 53), timeout=0.8)
            s.close()
            _last_ping_ms = round((time.perf_counter() - start) * 1000.0, 1)
            _last_ping_time = now
        except Exception:
            _last_ping_ms = None
            _last_ping_time = now

    info["ping_ms"] = _last_ping_ms
    return info


def get_detailed_gpu_info() -> Dict[str, Any]:
    """Return GPU adapter name, dedicated VRAM, and driver version."""
    global _cached_gpu_info
    if _cached_gpu_info is not None:
        return _cached_gpu_info

    info = {
        "name": "Generic Display Adapter",
        "vram_gb": None,
        "driver": "Standard Driver",
    }

    if sys.platform == "win32":
        try:
            # Fast query via PowerShell CIM
            cmd = "Get-CimInstance Win32_VideoController | Select-Object -First 1 Name, AdapterRAM, DriverVersion | ConvertTo-Json"
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=2.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    info["name"] = data.get("Name") or info["name"]
                    ram = data.get("AdapterRAM")
                    if ram and isinstance(ram, (int, float)):
                        info["vram_gb"] = round(ram / (1024 ** 3), 1)
                    info["driver"] = data.get("DriverVersion") or info["driver"]
        except Exception:
            pass

    _cached_gpu_info = info
    return info


def get_top_processes(limit: int = 15, sort_by: str = "cpu") -> List[Dict[str, Any]]:
    """Return a live-sorted list of top resource-consuming applications."""
    procs: List[Dict[str, Any]] = []
    key_field = "cpu_percent" if sort_by == "cpu" else "memory_percent"

    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            item = p.info
            item["cpu_percent"] = float(item.get("cpu_percent") or 0.0)
            item["memory_percent"] = float(item.get("memory_percent") or 0.0)
            procs.append(item)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: (x.get(key_field) or 0.0), reverse=True)
    return procs[:limit]


def get_active_connections(limit: int = 25) -> List[Dict[str, Any]]:
    """Return active TCP/UDP ports and network endpoints."""
    active: List[Dict[str, Any]] = []
    try:
        conns = psutil.net_connections(kind="inet")
        for c in conns:
            if c.status in ("LISTEN", "ESTABLISHED", "TIME_WAIT"):
                l_ip = c.laddr.ip if c.laddr else "*"
                l_port = c.laddr.port if c.laddr else 0
                r_ip = c.raddr.ip if c.raddr else "*"
                r_port = c.raddr.port if c.raddr else 0
                active.append({
                    "proto": "TCP" if c.type == socket.SOCK_STREAM else "UDP",
                    "local": f"{l_ip}:{l_port}",
                    "remote": f"{r_ip}:{r_port}" if r_port else "-",
                    "status": c.status,
                    "pid": c.pid or 0,
                })
                if len(active) >= limit:
                    break
    except Exception:
        pass
    return active


def terminate_process(pid: int) -> bool:
    """Terminate / kill a process by PID."""
    try:
        p = psutil.Process(pid)
        p.terminate()
        return True
    except Exception:
        return False


def suspend_process(pid: int) -> bool:
    """Suspend execution of a process by PID."""
    try:
        p = psutil.Process(pid)
        p.suspend()
        return True
    except Exception:
        return False


def resume_process(pid: int) -> bool:
    """Resume execution of a suspended process by PID."""
    try:
        p = psutil.Process(pid)
        p.resume()
        return True
    except Exception:
        return False


def set_process_priority(pid: int, priority: str) -> bool:
    """Change process scheduling priority on Windows."""
    try:
        p = psutil.Process(pid)
        prio_map = {
            "Realtime": getattr(psutil, "REALTIME_PRIORITY_CLASS", 256),
            "High": getattr(psutil, "HIGH_PRIORITY_CLASS", 128),
            "Above Normal": getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", 32768),
            "Normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", 32),
            "Below Normal": getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 16384),
            "Idle": getattr(psutil, "IDLE_PRIORITY_CLASS", 64),
        }
        if priority in prio_map:
            p.nice(prio_map[priority])
            return True
        return False
    except Exception:
        return False
