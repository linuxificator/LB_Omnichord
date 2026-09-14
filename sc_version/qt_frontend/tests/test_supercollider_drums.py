from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from sc_music_catalog import load_sc_music_catalog  # noqa: E402


class SuperColliderDrumMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (SC_ROOT / "vsco-manifest.json").read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (SC_ROOT / "drum-key-map.json").read_text(encoding="utf-8")
        )

    def test_every_drum_role_has_full_velocity_sample_coverage(self) -> None:
        catalog = load_sc_music_catalog(
            ROOT / "music" / "sc_expansion" / "sc_kit_grooves_v1.json"
        )
        roles = catalog.roles

        program = self.mapping["program_id"]
        role_keys = self.mapping["role_keys"]
        self.assertEqual(set(role_keys), roles)
        regions = [
            region
            for region in self.manifest["regions"]
            if region["program_id"] == program
        ]
        self.assertGreater(len(regions), 0)
        for role, sample_key in sorted(role_keys.items()):
            with self.subTest(role=role, sample_key=sample_key):
                covered: set[int] = set()
                for region in regions:
                    if region["key_lo"] <= sample_key <= region["key_hi"]:
                        covered.update(
                            range(region["velocity_lo"], region["velocity_hi"] + 1)
                        )
                self.assertTrue(
                    set(range(1, 128)).issubset(covered),
                    f"{role} -> GM key {sample_key} lacks velocity coverage",
                )

    def test_roles_map_to_matching_vsco_instrument_families(self) -> None:
        roles = self.mapping["role_keys"]
        self.assertEqual(roles["low_primary"], 36)
        self.assertEqual(roles["backbeat_primary"], 38)
        self.assertEqual(roles["timekeeper_primary"], 54)
        self.assertEqual(roles["timekeeper_open"], 51)
        self.assertEqual(roles["tonal_low"], 77)
        self.assertEqual(roles["tonal_high"], 76)
        self.assertEqual(roles["section_accent"], 49)
        self.assertEqual(roles["hand_low"], 65)

    def test_role_keys_do_not_claim_gong_scrapes_as_hihats(self) -> None:
        files = {item["id"]: item for item in self.manifest["files"]}
        program = self.mapping["program_id"]
        regions = [
            region
            for region in self.manifest["regions"]
            if region["program_id"] == program
        ]
        expected_fragments = {
            "low_primary": "BDrum",
            "backbeat_primary": "Snare",
            "timekeeper_primary": "Tamb",
            "timekeeper_open": "susCymb",
            "timeline_primary": "Cowbell",
            "tonal_low": "LogDrumLo",
            "tonal_high": "LogDrumHi",
        }
        for role, fragment in expected_fragments.items():
            key = self.mapping["role_keys"][role]
            names = {
                files[region["sample_id"]]["relative_path"]
                for region in regions
                if region["key_lo"] <= key <= region["key_hi"]
            }
            with self.subTest(role=role):
                self.assertTrue(any(fragment in name for name in names), names)
                self.assertFalse(any("gong" in name.casefold() for name in names))


if __name__ == "__main__":
    unittest.main()
