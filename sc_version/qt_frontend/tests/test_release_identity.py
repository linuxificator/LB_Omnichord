from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from release_identity import (  # noqa: E402
    RELEASE_NAME_ENV,
    active_release_name,
    configure_release_environment,
    read_release_name,
    release_user_root,
    validate_release_name,
    write_release_identity,
)


class ReleaseIdentityTests(unittest.TestCase):
    def test_release_name_is_safe_as_a_single_directory_component(self) -> None:
        self.assertEqual(
            validate_release_name("R20260916T120000-SC"),
            "R20260916T120000-SC",
        )
        for unsafe in ("", ".", "..", "../main", "SC/current", "contains space"):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                validate_release_name(unsafe)

    def test_identity_round_trip_and_environment_agreement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release_identity.json"
            write_release_identity(path, "R20260916T120000-SC")
            self.assertEqual(read_release_name(path), "R20260916T120000-SC")
            self.assertEqual(json.loads(path.read_text())["schema_revision"], 1)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    configure_release_environment(path), "R20260916T120000-SC"
                )
                self.assertEqual(active_release_name(), "R20260916T120000-SC")

    def test_different_releases_have_disjoint_user_roots(self) -> None:
        home = Path("/tmp/lb-omnichord-release-test-home")
        with patch.dict(os.environ, {RELEASE_NAME_ENV: "release-one"}):
            first = release_user_root(home=home)
        with patch.dict(os.environ, {RELEASE_NAME_ENV: "release-two"}):
            second = release_user_root(home=home)
        self.assertEqual(first, home / ".omnichord" / "release-one")
        self.assertEqual(second, home / ".omnichord" / "release-two")
        self.assertNotEqual(first, second)

    def test_packaged_identity_refuses_an_external_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release_identity.json"
            write_release_identity(path, "packaged-SC")
            with patch.dict(
                os.environ, {RELEASE_NAME_ENV: "different-SC"}, clear=True
            ), self.assertRaisesRegex(RuntimeError, "disagrees"):
                configure_release_environment(path)


if __name__ == "__main__":
    unittest.main()
