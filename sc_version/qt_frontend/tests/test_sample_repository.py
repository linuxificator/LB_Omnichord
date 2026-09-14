from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from dulwich import porcelain
from dulwich.repo import Repo


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))

from sample_repository import (  # noqa: E402
    DEFAULT_REPOSITORY,
    SampleRepositoryError,
    ensure_sample_repository,
    prepare_user_runtime_config,
    validate_sample_repository,
)


def make_clone(path: Path, origin: str = DEFAULT_REPOSITORY) -> None:
    porcelain.init(str(path))
    config = Repo(str(path)).get_config()
    config.set((b"remote", b"origin"), b"url", origin.encode())
    config.write_to_path()


class SampleRepositoryTests(unittest.TestCase):
    def test_existing_non_repository_is_rejected_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                SampleRepositoryError,
                "not a readable Git clone",
            ):
                validate_sample_repository(Path(temporary), DEFAULT_REPOSITORY)

    def test_origin_identity_accepts_https_and_ssh_but_rejects_other_forks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_clone(root / "https")
            make_clone(root / "ssh", "git@github.com:linuxificator/VSCO-2-CE.git")
            make_clone(root / "wrong", "https://github.com/sgossner/VSCO-2-CE.git")
            self.assertEqual(
                validate_sample_repository(root / "https", DEFAULT_REPOSITORY),
                (root / "https").resolve(),
            )
            self.assertEqual(
                validate_sample_repository(root / "ssh", DEFAULT_REPOSITORY),
                (root / "ssh").resolve(),
            )
            with self.assertRaisesRegex(SampleRepositoryError, "wrong Git origin"):
                validate_sample_repository(root / "wrong", DEFAULT_REPOSITORY)

    def test_missing_repository_is_cloned_to_final_path_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "VSCO-2-CE"

            def fake_clone(url: str, target: str, **_arguments: object) -> None:
                self.assertEqual(url, DEFAULT_REPOSITORY)
                make_clone(Path(target), url)
                (Path(target) / "fixture.wav").write_bytes(b"sample")

            with patch("sample_repository.porcelain.clone", side_effect=fake_clone):
                result = ensure_sample_repository(destination, DEFAULT_REPOSITORY)
            self.assertEqual(result, destination.resolve())
            self.assertEqual((destination / "fixture.wav").read_bytes(), b"sample")
            self.assertFalse(any(destination.parent.glob(".VSCO-2-CE.clone-*")))

    def test_user_config_is_seeded_and_revision_one_default_is_migrated(self) -> None:
        shipped = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        old = json.loads(json.dumps(shipped))
        old["config_revision"] = 1
        old["samples"].pop("repository")
        old["samples"]["vsco_root"] = "~/sample_lib/VSCO-2-CE-1.1.0"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped_path = root / "shipped.json"
            shipped_path.write_text(json.dumps(old), encoding="utf-8")
            user_root = root / "home"
            target, config = prepare_user_runtime_config(
                shipped_path,
                user_root=user_root,
                install_samples=False,
            )
            persisted = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 2)
            self.assertEqual(persisted["samples"]["vsco_root"], "~/VSCO-2-CE")
            self.assertEqual(config.samples.repository, DEFAULT_REPOSITORY)
            self.assertEqual(target, user_root / "config" / "supercollider.json")

    def test_revision_one_custom_location_is_preserved(self) -> None:
        data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        data["config_revision"] = 1
        data["samples"].pop("repository")
        data["samples"]["vsco_root"] = "/media/samples/VSCO-2-CE"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(json.dumps(data), encoding="utf-8")
            target, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )
            self.assertEqual(config.samples.vsco_root, Path("/media/samples/VSCO-2-CE"))
            self.assertIn(
                "/media/samples/VSCO-2-CE", target.read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
