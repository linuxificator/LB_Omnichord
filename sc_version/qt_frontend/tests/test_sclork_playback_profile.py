from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "code"))

import build_sclork_playback_profile  # noqa: E402
from supercollider_programs import load_sclork_playback_profile  # noqa: E402


class SclorkPlaybackProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (SC_ROOT / "sclork-programs.json").read_text(encoding="utf-8")
        )["programs"]
        cls.profile = json.loads(
            (SC_ROOT / "sclork-playback.json").read_text(encoding="utf-8")
        )

    def test_profile_exactly_covers_browser_eligible_sclork_programs(self) -> None:
        candidates = {
            item["program_id"]
            for item in self.catalog
            if item["pitch_support"] and item["category"] != "drums"
        }
        included = set(self.profile["programs"])
        excluded = set(self.profile["excluded"])
        self.assertEqual(included | excluded, candidates)
        self.assertFalse(included & excluded)
        self.assertEqual(
            excluded,
            {"sc.sclork.metalPlate", "sc.sclork.noQuarter"},
        )

    def test_runtime_loader_preserves_gains_and_exclusion_reasons(self) -> None:
        gains, exclusions = load_sclork_playback_profile(
            SC_ROOT / "sclork-playback.json"
        )
        self.assertEqual(gains["sc.sclork.glockenspiel"], 16.0)
        self.assertIn("unstable raw output", exclusions["sc.sclork.metalPlate"])

    def test_runtime_loader_rejects_ambiguous_or_unsafe_profiles(self) -> None:
        examples = (
            {
                "schema_revision": 1,
                "method": {"max_gain": 16},
                "programs": {"sc.example": {"gain": 1}},
                "excluded": {"sc.example": {"reason": "ambiguous"}},
            },
            {
                "schema_revision": 1,
                "method": {"max_gain": 16},
                "programs": {"sc.example": {"gain": float("nan")}},
                "excluded": {},
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            for profile in examples:
                with self.subTest(profile=profile):
                    path.write_text(json.dumps(profile), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_sclork_playback_profile(path)

    def test_every_gain_is_finite_positive_and_bounded(self) -> None:
        maximum = float(self.profile["method"]["max_gain"])
        for program_id, record in self.profile["programs"].items():
            with self.subTest(program_id=program_id):
                gain = float(record["gain"])
                self.assertTrue(math.isfinite(gain))
                self.assertGreater(gain, 0)
                self.assertLessEqual(gain, maximum)

    def test_builder_is_deterministic_for_fixed_reports(self) -> None:
        reports = {
            note: {
                "schema_version": 1,
                "programs": [
                    {
                        "program_id": item["program_id"],
                        "rms": 0.01 + (note / 100_000),
                        "peak": 0.1 + (note / 10_000),
                    }
                    for item in self.catalog
                ],
            }
            for note in (45, 69)
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for note, report in reports.items():
                path = root / f"{note}.json"
                path.write_text(json.dumps(report), encoding="utf-8")
                paths.append(f"{note}={path}")
            first = root / "first.json"
            second = root / "second.json"
            arguments = [
                "profile-builder",
                "--catalog",
                str(SC_ROOT / "sclork-programs.json"),
                *(
                    argument
                    for value in paths
                    for argument in ("--report", value)
                ),
            ]
            previous = sys.argv
            try:
                sys.argv = [*arguments, "--output", str(first)]
                self.assertEqual(build_sclork_playback_profile.main(), 0)
                sys.argv = [*arguments, "--output", str(second)]
                self.assertEqual(build_sclork_playback_profile.main(), 0)
            finally:
                sys.argv = previous
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
