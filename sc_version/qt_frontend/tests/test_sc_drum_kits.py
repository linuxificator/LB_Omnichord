from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from sc_music_catalog import load_sc_music_catalog  # noqa: E402
from sc_drum_kits import (  # noqa: E402
    DEFAULT_DRUM_KIT_ID,
    DRUM_KITS,
    _catalog,
    kit_by_id,
    midi_role,
    resolve_hit,
)


class SuperColliderDrumKitTests(unittest.TestCase):
    def test_catalogue_resolves_from_frozen_asset_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packaged = Path(directory)
            target = packaged / "music" / "sc_expansion"
            target.mkdir(parents=True)
            source = ROOT / "music" / "sc_expansion" / "sc_native_drumkits_v1.json"
            shutil.copy2(source, target / source.name)
            with patch.object(sys, "_MEIPASS", str(packaged), create=True):
                self.assertEqual(_catalog(source.name)["schema_version"], 1)

    def test_default_pcm_kit_and_ids_are_stable_and_unique(self) -> None:
        self.assertEqual(DEFAULT_DRUM_KIT_ID, "pcm-vsco")
        self.assertEqual(len(DRUM_KITS), 15)
        self.assertEqual(len({kit.kit_id for kit in DRUM_KITS}), len(DRUM_KITS))
        with self.assertRaisesRegex(ValueError, "unknown SC drum kit"):
            kit_by_id("unknown")

    def test_every_rhythm_role_resolves_in_every_kit(self) -> None:
        catalog = load_sc_music_catalog(
            ROOT / "music" / "sc_expansion" / "sc_kit_grooves_v1.json"
        )
        roles = {
            event.role
            for kit in DRUM_KITS
            for rhythm_id in json.loads(
                (ROOT / "music" / "rhythms.json").read_text(encoding="utf-8")
            )["rhythms"]
            for level in catalog.arrangement(kit.kit_id, rhythm_id["id"]).levels
            for event in level
        }
        for kit in DRUM_KITS:
            for role in roles:
                with self.subTest(kit=kit.kit_id, role=role):
                    program, pad, gain = resolve_hit(kit.kit_id, role)
                    self.assertTrue(program)
                    self.assertTrue(pad)
                    self.assertGreater(gain, 0.0)

    def test_pcm_programs_and_pads_are_explicit(self) -> None:
        pcm_kits = [kit for kit in DRUM_KITS if kit.kit_id.startswith("pcm-")]
        native_kits = [kit for kit in DRUM_KITS if kit.kit_id.startswith("sc-")]
        self.assertEqual(len(pcm_kits), 10)
        self.assertEqual(len(native_kits), 5)
        self.assertTrue(
            all(
                program.startswith("sample.vsco.")
                for kit in pcm_kits
                for program in kit.sample_programs
            )
        )
        self.assertTrue(all(kit.role_defaults for kit in DRUM_KITS))
        program, pad, _gain = resolve_hit("sc-808", "timekeeper_primary")
        self.assertEqual(program, "sc.sclork.sosHats")
        self.assertEqual(pad, "sc-808/timekeeper_primary")

    def test_legacy_catalogue_slots_resolve_to_vsco_semantic_roles(self) -> None:
        expected = {
            "legacy/low_primary": "low_primary",
            "legacy/backbeat_primary": "backbeat_primary",
            "legacy/timekeeper_primary": "timekeeper_primary",
        }
        for slot, role in expected.items():
            with self.subTest(slot=slot):
                program, pad, gain = resolve_hit("pcm-vsco", slot)
                self.assertEqual(program, "sample.vsco.gm-styleperc")
                self.assertEqual(pad, role)
                self.assertEqual(gain, 1.0)

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
