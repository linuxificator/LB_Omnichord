from __future__ import annotations

from array import array
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[2]
SC_ROOT = ROOT.parent / "supercollider"
SAMPLE_RATE = 48_000


def _write_fixture(path: Path, *, stereo: bool) -> None:
    frames = []
    for index in range(round(0.25 * SAMPLE_RATE)):
        left = round(9000 * math.sin(2 * math.pi * 440 * index / SAMPLE_RATE))
        if stereo:
            right = round(5000 * math.sin(2 * math.pi * 660 * index / SAMPLE_RATE))
            frames.extend((left, right))
        else:
            frames.append(left)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2 if stereo else 1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(struct.pack(f"<{len(frames)}h", *frames))


def _channel_rms(frames: bytes) -> tuple[float, float]:
    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    left = samples[0::2]
    right = samples[1::2]
    return tuple(
        math.sqrt(sum(value * value for value in channel) / len(channel)) / 32767
        for channel in (left, right)
    )


@unittest.skipUnless(
    shutil.which("sclang") and shutil.which("scsynth"),
    "SuperCollider is unavailable",
)
class SuperColliderSampleNonRealtimeTests(unittest.TestCase):
    def test_production_mono_and_stereo_players_render_and_release(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lb-sample-nrt-") as temporary:
            root = Path(temporary)
            mono = root / "mono.wav"
            stereo = root / "stereo.wav"
            rendered = root / "rendered.wav"
            _write_fixture(mono, stereo=False)
            _write_fixture(stereo, stereo=True)
            environment = dict(os.environ)
            environment.update(
                {
                    "QT_QPA_PLATFORM": "offscreen",
                    "OMNICHORD_SC_SAMPLE_NRT_OUTPUT": str(rendered),
                    "OMNICHORD_SC_SAMPLE_NRT_MONO": str(mono),
                    "OMNICHORD_SC_SAMPLE_NRT_STEREO": str(stereo),
                }
            )
            completed = subprocess.run(
                ["sclang", "-D", str(SC_ROOT / "tests" / "sample_nrt_render.scd")],
                cwd=SC_ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("LB_OMNICHORD_SAMPLE_NRT_OK", completed.stdout)
            with wave.open(str(rendered), "rb") as source:
                self.assertEqual(source.getnchannels(), 2)
                self.assertEqual(source.getframerate(), SAMPLE_RATE)
                all_frames = source.readframes(source.getnframes())

        frame_bytes = 4
        mono_segment = all_frames[
            round(0.12 * SAMPLE_RATE) * frame_bytes :
            round(0.27 * SAMPLE_RATE) * frame_bytes
        ]
        stereo_segment = all_frames[
            round(0.62 * SAMPLE_RATE) * frame_bytes :
            round(0.77 * SAMPLE_RATE) * frame_bytes
        ]
        mono_left, mono_right = _channel_rms(mono_segment)
        stereo_left, stereo_right = _channel_rms(stereo_segment)
        self.assertGreater(mono_left, 0.03)
        self.assertAlmostEqual(mono_left, mono_right, delta=0.002)
        self.assertGreater(stereo_left, 0.03)
        self.assertGreater(stereo_right, 0.015)
        self.assertGreater(abs(stereo_left - stereo_right), 0.005)


if __name__ == "__main__":
    unittest.main()
