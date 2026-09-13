from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from drum_patterns import load_drum_pattern_catalog  # noqa: E402


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

    def test_roles_map_to_expected_gm_instrument_families(self) -> None:
        roles = self.mapping["role_keys"]
        self.assertEqual(roles["low_primary"], 36)
        self.assertEqual(roles["backbeat_primary"], 38)
        self.assertEqual(roles["timekeeper_primary"], 42)
        self.assertEqual(roles["tonal_low"], 41)
        self.assertEqual(roles["section_accent"], 49)
        self.assertEqual(roles["hand_low"], 64)


if __name__ == "__main__":
    unittest.main()
