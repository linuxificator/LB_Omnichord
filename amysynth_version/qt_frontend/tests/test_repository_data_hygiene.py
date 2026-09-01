from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
DESIGN_DATA = (
    REPOSITORY
    / "amysynth_version"
    / "design"
    / "rhythm_rework"
    / "new_patterns"
)
MANIFEST = DESIGN_DATA / "canonical_drum_data_manifest.json"


class RepositoryDataHygieneTests(unittest.TestCase):
    def test_canonical_drum_manifest_matches_runtime_files(self) -> None:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(payload["manifest_revision"], 1)
        root = (DESIGN_DATA / payload["canonical_root"]).resolve()
        self.assertEqual(root, (FRONTEND / "music" / "drums").resolve())

        records = payload["files"]
        self.assertEqual(len(records), 9)
        self.assertEqual(
            [record["name"] for record in records],
            sorted(record["name"] for record in records),
        )
        for record in records:
            path = root / record["name"]
            self.assertTrue(path.is_file(), path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, record["sha256"], path)

    def test_design_tree_does_not_duplicate_runtime_drum_json(self) -> None:
        runtime_hashes = {
            hashlib.sha256(path.read_bytes()).hexdigest(): path
            for path in (FRONTEND / "music" / "drums").glob("*.json")
        }
        duplicates = []
        for path in DESIGN_DATA.glob("*.json"):
            if path == MANIFEST:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in runtime_hashes:
                duplicates.append((path, runtime_hashes[digest]))
        self.assertEqual(duplicates, [])


if __name__ == "__main__":
    unittest.main()
