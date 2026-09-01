from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


FRONTEND = Path(__file__).resolve().parents[1]
PACKAGING = FRONTEND / "packaging"
sys.path.insert(0, str(PACKAGING))

from release_inputs import (  # noqa: E402
    append_github_environment,
    create_release_manifest,
    load_release_inputs,
)
import checkout_amy as checkout_module  # noqa: E402


SOURCE_COMMIT = "a" * 40
STAMP = "R20260901123456"


class ReleaseInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_release_inputs(PACKAGING / "release_inputs.json")

    def populate_release(self, directory: Path) -> None:
        for index, package in enumerate(self.inputs.packages, start=1):
            name = f"LB_Omnichord.{STAMP}.{package.suffix}"
            payload = f"package-{index}".encode()
            (directory / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (directory / f"{name}.sha256").write_text(
                f"{digest}  {name}\n",
                encoding="utf-8",
            )

    def test_one_manifest_accepts_exactly_five_packages_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.populate_release(root)
            output = root.parent / f"{root.name}-manifest.json"

            manifest = create_release_manifest(
                root,
                release_stamp=STAMP,
                source_commit=SOURCE_COMMIT,
                output=output,
                inputs=self.inputs,
            )

            self.assertEqual(len(manifest["packages"]), 5)
            self.assertEqual(
                {item["platform"] for item in manifest["packages"]},
                {item.platform for item in self.inputs.packages},
            )
            self.assertEqual(manifest["amy"]["commit"], self.inputs.amy.commit)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                manifest,
            )

    def test_missing_extra_and_incorrect_checksum_are_each_rejected(self) -> None:
        for mutation, expected in (
            ("missing", "missing="),
            ("extra", "extra="),
            ("checksum", "incorrect checksum"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.populate_release(root)
                first = f"LB_Omnichord.{STAMP}.{self.inputs.packages[0].suffix}"
                if mutation == "missing":
                    (root / first).unlink()
                elif mutation == "extra":
                    (root / "unexpected.txt").write_text("no", encoding="utf-8")
                else:
                    (root / f"{first}.sha256").write_text(
                        f"{'0' * 64}  {first}\n",
                        encoding="utf-8",
                    )

                with self.assertRaisesRegex(ValueError, expected):
                    create_release_manifest(
                        root,
                        release_stamp=STAMP,
                        source_commit=SOURCE_COMMIT,
                        output=root.parent / "manifest.json",
                        inputs=self.inputs,
                    )

    def test_github_environment_exports_the_same_amy_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-env"
            append_github_environment(output, self.inputs)
            values = dict(
                line.split("=", 1)
                for line in output.read_text(encoding="utf-8").splitlines()
            )

        self.assertEqual(values["AMY_REPO"], self.inputs.amy.repository)
        self.assertEqual(values["AMY_RELEASE_BRANCH"], self.inputs.amy.release_branch)
        self.assertEqual(values["AMY_COMMIT"], self.inputs.amy.commit)
        self.assertEqual(values["AMY_REF"], self.inputs.amy.commit)
        self.assertEqual(values["AMY_PCM_BANK"], self.inputs.amy.pcm_bank)

    def test_checkout_helper_verifies_branch_ancestry_and_exact_head(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str], *, capture: bool = False) -> str:
            commands.append(command)
            return self.inputs.amy.commit if capture else ""

        with tempfile.TemporaryDirectory() as directory, patch.object(
            checkout_module,
            "run",
            side_effect=fake_run,
        ):
            actual = checkout_module.checkout_amy(Path(directory) / "amy")

        self.assertEqual(actual, self.inputs.amy.commit)
        flattened = [" ".join(command) for command in commands]
        self.assertTrue(any("merge-base --is-ancestor" in line for line in flattened))
        self.assertTrue(any("checkout --detach" in line for line in flattened))
        self.assertTrue(any("rev-parse HEAD" in line for line in flattened))


if __name__ == "__main__":
    unittest.main()
