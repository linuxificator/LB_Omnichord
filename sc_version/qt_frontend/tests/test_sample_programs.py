from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from sample_programs import articulation_program_id, load_vsco_programs  # noqa: E402


class SampleProgramTests(unittest.TestCase):
    def test_all_vsco_programs_are_available_by_stable_id(self) -> None:
        programs = load_vsco_programs(
            ROOT.parent / "supercollider" / "vsco-manifest.json"
        )
        self.assertEqual(len(programs), 96)
        self.assertTrue(all(item.program_id.startswith("sample.vsco.") for item in programs))
        source_programs = [
            item for item in programs if item.program_id == item.source_program_id
        ]
        self.assertEqual(len(source_programs), 75)
        keyswitches = [item for item in source_programs if len(item.articulations) > 1]
        self.assertTrue(keyswitches)
        self.assertTrue(all(item.default_articulation in item.articulations for item in keyswitches))
        flute_staccato = articulation_program_id(
            "sample.vsco.flute-ks", "d-2-staccato"
        )
        variant = next(item for item in programs if item.program_id == flute_staccato)
        self.assertEqual(variant.source_program_id, "sample.vsco.flute-ks")
        self.assertEqual(variant.selected_articulation, "d-2-staccato")
        self.assertIn("staccato", variant.display_name)


if __name__ == "__main__":
    unittest.main()
