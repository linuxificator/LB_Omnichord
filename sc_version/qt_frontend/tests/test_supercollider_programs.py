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
from catalog_extensions import load_synth_catalog  # noqa: E402
from vsco_browser import load_vsco_browser  # noqa: E402


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
        self.assertEqual(display_name("organTonewheel1"), "Organ Tonewheel 1")

    def test_sc_browser_has_reviewed_controls_and_no_backend_prefixes(self) -> None:
        synths, *_ = load_synth_catalog(ROOT / "instruments" / "synths.json")
        self.assertEqual(sum(item.kind == "synth" for item in synths), 80)
        self.assertEqual(sum(item.kind == "sample" for item in synths), 66)
        self.assertTrue(all(not item.label.startswith(("SC ", "VSCO ")) for item in synths))
        warsaw = next(item for item in synths if item.key == "sc.sclork.bassWarsaw")
        self.assertEqual(
            [control.key for control in warsaw.controls if control.group == "common"][:4],
            ["attack_ms", "decay_ms", "sustain", "release_ms"],
        )
        self.assertIn("portamento_ms", {control.key for control in warsaw.controls})
        acid = [item for item in synths if item.key.startswith("sc.omni.acid")]
        self.assertEqual(len(acid), 4)
        self.assertTrue(all(item.supports_riff_articulation for item in acid))
        for synth in (item for item in synths if item.kind == "synth"):
            with self.subTest(program=synth.key):
                self.assertLessEqual(
                    sum(control.group == "extra" for control in synth.controls),
                    4,
                )
                lower_keys = [
                    control.key for control in synth.controls
                    if control.group == "common"
                ]
                adsr = [
                    key for key in (
                        "attack_ms", "decay_ms", "sustain", "release_ms"
                    ) if key in lower_keys
                ]
                self.assertEqual(lower_keys[:len(adsr)], adsr)

    def test_vsco_browser_covers_all_pitched_sources_in_musical_groups(self) -> None:
        choices = load_vsco_browser(SC_ROOT / "vsco-manifest.json")
        self.assertEqual(len(choices), 66)
        self.assertEqual(len({choice.family for choice in choices}), 22)
        organ = [choice for choice in choices if choice.family == "Organ"]
        self.assertEqual({choice.variant for choice in organ}, {"Loud", "Quiet"})
        self.assertEqual({choice.articulation for choice in organ}, {"Manual", "Pedal"})
        trumpet = [choice for choice in choices if choice.family == "Trumpet"]
        self.assertEqual(
            {choice.variant for choice in trumpet},
            {"Open", "Harmon mute", "Straight mute"},
        )


if __name__ == "__main__":
    unittest.main()
