from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from catalog_provenance import (  # noqa: E402
    load_provenance_manifest,
    verify_catalogue_provenance,
)
from catalog_schema import read_versioned_catalog  # noqa: E402


class CatalogueProvenanceTests(unittest.TestCase):
    def test_manifest_hashes_counts_and_schema_routes_match(self) -> None:
        manifest_path = ROOT / "music" / "catalogue_provenance.json"
        entries = load_provenance_manifest(manifest_path)

        self.assertEqual(verify_catalogue_provenance(ROOT, entries), ())
        self.assertEqual(len(entries), 10)
        for entry in entries:
            self.assertTrue((ROOT / entry.schema).is_file(), entry.schema)
            self.assertTrue(entry.process)

    def test_changed_payload_is_detected(self) -> None:
        entries = load_provenance_manifest(ROOT / "music" / "catalogue_provenance.json")
        source = ROOT / entries[0].path
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            target = temporary_root / entries[0].path
            target.parent.mkdir(parents=True)
            data = json.loads(source.read_text(encoding="utf-8"))
            data["riffs"] = data["riffs"][:-1]
            target.write_text(json.dumps(data), encoding="utf-8")

            failures = verify_catalogue_provenance(temporary_root, entries[:1])

        self.assertEqual(len(failures), 2)
        self.assertTrue(any("sha256" in failure for failure in failures))
        self.assertTrue(any("count" in failure for failure in failures))

    def test_gamma_snapshot_has_unique_literal_keys_and_recorded_size(self) -> None:
        source = ROOT / "code" / "drum_gamma9001.py"
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        assignment = next(
            node for node in tree.body if isinstance(node, ast.AnnAssign)
        )
        self.assertIsInstance(assignment.value, ast.Dict)
        assert isinstance(assignment.value, ast.Dict)
        keys = [ast.literal_eval(key) for key in assignment.value.keys]
        self.assertEqual(len(keys), 121)
        self.assertEqual(len(set(keys)), len(keys))

    def test_wrong_catalogue_version_fails_at_the_schema_boundary(self) -> None:
        source = ROOT / "music" / "drums" / "drum_activity_timing.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["schema_version"] = 999
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "activity.json"
            target.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                r"activity\.json violates drum_activity_v1\.schema\.json "
                r"at data\.schema_version",
            ):
                read_versioned_catalog(
                    target,
                    "drum_activity_v1.schema.json",
                )


if __name__ == "__main__":
    unittest.main()
