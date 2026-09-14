from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
CATALOG_ROOT = ROOT / "music" / "sc_expansion"
sys.path.insert(0, str(ROOT / "code"))

from sc_drum_kits import DRUM_KITS, resolve_hit  # noqa: E402
from sc_music_catalog import load_sc_music_catalog  # noqa: E402


class ScMusicExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_sc_music_catalog(CATALOG_ROOT / "sc_kit_grooves_v1.json")
        cls.rhythm_ids = tuple(
            str(row["id"])
            for row in json.loads(
                (ROOT / "music" / "rhythms.json").read_text(encoding="utf-8")
            )["rhythms"]
        )

    def test_generated_authorities_match_their_recorded_hashes(self) -> None:
        manifest = json.loads((CATALOG_ROOT / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["outputs"].items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256((CATALOG_ROOT / name).read_bytes()).hexdigest(),
                    expected,
                )

    def test_every_kit_rhythm_has_five_levels_and_five_fills(self) -> None:
        self.assertEqual(len(DRUM_KITS), 9)
        self.assertEqual(len(self.rhythm_ids), 54)
        for kit in DRUM_KITS:
            for rhythm_id in self.rhythm_ids:
                with self.subTest(kit=kit.kit_id, rhythm=rhythm_id):
                    arrangement = self.catalog.arrangement(kit.kit_id, rhythm_id)
                    fills = self.catalog.fills(kit.kit_id, rhythm_id)
                    self.assertEqual(len(arrangement.levels), 5)
                    self.assertEqual([fill.slot_level for fill in fills], [1, 2, 3, 4, 5])
                    self.assertTrue(all(fill.events for fill in fills))

    def test_every_drum_sample_is_in_the_pinned_vsco_manifest(self) -> None:
        kit_data = json.loads(
            (CATALOG_ROOT / "sc_pcm_drumkits_v1.json").read_text(encoding="utf-8")
        )
        sample_ids = {
            sample_id
            for sample_set in kit_data["sample_sets"]
            for layer in sample_set["layers"]
            for sample_id in layer["round_robin_sample_ids"]
        }
        manifest_ids = {
            row["id"]
            for row in json.loads(
                (SC_ROOT / "vsco-manifest.json").read_text(encoding="utf-8")
            )["files"]
        }
        self.assertEqual(len(sample_ids), 262)
        self.assertLessEqual(sample_ids, manifest_ids)

    def test_explicit_pad_identity_is_not_encoded_as_a_gm_note(self) -> None:
        for kit in DRUM_KITS:
            program, pad, _gain = resolve_hit(kit.kit_id, "backbeat_primary")
            self.assertEqual(program, kit.program_id)
            self.assertIsInstance(pad, str)
            self.assertFalse(pad.isdecimal())


if __name__ == "__main__":
    unittest.main()
