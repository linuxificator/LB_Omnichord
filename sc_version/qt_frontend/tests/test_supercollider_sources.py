from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SC_ROOT = ROOT / "supercollider"


class SuperColliderSourceLockTests(unittest.TestCase):
    def test_pinned_sclork_inventory_and_license_are_complete(self) -> None:
        lock = json.loads((SC_ROOT / "source-lock.json").read_text(encoding="utf-8"))
        source = lock["sclork_synths"]
        vendor = SC_ROOT / "vendor" / "SCLOrkSynths"
        definitions = sorted((vendor / "SynthDefs").rglob("*.scd"))

        self.assertEqual(len(definitions), source["definition_count"])
        self.assertEqual(
            hashlib.sha256((vendor / "LICENSE").read_bytes()).hexdigest(),
            source["license_sha256"],
        )

        lines = []
        for path in definitions:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            relative = path.relative_to(vendor).as_posix()
            lines.append(f"{digest}  {relative}\n")
        manifest_digest = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
        self.assertEqual(manifest_digest, source["definition_manifest_sha256"])

    def test_vendor_tree_contains_no_demo_or_repository_metadata(self) -> None:
        vendor = SC_ROOT / "vendor" / "SCLOrkSynths"
        self.assertFalse((vendor / ".git").exists())
        self.assertFalse((vendor / "pbind-demos").exists())
        self.assertFalse((vendor / "in-process").exists())


if __name__ == "__main__":
    unittest.main()
