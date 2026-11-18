"""Pure Python state, history, thresholds, and formatting for Sentinel.

No Qt dependencies in this module so it can be thoroughly unit-tested.
"""

from collections import deque
from typing import Optional, List, Tuple, Dict, Any
import time


# Thresholds: (warning, critical)
CPU_THRESHOLDS = (65.0, 85.0)
RAM_THRESHOLDS = (65.0, 85.0)
DISK_THRESHOLDS = (90.0, 95.0)
TEMP_THRESHOLDS = (75.0, 85.0)

# Status labels
STATUS_NORMAL = "NORMAL"
STATUS_WARNING = "WARNING"
STATUS_CRITICAL = "CRITICAL"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_CHECKING = "CHECKING"

# Moods
MOOD_CALM = "calm"
MOOD_WARNING = "warning"
MOOD_CRITICAL = "critical"

# Rank for escalation comparison
MOOD_RANK = {
    MOOD_CALM: 0,
    MOOD_WARNING: 1,
    MOOD_CRITICAL: 2,
}


def get_metric_status(value: Optional[float], warn: float, crit: float) -> str:
    """Return the status string for a metric value."""
    if value is None:
        return STATUS_UNAVAILABLE
    if value >= crit:
        return STATUS_CRITICAL
    if value >= warn:
        return STATUS_WARNING
    return STATUS_NORMAL


def evaluate_raw_mood(
    cpu: Optional[float],
    ram: Optional[float],
    disk: Optional[float],
    temp: Optional[float],
) -> str:
    """Evaluate mood for a single set of metric values.
    
    Missing values (None) count as normal.
    """
    # Critical check first
    if (cpu is not None and cpu >= CPU_THRESHOLDS[1]) or \
       (ram is not None and ram >= RAM_THRESHOLDS[1]) or \
       (disk is not None and disk >= DISK_THRESHOLDS[1]) or \
       (temp is not None and temp >= TEMP_THRESHOLDS[1]):
        return MOOD_CRITICAL

    # Warning check
    if (cpu is not None and cpu >= CPU_THRESHOLDS[0]) or \
       (ram is not None and ram >= RAM_THRESHOLDS[0]) or \
       (disk is not None and disk >= DISK_THRESHOLDS[0]) or \
       (temp is not None and temp >= TEMP_THRESHOLDS[0]):
        return MOOD_WARNING

    return MOOD_CALM


class StateTracker:
    """Tracks system metrics and determines SENTI's mood with smoothing and hysteresis.
    
    Rules:
    - Moving average of the last 3 samples for each metric (missing values ignored in average).
    - Escalate immediately if the moving average triggers a higher mood.
    - Relax to a lower mood only after 4 consecutive samples indicating the lower state.
    """

    def __init__(self, window_size: int = 3, relax_delay: int = 4):
        self.window_size = window_size
        self.relax_delay = relax_delay

        self._cpu_samples: deque = deque(maxlen=window_size)
        self._ram_samples: deque = deque(maxlen=window_size)
        self._disk_samples: deque = deque(maxlen=window_size)
        self._temp_samples: deque = deque(maxlen=window_size)

        self.current_mood: str = MOOD_CALM
        self._consecutive_relax_count: int = 0
        self._pending_lower_mood: Optional[str] = None

    def _avg(self, samples: deque) -> Optional[float]:
        valid = [s for s in samples if s is not None]
        if not valid:
            return None
        return sum(valid) / len(valid)

    def update(
        self,
        cpu: Optional[float],
        ram: Optional[float],
        disk: Optional[float],
        temp: Optional[float],
    ) -> str:
        """Add a new sample and return the updated mood."""
        self._cpu_samples.append(cpu)
        self._ram_samples.append(ram)
        self._disk_samples.append(disk)
        self._temp_samples.append(temp)

        # Compute moving averages
        avg_cpu = self._avg(self._cpu_samples)
        avg_ram = self._avg(self._ram_samples)
        avg_disk = self._avg(self._disk_samples)
        avg_temp = self._avg(self._temp_samples)

        target_mood = evaluate_raw_mood(avg_cpu, avg_ram, avg_disk, avg_temp)

        curr_rank = MOOD_RANK[self.current_mood]
        target_rank = MOOD_RANK[target_mood]

        if target_rank > curr_rank:
            # Immediate escalation!
            self.current_mood = target_mood
            self._consecutive_relax_count = 0
            self._pending_lower_mood = None
        elif target_rank < curr_rank:
            # Hysteresis: require relax_delay consecutive lower samples
            if self._pending_lower_mood == target_mood:
                self._consecutive_relax_count += 1
            else:
                self._pending_lower_mood = target_mood
                self._consecutive_relax_count = 1

            if self._consecutive_relax_count >= self.relax_delay:
                self.current_mood = target_mood
                self._consecutive_relax_count = 0
                self._pending_lower_mood = None
        else:
            # Same mood, reset relax counter
            self._consecutive_relax_count = 0
            self._pending_lower_mood = None

        return self.current_mood

    def reset(self):
        self._cpu_samples.clear()
        self._ram_samples.clear()
        self._disk_samples.clear()
        self._temp_samples.clear()
        self.current_mood = MOOD_CALM
        self._consecutive_relax_count = 0
        self._pending_lower_mood = None


class MetricHistory:
    """Rolling history of timestamped metric samples (up to 900 samples, ~15 mins at 1/sec)."""

    def __init__(self, maxlen: int = 900):
        self.maxlen = maxlen
        # Stores tuples of (timestamp_seconds, Optional[float])
        self.samples: deque = deque(maxlen=maxlen)

    def append(self, value: Optional[float], timestamp: Optional[float] = None):
        if timestamp is None:
            timestamp = time.time()
        self.samples.append((timestamp, value))

    def get_range(self, duration_seconds: float, now: Optional[float] = None) -> List[Tuple[float, Optional[float]]]:
        """Return samples within the last duration_seconds, relative to `now`."""
        if now is None:
            now = time.time()
        cutoff = now - duration_seconds
        return [(ts, val) for ts, val in self.samples if ts >= cutoff]

    def stats(self, duration_seconds: float, now: Optional[float] = None) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate (current, average, peak) for the given duration window.
        
        Ignores None values. Returns (None, None, None) if no valid data points exist.
        """
        window = self.get_range(duration_seconds, now)
        valid_vals = [val for _, val in window if val is not None]

        current = valid_vals[-1] if valid_vals else None
        avg = (sum(valid_vals) / len(valid_vals)) if valid_vals else None
        peak = max(valid_vals) if valid_vals else None

        return current, avg, peak


# ---------- FORMATTING HELPERS ----------

def format_uptime(seconds: int) -> str:
    """Format uptime seconds into 'Xd Xh Xm' or 'Xh Xm'."""
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"


def format_gb(val: Optional[float]) -> str:
    """Format GB to 1 decimal place or 'Unavailable'."""
    if val is None:
        return "Unavailable"
    return f"{val:.1f} GB"


def format_percent(val: Optional[float]) -> str:
    """Format percentage to 0 decimal places or 'Unavailable'."""
    if val is None:
        return "Unavailable"
    return f"{val:.0f}%"


def format_temp(val: Optional[float]) -> str:
    """Format temperature in Celsius or 'Unavailable'."""
    if val is None:
        return "Unavailable"
    return f"{val:.0f} °C"
