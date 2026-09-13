from __future__ import annotations

from array import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[2]
SC_ROOT = ROOT.parent / "supercollider"
SEGMENT_SECONDS = 0.75
SAMPLE_RATE = 48_000
BATCH_SIZE = 12


@unittest.skipUnless(
    shutil.which("sclang") and shutil.which("scsynth"),
    "SuperCollider is unavailable",
)
class SuperColliderNonRealtimeTests(unittest.TestCase):
    def test_all_sclork_programs_render_bounded_finite_audio(self) -> None:
        artifact_root = Path(
            os.environ.get("OMNICHORD_TEST_ARTIFACT_DIR", ROOT / "test-artifacts")
        )
        artifact_root.mkdir(parents=True, exist_ok=True)
        catalog = json.loads(
            (SC_ROOT / "sclork-programs.json").read_text(encoding="utf-8")
        )["programs"]
        report = []
        render_logs = []
        with tempfile.TemporaryDirectory(prefix="lb-sclork-nrt-") as temporary:
            temporary_root = Path(temporary)
            for batch_start in range(0, len(catalog), BATCH_SIZE):
                batch = catalog[batch_start : batch_start + BATCH_SIZE]
                print(
                    f"Rendering SCLOrk programs {batch_start + 1}-"
                    f"{batch_start + len(batch)} of {len(catalog)}",
                    flush=True,
                )
                output = temporary_root / f"sclork-audit-{batch_start:03d}.wav"
                environment = dict(os.environ)
                environment["QT_QPA_PLATFORM"] = "offscreen"
                environment["OMNICHORD_SC_NRT_OUTPUT"] = str(output)
                environment["OMNICHORD_SC_NRT_START"] = str(batch_start)
                environment["OMNICHORD_SC_NRT_COUNT"] = str(len(batch))
                completed = subprocess.run(
                    [
                        "sclang",
                        "-D",
                        str(SC_ROOT / "tests" / "sclork_nrt_render.scd"),
                    ],
                    cwd=SC_ROOT,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=45,
                    check=False,
                )
                render_logs.append(completed.stdout)
                self.assertEqual(completed.returncode, 0, completed.stdout)
                self.assertTrue(output.is_file(), completed.stdout)
                self.assertNotIn("SynthDef not found", completed.stdout)
                self.assertNotIn("makeSynthMsgWithTags: buffer overflow", completed.stdout)
                with wave.open(str(output), "rb") as rendered:
                    self.assertEqual(rendered.getframerate(), SAMPLE_RATE)
                    self.assertEqual(rendered.getnchannels(), 2)
                    self.assertEqual(rendered.getsampwidth(), 2)
                    frames = rendered.readframes(rendered.getnframes())

                segment_bytes = round(SEGMENT_SECONDS * SAMPLE_RATE) * 4
                for index, program in enumerate(batch):
                    start = index * segment_bytes
                    segment = frames[start : start + segment_bytes]
                    samples = array("h")
                    samples.frombytes(segment)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    rms = math.sqrt(
                        sum(sample * sample for sample in samples) / len(samples)
                    ) / 32767.0
                    peak = max(abs(sample) for sample in samples) / 32767.0
                    report.append(
                        {
                            "program_id": program["program_id"],
                            "native_name": program["native_name"],
                            "rms": round(rms, 8),
                            "peak": round(peak, 8),
                            "silent": rms < 1e-6,
                            "clipped": math.isclose(
                                peak, 1.0, abs_tol=1 / 32767
                            ),
                        }
                    )
            self.assertEqual(len(report), len(catalog))
            report_path = artifact_root / "sclork-nrt-report.json"
            report_path.write_text(
                json.dumps({"schema_version": 1, "programs": report}, indent=2) + "\n",
                encoding="utf-8",
            )
            silent = [item["program_id"] for item in report if item["silent"]]
            self.assertEqual(
                silent,
                [],
                f"silent programs: {silent}; see {report_path}\n"
                + "\n".join(render_logs),
            )


if __name__ == "__main__":
    unittest.main()
