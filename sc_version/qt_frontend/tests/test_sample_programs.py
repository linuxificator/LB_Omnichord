from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from sample_programs import load_vsco_programs  # noqa: E402


class SampleProgramTests(unittest.TestCase):
    def test_all_vsco_programs_are_available_by_stable_id(self) -> None:
        programs = load_vsco_programs(
            ROOT.parent / "supercollider" / "vsco-manifest.json"
        )
        self.assertEqual(len(programs), 75)
        self.assertTrue(all(item.program_id.startswith("sample.vsco.") for item in programs))
        keyswitches = [item for item in programs if len(item.articulations) > 1]
        self.assertTrue(keyswitches)
        self.assertTrue(all(item.default_articulation in item.articulations for item in keyswitches))


if __name__ == "__main__":
    unittest.main()
