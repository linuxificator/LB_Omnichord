from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
PACKAGING = FRONTEND / "packaging"
sys.path.insert(0, str(PACKAGING))

from release_inputs import create_release_manifest, load_release_inputs  # noqa: E402
from release_sbom import create_spdx_sbom, write_spdx_sbom  # noqa: E402


STAMP = "R20260901123456"
SOURCE_COMMIT = "a" * 40


class ReleaseSbomTests(unittest.TestCase):
    def manifest(self, directory: Path) -> tuple[dict[str, object], Path]:
        inputs = load_release_inputs(PACKAGING / "release_inputs.json")
        for index, package in enumerate(inputs.packages):
            name = f"LB_Omnichord.{STAMP}.{package.suffix}"
            payload = f"payload-{index}".encode()
            (directory / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (directory / f"{name}.sha256").write_text(
                f"{digest}  {name}\n", encoding="utf-8"
            )
        output = directory.parent / f"{directory.name}-manifest.json"
        manifest = create_release_manifest(
            directory,
            release_stamp=STAMP,
            source_commit=SOURCE_COMMIT,
            output=output,
            inputs=inputs,
        )
        return manifest, output

    def test_spdx_describes_all_five_hashed_packages_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest, _ = self.manifest(Path(raw))
            sbom = create_spdx_sbom(manifest)

        self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
        self.assertEqual(len(sbom["documentDescribes"]), 5)
        app_packages = [
            package
            for package in sbom["packages"]
            if str(package["name"]).startswith("LB Omnichord (")
        ]
        self.assertEqual(len(app_packages), 5)
        self.assertTrue(all(len(package["checksums"]) == 1 for package in app_packages))
        self.assertTrue(all("copyrightText" in package for package in sbom["packages"]))
        relationships = sbom["relationships"]
        self.assertEqual(
            sum(item["relationshipType"] == "DESCRIBES" for item in relationships),
            5,
        )
        self.assertTrue(
            any(item["relationshipType"] == "BUILD_DEPENDENCY_OF" for item in relationships)
        )

    def test_sbom_is_deterministic_and_rejects_an_incomplete_release(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest, manifest_path = self.manifest(Path(raw))
            first = Path(raw).parent / f"{Path(raw).name}-first.spdx.json"
            second = Path(raw).parent / f"{Path(raw).name}-second.spdx.json"
            write_spdx_sbom(manifest_path, first)
            write_spdx_sbom(manifest_path, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            incomplete = json.loads(json.dumps(manifest))
            incomplete["packages"].pop()
            with self.assertRaisesRegex(ValueError, "exactly five"):
                create_spdx_sbom(incomplete)


if __name__ == "__main__":
    unittest.main()
