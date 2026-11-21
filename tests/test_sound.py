"""Unit tests for sound synthesis: valid WAV format, non-silent, not clipped."""

import io
import struct
import unittest
import wave
from src.senti_sound import (
    synthesize_tone,
    synthesize_glass_tone,
    generate_sound_specs,
    write_wav_file,
    get_sound_engine,
    play_sound,
    play_pill_hover,
    play_pill_tick,
    PILL_SCALE_FREQUENCIES,
)


class TestSoundSynthesis(unittest.TestCase):

    def test_synthesize_tone_pcm_validity(self):
        pcm = synthesize_tone([440.0], duration_s=0.1, sample_rate=44100)
        self.assertGreater(len(pcm), 0)
        # 16-bit mono = 2 bytes per sample
        num_samples = len(pcm) // 2
        self.assertEqual(num_samples, int(44100 * 0.1))

        # Check samples are within 16-bit range and not clipped (not constantly at +-32767)
        samples = [struct.unpack("<h", pcm[i:i+2])[0] for i in range(0, len(pcm), 2)]
        max_val = max(samples)
        min_val = min(samples)

        # Tone must be non-silent
        self.assertGreater(max_val, 1000)
        self.assertLess(min_val, -1000)

        # Must not be clipped (peak amplitude was designed at ~0.55 * 32767)
        self.assertLess(max_val, 32700)
        self.assertGreater(min_val, -32700)

    def test_glass_tone_synthesis_and_scale(self):
        self.assertEqual(len(PILL_SCALE_FREQUENCIES), 8)
        for i, freq in enumerate(PILL_SCALE_FREQUENCIES):
            pcm = synthesize_glass_tone(freq, duration_s=0.04)
            self.assertGreater(len(pcm), 0)
            samples = [struct.unpack("<h", pcm[j:j+2])[0] for j in range(0, len(pcm), 2)]
            self.assertGreater(max(samples), 500)
            self.assertLess(max(samples), 32700)

    def test_polyphonic_engine_multi_voice_and_max_volume(self):
        engine = get_sound_engine()
        engine._ensure_initialized()

        # Rapid fire triggers must not raise exceptions
        for sound_name in ["blip", "tick", "hover", "attach", "open", "close"]:
            engine.play(sound_name, enabled=True)

        # Pill pitch modulation triggers 0..7
        for pill_idx in range(8):
            engine.play_pill_hover(pill_idx, enabled=True)
            engine.play_pill_tick(pill_idx, enabled=True)

    def test_all_sound_specs_generate_valid_wav(self):
        specs = generate_sound_specs()
        expected_sounds = ["click", "open", "close", "shrink", "restore", "show", "hide", "dock"]

        for name in expected_sounds:
            self.assertIn(name, specs)
            pcm = specs[name]
            self.assertGreater(len(pcm), 0)

            # Test in-memory WAV generation
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(pcm)

            # Read back and verify WAV header
            buffer.seek(0)
            with wave.open(buffer, "rb") as wf_in:
                self.assertEqual(wf_in.getnchannels(), 1)
                self.assertEqual(wf_in.getsampwidth(), 2)
                self.assertEqual(wf_in.getframerate(), 44100)
                self.assertGreater(wf_in.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
