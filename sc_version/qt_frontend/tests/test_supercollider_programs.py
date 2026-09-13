from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from supercollider_programs import (  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
