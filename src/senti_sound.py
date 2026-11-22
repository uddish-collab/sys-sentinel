"""Polyphonic multi-channel sound engine for Sentinel.

Provides:
- Multi-channel zero-latency polyphony: Overlapping sounds decay naturally without cutting off.
- 100% Maximum Volume: Crisp, punchy feedback across all channels.
- Multi-voice round-robin pooling: Rapid repetitive clicks never drop a transient.
- Dynamic Pitch Modulation: Tuned crystalline glass harmonics for the 8 island subsystem pills.
- Hybrid Audio: Blends tactile luxury glass mechanics with expressive Senti character vocalizations.
- Pure standard fallback: Graceful multi-threaded playback if QtMultimedia is unavailable.
"""

import math
import os
import struct
import sys
import threading
import wave
from typing import Dict, List, Optional, Any

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect
    from PySide6.QtWidgets import QApplication
    HAS_QT_AUDIO = True
except Exception:
    HAS_QT_AUDIO = False


# Core Active Sound Names
MOCHI_SOUND_NAMES = [
    "annoyed", "approval", "attach", "blip", "close", "dizzy", "greeting",
    "hover", "love", "open", "pop", "tick", "wink", "work",
]

LEGACY_SOUND_NAMES = ["click", "open", "close", "shrink", "restore", "show", "hide", "dock"]

# Tuned hover and tick names for 8-pill dynamic pitch modulation
PITCH_HOVER_NAMES = [f"hover_{i}" for i in range(8)]
PITCH_TICK_NAMES = [f"tick_{i}" for i in range(8)]

SOUND_NAMES = list(set(MOCHI_SOUND_NAMES + LEGACY_SOUND_NAMES + PITCH_HOVER_NAMES + PITCH_TICK_NAMES))

SOUND_ALIASES = {
    "click": "blip",
    "dock": "attach",
    "show": "open",
    "hide": "close",
    "shrink": "close",
    "restore": "open",
}

# 8-Pill Crystal Glass Harmonics Scale (G5 major hexatonic/pentatonic extension)
# Clean, modern, luxury marimba feel when gliding across the island pills:
# CPU (0) -> RAM (1) -> GPU (2) -> NET (3) -> DISK (4) -> TEMP (5) -> SYS (6) -> SET (7)
PILL_SCALE_FREQUENCIES = [
    783.99,   # 0: CPU  (G5)
    880.00,   # 1: RAM  (A5)
    987.77,   # 2: GPU  (B5)
    1046.50,  # 3: NET  (C6)
    1174.66,  # 4: DISK (D6)
    1318.51,  # 5: TEMP (E6)
    1479.98,  # 6: SYS  (F#6)
    1567.98,  # 7: SET  (G6)
]


def get_sound_dir() -> str:
    """Return %LOCALAPPDATA%\\Sentinel\\sounds."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.expanduser("~")
    sound_dir = os.path.join(local_app_data, "Sentinel", "sounds")
    os.makedirs(sound_dir, exist_ok=True)
    return sound_dir


def get_bundled_sound_dir() -> str:
    """Return path to bundled assets/sounds folder."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", "sounds")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "assets", "sounds")


def synthesize_tone(
    frequencies: List[float],
    duration_s: float,
    attack_s: float = 0.01,
    decay_rate: float = 18.0,
    peak_amplitude: float = 0.55,
    sample_rate: int = 44100,
) -> bytes:
    """Generate 16-bit mono PCM bytes for a soft tone with harmonics and envelope."""
    num_samples = int(sample_rate * duration_s)
    attack_samples = max(1, int(sample_rate * attack_s))
    raw_data = bytearray()

    for i in range(num_samples):
        t = i / sample_rate
        if i < attack_samples:
            env = i / attack_samples
        else:
            env = math.exp(-decay_rate * (t - attack_s))

        sample_val = 0.0
        for f in frequencies:
            sample_val += math.sin(2.0 * math.pi * f * t)
            sample_val += 0.20 * math.sin(4.0 * math.pi * f * t)

        sample_val = (sample_val / len(frequencies)) * env * peak_amplitude
        sample_val = max(-1.0, min(1.0, sample_val))
        int_sample = int(sample_val * 32767.0)
        raw_data.extend(struct.pack("<h", int_sample))

    return bytes(raw_data)


def synthesize_glass_tone(
    fundamental_hz: float,
    duration_s: float = 0.040,
    attack_s: float = 0.003,
    decay_rate: float = 38.0,
    peak_amplitude: float = 0.58,
    sample_rate: int = 44100,
) -> bytes:
    """Synthesize crisp, luxury glass marimba tone with crystalline harmonics."""
    num_samples = int(sample_rate * duration_s)
    attack_samples = max(1, int(sample_rate * attack_s))
    raw_data = bytearray()

    for i in range(num_samples):
        t = i / sample_rate
        if i < attack_samples:
            env = i / attack_samples
        else:
            env = math.exp(-decay_rate * (t - attack_s))

        # Fundamental + glass harmonics (2x octave + 2.76x crystalline glass bell overtone)
        sample_val = (
            math.sin(2.0 * math.pi * fundamental_hz * t)
            + 0.28 * math.sin(4.0 * math.pi * fundamental_hz * t)
            + 0.15 * math.sin(2.0 * math.pi * fundamental_hz * 2.76 * t)
        )
        sample_val = (sample_val / 1.43) * env * peak_amplitude
        sample_val = max(-1.0, min(1.0, sample_val))
        int_sample = int(sample_val * 32767.0)
        raw_data.extend(struct.pack("<h", int_sample))

    return bytes(raw_data)


def write_wav_file(file_path: str, pcm_bytes: bytes, sample_rate: int = 44100):
    """Write raw 16-bit mono PCM bytes to a WAV file."""
    with wave.open(file_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def generate_sound_specs() -> Dict[str, bytes]:
    """Define tone recipes for interaction sounds."""
    specs = {}

    # 1. Click: subtle, gentle high-pitch pop (40 ms)
    specs["click"] = synthesize_tone([750.0], duration_s=0.04, attack_s=0.005, decay_rate=45.0, peak_amplitude=0.45)

    # 2. Open: ascending warm two-tone chime (130 ms)
    pcm1 = synthesize_tone([480.0], duration_s=0.065, attack_s=0.008, decay_rate=22.0, peak_amplitude=0.40)
    pcm2 = synthesize_tone([680.0], duration_s=0.085, attack_s=0.008, decay_rate=18.0, peak_amplitude=0.42)
    specs["open"] = pcm1 + pcm2

    # 3. Close: descending soft chime (130 ms)
    pcm_c1 = synthesize_tone([640.0], duration_s=0.065, attack_s=0.008, decay_rate=22.0, peak_amplitude=0.40)
    pcm_c2 = synthesize_tone([440.0], duration_s=0.085, attack_s=0.008, decay_rate=18.0, peak_amplitude=0.42)
    specs["close"] = pcm_c1 + pcm_c2

    # 4. Shrink: swoosh downward (150 ms)
    pcm_s = bytearray()
    for freq in [700.0, 560.0, 420.0, 320.0]:
        pcm_s.extend(synthesize_tone([freq], duration_s=0.038, attack_s=0.006, decay_rate=24.0, peak_amplitude=0.38))
    specs["shrink"] = bytes(pcm_s)

    # 5. Restore: swoosh upward (150 ms)
    pcm_r = bytearray()
    for freq in [320.0, 440.0, 600.0, 780.0]:
        pcm_r.extend(synthesize_tone([freq], duration_s=0.038, attack_s=0.006, decay_rate=24.0, peak_amplitude=0.38))
    specs["restore"] = bytes(pcm_r)

    # 6. Show: bright welcoming chime (140 ms)
    specs["show"] = synthesize_tone([523.25, 784.0], duration_s=0.14, attack_s=0.01, decay_rate=16.0, peak_amplitude=0.40)

    # 7. Hide: soft settling chime (140 ms)
    specs["hide"] = synthesize_tone([440.0, 329.63], duration_s=0.14, attack_s=0.01, decay_rate=18.0, peak_amplitude=0.38)

    # 8. Dock: cute ascending 3-tone arpeggio (185 ms)
    pcm_d1 = synthesize_tone([587.33], duration_s=0.045, attack_s=0.005, decay_rate=24.0, peak_amplitude=0.38)
    pcm_d2 = synthesize_tone([783.99], duration_s=0.050, attack_s=0.005, decay_rate=22.0, peak_amplitude=0.42)
    pcm_d3 = synthesize_tone([1046.50], duration_s=0.090, attack_s=0.005, decay_rate=16.0, peak_amplitude=0.45)
    specs["dock"] = pcm_d1 + pcm_d2 + pcm_d3

    return specs


def ensure_sound_files() -> str:
    """Ensure all required WAV files exist on disk, copying bundled ones or synthesizing."""
    sound_dir = get_sound_dir()
    bundled_dir = get_bundled_sound_dir()

    # 1. Copy bundled Mochi sounds if available
    if os.path.isdir(bundled_dir):
        for f in os.listdir(bundled_dir):
            if f.endswith(".wav"):
                src_file = os.path.join(bundled_dir, f)
                dst_file = os.path.join(sound_dir, f)
                if not os.path.exists(dst_file):
                    try:
                        with open(src_file, "rb") as rf, open(dst_file, "wb") as wf:
                            wf.write(rf.read())
                    except Exception:
                        pass

    # 2. Synthesize fallback tones for any missing legacy names
    specs = generate_sound_specs()
    for name, pcm in specs.items():
        wav_path = os.path.join(sound_dir, f"{name}.wav")
        if not os.path.exists(wav_path):
            write_wav_file(wav_path, pcm)

    # 3. Synthesize the 8 tuned dynamic pitch-modulated hover & tick files
    for i, freq in enumerate(PILL_SCALE_FREQUENCIES):
        hover_path = os.path.join(sound_dir, f"hover_{i}.wav")
        if not os.path.exists(hover_path):
            pcm_h = synthesize_glass_tone(freq, duration_s=0.038, attack_s=0.003, decay_rate=38.0, peak_amplitude=0.58)
            write_wav_file(hover_path, pcm_h)

        tick_path = os.path.join(sound_dir, f"tick_{i}.wav")
        if not os.path.exists(tick_path):
            pcm_t = synthesize_glass_tone(freq * 1.15, duration_s=0.026, attack_s=0.002, decay_rate=52.0, peak_amplitude=0.52)
            write_wav_file(tick_path, pcm_t)

    return sound_dir


class PolyphonicSoundEngine:
    """Multi-channel zero-latency sound engine for Sentinel.
    
    Features:
    - Multi-channel polyphony: Overlapping sounds decay naturally without cutting off.
    - Max volume: All voices hardcoded at 1.0 (100% maximum volume).
    - Multi-voice round-robin pooling: Rapid clicks never drop a transient.
    - Dynamic pitch modulation: Tuned glass marimba tones for the 8 island pills.
    - Resilient fallback: Background threaded audio if QtMultimedia is uninitialized.
    """

    def __init__(self):
        self._voices: Dict[str, List[Any]] = {}
        self._voice_indices: Dict[str, int] = {}
        self._initialized = False
        self._lock = threading.Lock()

    def _ensure_initialized(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            ensure_sound_files()
            self._init_qt_voices()
            self._initialized = True

    def _init_qt_voices(self):
        if not HAS_QT_AUDIO or not QApplication.instance():
            return

        sound_dir = get_sound_dir()

        # Build list of all available sound files in sound_dir
        if not os.path.isdir(sound_dir):
            return

        for f in os.listdir(sound_dir):
            if not f.endswith(".wav"):
                continue
            name = f[:-4]
            wav_path = os.path.join(sound_dir, f)
            if not os.path.isfile(wav_path):
                continue

            # Multi-voice allocation: Rapid sounds get 4 voices, others get 2 voices
            voice_count = 4 if any(k in name for k in ("tick", "hover", "blip", "click")) else 2
            voices = []
            url = QUrl.fromLocalFile(os.path.abspath(wav_path))

            for _ in range(voice_count):
                try:
                    eff = QSoundEffect()
                    eff.setSource(url)
                    eff.setVolume(1.0)  # Always at maximum volume
                    voices.append(eff)
                except Exception:
                    pass

            if voices:
                self._voices[name] = voices
                self._voice_indices[name] = 0

    def _resolve_path(self, name: str) -> Optional[str]:
        actual = SOUND_ALIASES.get(name, name)
        sound_dir = get_sound_dir()
        bundled_dir = get_bundled_sound_dir()

        candidates = [
            os.path.join(sound_dir, f"{name}.wav"),
            os.path.join(sound_dir, f"{actual}.wav"),
            os.path.join(bundled_dir, f"{name}.wav"),
            os.path.join(bundled_dir, f"{actual}.wav"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    def play(self, name: str, enabled: bool = True):
        """Play a sound effect with true polyphony and maximum volume."""
        if not enabled:
            return

        self._ensure_initialized()
        actual = SOUND_ALIASES.get(name, name)

        # 1. Primary Engine: QtMultimedia Multi-Voice Pool (true polyphony, zero latency)
        if HAS_QT_AUDIO and QApplication.instance():
            voices = self._voices.get(name) or self._voices.get(actual)
            if voices:
                idx = self._voice_indices.get(name, 0)
                voice = voices[idx]
                self._voice_indices[name] = (idx + 1) % len(voices)
                voice.setVolume(1.0)  # Maximum volume
                voice.play()
                return

        # 2. Resilient Fallback: Threaded background winsound (never blocks main thread)
        self._play_threaded_fallback(actual)

    def play_pill_hover(self, pill_idx: int, enabled: bool = True):
        """Play dynamically modulated glass transient for pill index 0..7."""
        if not enabled:
            return
        idx = max(0, min(7, pill_idx))
        sound_name = f"hover_{idx}"
        self.play(sound_name, enabled=enabled)

    def play_pill_tick(self, pill_idx: int, enabled: bool = True):
        """Play ascending ripple transient for pill entrance cascade 0..7."""
        if not enabled:
            return
        idx = max(0, min(7, pill_idx))
        sound_name = f"tick_{idx}"
        self.play(sound_name, enabled=enabled)

    def _play_threaded_fallback(self, name: str):
        if sys.platform != "win32":
            return
        wav_path = self._resolve_path(name)
        if not wav_path:
            return

        def _worker():
            try:
                import winsound
                # SND_ASYNC guarantees asynchronous execution
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()


# Global engine singleton
_ENGINE: Optional[PolyphonicSoundEngine] = None


def get_sound_engine() -> PolyphonicSoundEngine:
    """Return the global polyphonic sound engine instance."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = PolyphonicSoundEngine()
    return _ENGINE


def play_sound(name: str, enabled: bool = True):
    """Play a sound effect asynchronously with true multi-channel polyphony."""
    get_sound_engine().play(name, enabled=enabled)


def play_pill_hover(pill_idx: int, enabled: bool = True):
    """Play dynamically pitch-modulated glass hover tone for pill index 0..7."""
    get_sound_engine().play_pill_hover(pill_idx, enabled=enabled)


def play_pill_tick(pill_idx: int, enabled: bool = True):
    """Play ascending ripple entrance transient for pill index 0..7."""
    get_sound_engine().play_pill_tick(pill_idx, enabled=enabled)
