from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
sys.path.insert(0, str(PACKAGING))

from supercollider_release_evidence import create_release_evidence  # noqa: E402


class SuperColliderReleaseEvidenceTests(unittest.TestCase):
    def test_manifest_and_spdx_describe_one_exact_sc_package(self) -> None:
        inputs = json.loads(
            (PACKAGING / "supercollider_release_inputs.json").read_text()
        )
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / (
                "LB_Omnichord.SC.R20260914123456.Linux-x86_64.AppImage"
            )
            package.write_bytes(b"tested-package")
            manifest, sbom = create_release_evidence(
                package=package,
                release_stamp="R20260914123456",
                source_commit="a" * 40,
                inputs=inputs,
                inputs_root=PACKAGING,
            )

        digest = hashlib.sha256(b"tested-package").hexdigest()
        self.assertEqual(manifest["edition"], "supercollider")
        self.assertEqual(manifest["release_tag"], "R20260914T123456-SC")
        self.assertEqual(manifest["package"]["sha256"], digest)
        self.assertFalse(manifest["external_sample_assets"]["bundled"])
        self.assertEqual(
            len(manifest["external_sample_assets"]["manifest_sha256"]), 64
        )
        self.assertEqual(
            len(manifest["external_sample_assets"]["source_catalog_sha256"]),
            64,
        )
        self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
        self.assertEqual(len(sbom["documentDescribes"]), 1)
        app = next(
            item for item in sbom["packages"] if item["name"].startswith("LB ")
        )
        self.assertEqual(app["checksums"][0]["checksumValue"], digest)
        relationships = {item["relationshipType"] for item in sbom["relationships"]}
        self.assertEqual(relationships, {"DESCRIBES", "DEPENDS_ON", "CONTAINS"})
        self.assertEqual(sbom["annotations"][0]["annotatedElement"], app["SPDXID"])
        self.assertNotIn("SPDXID", sbom["annotations"][0])

    def test_invalid_pin_or_source_commit_is_rejected(self) -> None:
        inputs = json.loads(
            (PACKAGING / "supercollider_release_inputs.json").read_text()
        )
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package.AppImage"
            package.write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "full lowercase Git SHA"):
                create_release_evidence(
                    package=package,
                    release_stamp="R20260914123456",
                    source_commit="short",
                    inputs=inputs,
                )
            inputs["supercollider"]["version"] = "latest"
            with self.assertRaisesRegex(ValueError, "pinned version"):
                create_release_evidence(
                    package=package,
                    release_stamp="R20260914123456",
                    source_commit="b" * 40,
                    inputs=inputs,
                )


if __name__ == "__main__":
    unittest.main()
