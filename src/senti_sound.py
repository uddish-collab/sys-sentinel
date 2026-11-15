"""Synthesizes soft interaction tones and plays them via Windows winsound.

Writes WAV files to %LOCALAPPDATA%\\SYS-SENTINEL\\sounds.
No QtMultimedia and no third-party audio libraries used.
"""

import math
import os
import struct
import sys
import wave
from typing import Dict, List, Tuple


SOUND_NAMES = ["click", "open", "close", "shrink", "restore", "show", "hide", "dock"]


def get_sound_dir() -> str:
    """Return %LOCALAPPDATA%\\SYS-SENTINEL\\sounds."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.expanduser("~")
    sound_dir = os.path.join(local_app_data, "SYS-SENTINEL", "sounds")
    os.makedirs(sound_dir, exist_ok=True)
    return sound_dir


def synthesize_tone(
    frequencies: List[float],
    duration_s: float,
    attack_s: float = 0.01,
    decay_rate: float = 18.0,
    peak_amplitude: float = 0.55,
    sample_rate: int = 44100,
) -> bytes:
    """Generate 16-bit mono PCM bytes for a soft tone with harmonics and envelope.
    
    Includes fundamental frequencies with a soft second harmonic (20% amplitude),
    smooth linear attack to prevent clicks, and exponential decay.
    """
    num_samples = int(sample_rate * duration_s)
    attack_samples = max(1, int(sample_rate * attack_s))
    raw_data = bytearray()

    for i in range(num_samples):
        t = i / sample_rate

        # Linear attack envelope
        if i < attack_samples:
            env = i / attack_samples
        else:
            env = math.exp(-decay_rate * (t - attack_s))

        # Sum fundamental + second harmonic for warmth
        sample_val = 0.0
        for f in frequencies:
            sample_val += math.sin(2.0 * math.pi * f * t)
            sample_val += 0.20 * math.sin(4.0 * math.pi * f * t)

        sample_val = (sample_val / len(frequencies)) * env * peak_amplitude

        # Clamp between -1.0 and 1.0 to guarantee no clipping
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
    """Define tone recipes for all interaction sounds."""
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
    # Simulated by stepped frequencies descending smoothly
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
    """Ensure all required WAV files exist on disk, generating them if missing."""
    sound_dir = get_sound_dir()
    specs = generate_sound_specs()
    for name, pcm in specs.items():
        wav_path = os.path.join(sound_dir, f"{name}.wav")
        if not os.path.exists(wav_path):
            write_wav_file(wav_path, pcm)
    return sound_dir


def play_sound(name: str, enabled: bool = True):
    """Play an interaction sound asynchronously using winsound.
    
    Uses SND_FILENAME | SND_ASYNC | SND_NODEFAULT.
    Does NOT use SND_MEMORY (which raises RuntimeError with SND_ASYNC).
    """
    if not enabled:
        return

    if sys.platform != "win32":
        return

    try:
        import winsound
        sound_dir = get_sound_dir()
        wav_path = os.path.join(sound_dir, f"{name}.wav")
        if not os.path.exists(wav_path):
            ensure_sound_files()

        if os.path.exists(wav_path):
            flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
            winsound.PlaySound(wav_path, flags)
    except Exception:
        # Never crash the main UI thread if audio device is unavailable
        pass
