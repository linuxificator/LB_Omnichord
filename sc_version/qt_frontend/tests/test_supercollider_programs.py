from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from supercollider_programs import (  # noqa: E402
    build_legacy_program_map,
    display_name,
    load_legacy_program_map,
    build_sclork_catalog,
    load_supercollider_programs,
)


class SuperColliderProgramCatalogTests(unittest.TestCase):
    def test_checked_in_catalog_is_reproducible_from_pinned_sources(self) -> None:
        source_root = SC_ROOT / "vendor" / "SCLOrkSynths" / "SynthDefs"
        expected = build_sclork_catalog(source_root)
        checked_in = json.loads(
            (SC_ROOT / "sclork-programs.json").read_text(encoding="utf-8")
        )
        self.assertEqual(checked_in, expected)

    def test_runtime_catalog_has_all_stable_ids_and_lifetime_metadata(self) -> None:
        programs = load_supercollider_programs(SC_ROOT / "sclork-programs.json")
        self.assertEqual(len(programs), 109)
        self.assertTrue(all(item.program_id.startswith("sc.sclork.") for item in programs))
        self.assertEqual({item.release_mode for item in programs}, {"gated", "natural"})
        self.assertTrue(all(item.controls for item in programs))

    def test_legacy_program_mapping_is_explicit_and_reproducible(self) -> None:
        legacy = ROOT / "instruments" / "synths.json"
        expected = build_legacy_program_map(legacy)
        path = ROOT / "instruments" / "supercollider-legacy-map.json"
        checked_in = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(checked_in, expected)
        mappings = load_legacy_program_map(path)
        programs = load_supercollider_programs(SC_ROOT / "sclork-programs.json")
        available = {program.program_id for program in programs} | {
            "sc.omni.acid303",
            "sc.omni.acidOto",
            "sc.omni.acidMoog",
            "sc.omni.acidWarsaw",
        }
        self.assertEqual(len(mappings), 125)
        self.assertLessEqual(set(mappings.values()), available)
        self.assertEqual(mappings["tb303"], "sc.omni.acid303")
        self.assertEqual(mappings["physical_strings"], "sc.sclork.pluck")

    def test_native_names_have_human_readable_sc_labels(self) -> None:
        self.assertEqual(display_name("organTonewheel1"), "SC Organ Tonewheel 1")


if __name__ == "__main__":
    unittest.main()
