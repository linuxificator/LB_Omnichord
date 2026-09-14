from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from drum_patterns import load_drum_pattern_catalog  # noqa: E402
from sc_drum_kits import (  # noqa: E402
    DEFAULT_DRUM_KIT_ID,
    DRUM_KITS,
    kit_by_id,
    midi_role,
    resolve_program,
)


class SuperColliderDrumKitTests(unittest.TestCase):
    def test_default_pcm_kit_and_ids_are_stable_and_unique(self) -> None:
        self.assertEqual(DEFAULT_DRUM_KIT_ID, "pcm-vsco")
        self.assertEqual(len({kit.kit_id for kit in DRUM_KITS}), len(DRUM_KITS))
        self.assertEqual(kit_by_id("unknown").kit_id, DEFAULT_DRUM_KIT_ID)

    def test_every_rhythm_role_resolves_in_every_kit(self) -> None:
        catalog = load_drum_pattern_catalog(ROOT / "music" / "drums")
        roles = {
            event.role
            for rhythm in catalog.rhythms.values()
            for level in rhythm.levels
            for event in level
        } | {
            event.role
            for rhythm in catalog.rhythms.values()
            for fill in rhythm.fills
            for event in fill.events
        }
        for kit in DRUM_KITS:
            for role in roles:
                with self.subTest(kit=kit.kit_id, role=role):
                    program, gain = resolve_program(kit.kit_id, role)
                    self.assertTrue(program)
                    self.assertGreater(gain, 0.0)
                    self.assertLessEqual(gain, 1.0)

    def test_synth_drum_programs_exist_in_pinned_sc_catalog(self) -> None:
        raw = json.loads(
            (SC_ROOT / "sclork-programs.json").read_text(encoding="utf-8")
        )
        known = {str(item["program_id"]) for item in raw["programs"]}
        requested = {
            program
            for kit in DRUM_KITS
            for _role, program in kit.programs
            if program.startswith("sc.sclork.")
        }
        self.assertLessEqual(requested, known)

    def test_general_midi_notes_map_to_musical_roles(self) -> None:
        self.assertEqual(midi_role(36), "low_primary")
        self.assertEqual(midi_role(38), "backbeat_primary")
        self.assertEqual(midi_role(42), "timekeeper_primary")
        self.assertEqual(midi_role(46), "timekeeper_open")
        self.assertEqual(midi_role(49), "section_accent")
        self.assertEqual(midi_role(43), "tonal_low")
        self.assertEqual(midi_role(50), "tonal_high")


if __name__ == "__main__":
    unittest.main()
