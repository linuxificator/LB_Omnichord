from __future__ import annotations

import math
import unittest

import numpy as np

from audio_metrics import audio_metrics


class AudioMetricsTests(unittest.TestCase):
    SAMPLE_RATE = 44_100

    def tone(self, frequency: float, amplitude: float = 0.1) -> np.ndarray:
        time = np.arange(self.SAMPLE_RATE, dtype=np.float64) / self.SAMPLE_RATE
        return amplitude * np.sin(2.0 * math.pi * frequency * time)

    def test_doubling_amplitude_adds_six_decibels(self) -> None:
        quiet = audio_metrics(self.tone(1_000.0, 0.1), self.SAMPLE_RATE)
        loud = audio_metrics(self.tone(1_000.0, 0.2), self.SAMPLE_RATE)
        self.assertAlmostEqual(
            float(loud["loudness_lkfs"]) - float(quiet["loudness_lkfs"]),
            6.0206,
            places=2,
        )

    def test_k_weighting_penalizes_low_frequency_energy(self) -> None:
        bass = audio_metrics(self.tone(50.0), self.SAMPLE_RATE)
        reference = audio_metrics(self.tone(1_000.0), self.SAMPLE_RATE)
        self.assertLess(
            float(bass["loudness_lkfs"]),
            float(reference["loudness_lkfs"]) - 4.0,
        )

    def test_silence_is_finite_and_not_clipped(self) -> None:
        metrics = audio_metrics(np.zeros((128, 2)), self.SAMPLE_RATE)
        self.assertTrue(math.isfinite(float(metrics["loudness_lkfs"])))
        self.assertEqual(int(metrics["clipped_samples"]), 0)


if __name__ == "__main__":
    unittest.main()
