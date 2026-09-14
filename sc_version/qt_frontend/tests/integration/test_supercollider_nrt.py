from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy
import soundfile


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
    def test_strum_ceiling_is_finite_for_repaired_source_definitions(self) -> None:
        regression_programs = {
            "sc.sclork.acidOto3091",
            "sc.sclork.acidOto3092",
            "sc.sclork.combs",
            "sc.sclork.doubleBass",
            "sc.sclork.tubularBell",
        }
        catalog = json.loads(
            (SC_ROOT / "sclork-programs.json").read_text(encoding="utf-8")
        )["programs"]
        indexes = [
            index
            for index, program in enumerate(catalog)
            if program["program_id"] in regression_programs
        ]
        self.assertEqual(len(indexes), len(regression_programs))
        start_index = min(indexes)
        count = max(indexes) - start_index + 1
        with tempfile.TemporaryDirectory(prefix="lb-sclork-register-") as temporary:
            output = Path(temporary) / "strum-ceiling.wav"
            environment = dict(os.environ)
            environment.update(
                {
                    "QT_QPA_PLATFORM": "offscreen",
                    "OMNICHORD_SC_NRT_OUTPUT": str(output),
                    "OMNICHORD_SC_NRT_START": str(start_index),
                    "OMNICHORD_SC_NRT_COUNT": str(count),
                    # MIDI 107, the public strum's upper inclusive boundary.
                    "OMNICHORD_SC_NRT_FREQUENCY": "3951.066410",
                }
            )
            completed = subprocess.run(
                ["sclang", "-D", str(SC_ROOT / "tests" / "sclork_nrt_render.scd")],
                cwd=SC_ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=45,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            frames, sample_rate = soundfile.read(
                output,
                dtype="float64",
                always_2d=True,
            )
        self.assertEqual(sample_rate, SAMPLE_RATE)
        segment_frames = round(SEGMENT_SECONDS * SAMPLE_RATE)
        for catalog_index in indexes:
            relative = catalog_index - start_index
            segment = frames[
                relative * segment_frames : (relative + 1) * segment_frames
            ]
            rms = math.sqrt(float(numpy.mean(numpy.square(segment))))
            peak = float(numpy.max(numpy.abs(segment)))
            with self.subTest(program=catalog[catalog_index]["program_id"]):
                self.assertTrue(math.isfinite(rms))
                self.assertTrue(math.isfinite(peak))
                self.assertLess(peak, 1.0)

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
                frames, sample_rate = soundfile.read(
                    output,
                    dtype="float64",
                    always_2d=True,
                )
                self.assertEqual(sample_rate, SAMPLE_RATE)
                self.assertEqual(frames.shape[1], 2)

                segment_frames = round(SEGMENT_SECONDS * SAMPLE_RATE)
                for index, program in enumerate(batch):
                    start = index * segment_frames
                    segment = frames[start : start + segment_frames]
                    rms = math.sqrt(float(numpy.mean(numpy.square(segment))))
                    peak = float(numpy.max(numpy.abs(segment)))
                    report.append(
                        {
                            "program_id": program["program_id"],
                            "native_name": program["native_name"],
                            "rms": round(rms, 8),
                            "peak": round(peak, 8),
                            "finite": math.isfinite(rms) and math.isfinite(peak),
                            "silent": math.isfinite(rms) and rms < 1e-6,
                            "clipped": math.isfinite(peak) and peak >= 1.0,
                        }
                    )
            self.assertEqual(len(report), len(catalog))
            report_path = artifact_root / "sclork-nrt-report.json"
            report_path.write_text(
                json.dumps({"schema_version": 1, "programs": report}, indent=2) + "\n",
                encoding="utf-8",
            )
            profile = json.loads(
                (SC_ROOT / "sclork-playback.json").read_text(encoding="utf-8")
            )
            browser_programs = set(profile["programs"])
            visible = [
                item for item in report if item["program_id"] in browser_programs
            ]
            silent = [item["program_id"] for item in visible if item["silent"]]
            self.assertEqual(
                silent,
                [],
                f"silent programs: {silent}; see {report_path}\n"
                + "\n".join(render_logs),
            )
            invalid = [item["program_id"] for item in visible if not item["finite"]]
            self.assertEqual(invalid, [], f"non-finite browser programs: {invalid}")
            clipped = [item["program_id"] for item in visible if item["clipped"]]
            self.assertEqual(clipped, [], f"clipped browser programs: {clipped}")
            too_quiet = [
                item["program_id"] for item in visible if float(item["rms"]) < 0.002
            ]
            self.assertEqual(
                too_quiet,
                [],
                f"inaudibly quiet browser programs: {too_quiet}",
            )
            categories = {
                str(item["program_id"]): str(item["category"])
                for item in catalog
            }
            calibrated_drums = [
                item
                for item in visible
                if categories[str(item["program_id"])] == "drums"
            ]
            self.assertTrue(calibrated_drums)
            unbalanced = [
                item
                for item in calibrated_drums
                if not 0.015 <= float(item["rms"]) <= 0.075
                or float(item["peak"]) >= 0.85
            ]
            self.assertEqual(
                unbalanced,
                [],
                "drum-kit programs exceed the reviewed runtime balance window",
            )


if __name__ == "__main__":
    unittest.main()
