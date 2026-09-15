from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
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
    DEFAULT_SAMPLE_BRANCH,
    DEFAULT_SAMPLE_COMMIT,
    SAMPLE_RECEIPT_NAME,
    SampleRepositoryError,
    ensure_sample_repository,
    prepare_user_runtime_config,
    validate_sample_tree,
    validate_sample_repository,
)


def make_clone(path: Path, origin: str = DEFAULT_REPOSITORY) -> None:
    porcelain.init(str(path))
    config = Repo(str(path)).get_config()
    config.set((b"remote", b"origin"), b"url", origin.encode())
    config.write_to_path()


def commit_clone(path: Path) -> str:
    marker = path / "fixture.wav"
    marker.write_bytes(b"sample")
    porcelain.add(str(path), paths=[marker.name])
    return porcelain.commit(
        str(path),
        message=b"fixture",
        author=b"Test <test@example.com>",
        committer=b"Test <test@example.com>",
    ).decode("ascii")


class SampleRepositoryTests(unittest.TestCase):
    def test_plain_sample_copy_is_validated_by_content_and_cached(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / "ordinary-copy"
            sample = samples / "Keys" / "fixture.wav"
            sample.parent.mkdir(parents=True)
            sample.write_bytes(b"sample audio")
            manifest = root / "vsco-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "fixture",
                                "relative_path": "Keys/fixture.wav",
                                "sha256": hashlib.sha256(b"sample audio").hexdigest(),
                            }
                        ],
                        "regions": [{"sample_id": "fixture"}],
                    }
                ),
                encoding="utf-8",
            )
            cache = root / "cache" / "vsco-validation.json"

            self.assertEqual(
                validate_sample_tree(samples, manifest, cache_path=cache),
                samples.resolve(),
            )
            self.assertTrue(cache.is_file())
            receipt = json.loads(
                (samples / SAMPLE_RECEIPT_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["file_count"], 1)
            self.assertEqual(
                receipt["files"],
                [
                    {
                        "relative_path": "Keys/fixture.wav",
                        "sha256": hashlib.sha256(b"sample audio").hexdigest(),
                    }
                ],
            )
            with patch("sample_repository.hashlib.file_digest") as digest:
                self.assertEqual(
                    validate_sample_tree(samples, manifest, cache_path=cache),
                    samples.resolve(),
                )
                digest.assert_not_called()

    def test_plain_sample_copy_with_changed_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / "ordinary-copy"
            samples.mkdir()
            sample = samples / "fixture.wav"
            sample.write_bytes(b"unexpected audio")
            manifest = root / "vsco-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "fixture",
                                "relative_path": "fixture.wav",
                                "sha256": hashlib.sha256(b"expected audio").hexdigest(),
                            }
                        ],
                        "regions": [{"sample_id": "fixture"}],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                SampleRepositoryError, "content differs from the supported set"
            ):
                validate_sample_tree(samples, manifest)

    def test_unreferenced_source_audio_is_not_required_or_receipted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / "runtime-subset"
            samples.mkdir()
            (samples / "used.wav").write_bytes(b"used")
            manifest = root / "vsco-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "used",
                                "relative_path": "used.wav",
                                "sha256": hashlib.sha256(b"used").hexdigest(),
                            },
                            {
                                "id": "unmapped",
                                "relative_path": "not-downloaded.wav",
                                "sha256": hashlib.sha256(b"unused").hexdigest(),
                            },
                        ],
                        "regions": [{"sample_id": "used"}],
                    }
                ),
                encoding="utf-8",
            )

            validate_sample_tree(samples, manifest)

            receipt = json.loads(
                (samples / SAMPLE_RECEIPT_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["file_count"], 1)
            self.assertEqual(
                [record["relative_path"] for record in receipt["files"]],
                ["used.wav"],
            )

    def test_direct_pcm_drum_reference_is_part_of_runtime_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / "samples"
            samples.mkdir()
            (samples / "melodic.wav").write_bytes(b"melodic")
            (samples / "drum.wav").write_bytes(b"drum")
            manifest = root / "vsco-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "melodic",
                                "relative_path": "melodic.wav",
                                "sha256": hashlib.sha256(b"melodic").hexdigest(),
                            },
                            {
                                "id": "drum",
                                "relative_path": "drum.wav",
                                "sha256": hashlib.sha256(b"drum").hexdigest(),
                            },
                        ],
                        "regions": [{"sample_id": "melodic"}],
                    }
                ),
                encoding="utf-8",
            )
            drums = root / "drums.json"
            drums.write_text(
                json.dumps({"sample_files": [{"source_sample_id": "drum"}]}),
                encoding="utf-8",
            )

            validate_sample_tree(
                samples,
                manifest,
                direct_reference_catalogue=drums,
            )

            receipt = json.loads(
                (samples / SAMPLE_RECEIPT_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(
                {record["relative_path"] for record in receipt["files"]},
                {"melodic.wav", "drum.wav"},
            )

    def test_changed_receipt_forces_content_revalidation_and_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / "samples"
            samples.mkdir()
            (samples / "fixture.wav").write_bytes(b"sample")
            manifest = root / "vsco-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "fixture",
                                "relative_path": "fixture.wav",
                                "sha256": hashlib.sha256(b"sample").hexdigest(),
                            }
                        ],
                        "regions": [{"sample_id": "fixture"}],
                    }
                ),
                encoding="utf-8",
            )
            cache = root / "cache.json"
            validate_sample_tree(samples, manifest, cache_path=cache)
            receipt_path = samples / SAMPLE_RECEIPT_NAME
            receipt_path.write_text("{}\n", encoding="utf-8")

            with patch(
                "sample_repository.hashlib.file_digest",
                wraps=hashlib.file_digest,
            ) as digest:
                validate_sample_tree(samples, manifest, cache_path=cache)
                digest.assert_called_once()
            self.assertEqual(
                json.loads(receipt_path.read_text(encoding="utf-8"))["file_count"],
                1,
            )

    def test_runtime_preparation_accepts_an_ordinary_sample_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frontend = root / "sc_version" / "qt_frontend"
            shipped = frontend / "config" / "supercollider.json"
            shipped.parent.mkdir(parents=True)
            config = json.loads(
                (FRONTEND / "config" / "supercollider.json").read_text(
                    encoding="utf-8"
                )
            )
            samples = root / "samples-copy"
            samples.mkdir()
            sample = samples / "fixture.wav"
            sample.write_bytes(b"sample audio")
            config["samples"]["vsco_root"] = str(samples)
            shipped.write_text(json.dumps(config), encoding="utf-8")

            manifest = root / "sc_version" / "supercollider" / "vsco-manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "fixture",
                                "relative_path": "fixture.wav",
                                "sha256": hashlib.sha256(b"sample audio").hexdigest(),
                            }
                        ],
                        "regions": [{"sample_id": "fixture"}],
                    }
                ),
                encoding="utf-8",
            )
            drum_catalogue = (
                frontend / "music" / "sc_expansion" / "sc_pcm_drumkits_v1.json"
            )
            drum_catalogue.parent.mkdir(parents=True)
            drum_catalogue.write_text(
                json.dumps({"sample_files": []}), encoding="utf-8"
            )

            target, runtime = prepare_user_runtime_config(
                shipped,
                user_root=root / "empty-user-root",
                install_samples=True,
            )

            self.assertEqual(runtime.samples.vsco_root, samples)
            self.assertTrue(target.is_file())
            self.assertTrue(
                (root / "empty-user-root" / "cache" / "vsco-validation.json").is_file()
            )
            self.assertTrue((samples / SAMPLE_RECEIPT_NAME).is_file())

    def test_cli_seeds_a_valid_config_in_a_completely_empty_home(self) -> None:
        """Cover the exact first source-run boundary used by run_local.sh."""

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            environment = os.environ.copy()
            environment.update(HOME=str(home), USERPROFILE=str(home))

            result = subprocess.run(
                [
                    sys.executable,
                    str(FRONTEND / "code" / "sample_repository.py"),
                    str(FRONTEND / "config" / "supercollider.json"),
                    "--without-samples",
                ],
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            target = home / ".omnichord" / "config" / "supercollider.json"
            self.assertEqual(Path(result.stdout.strip()).resolve(), target.resolve())
            persisted = json.loads(target.read_text(encoding="utf-8"))
            self.assertIs(type(persisted["server"]["max_buffers"]), int)
            self.assertEqual(persisted["server"]["max_buffers"], 8192)
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["protocol_version"], 2)

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
            https_commit = commit_clone(root / "https")
            ssh_commit = commit_clone(root / "ssh")
            commit_clone(root / "wrong")
            self.assertEqual(
                validate_sample_repository(
                    root / "https", DEFAULT_REPOSITORY, https_commit
                ),
                (root / "https").resolve(),
            )
            self.assertEqual(
                validate_sample_repository(root / "ssh", DEFAULT_REPOSITORY, ssh_commit),
                (root / "ssh").resolve(),
            )
            with self.assertRaisesRegex(SampleRepositoryError, "wrong Git origin"):
                validate_sample_repository(root / "wrong", DEFAULT_REPOSITORY)
            with self.assertRaisesRegex(SampleRepositoryError, "wrong Git commit"):
                validate_sample_repository(
                    root / "https", DEFAULT_REPOSITORY, "0" * 40
                )

    def test_missing_repository_is_cloned_to_final_path_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "VSCO-2-CE"
            manifest = root / "vsco-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "id": "fixture",
                                "relative_path": "fixture.wav",
                                "sha256": hashlib.sha256(b"sample").hexdigest(),
                            }
                        ],
                        "regions": [{"sample_id": "fixture"}],
                    }
                ),
                encoding="utf-8",
            )

            def fake_clone(url: str, target: str, **arguments: object) -> None:
                self.assertEqual(url, DEFAULT_REPOSITORY)
                self.assertEqual(arguments["depth"], 1)
                self.assertEqual(arguments["branch"], DEFAULT_SAMPLE_BRANCH)
                make_clone(Path(target), url)
                commit_clone(Path(target))

            with (
                patch("sample_repository.porcelain.clone", side_effect=fake_clone),
                patch(
                    "sample_repository.repository_commit",
                    return_value=DEFAULT_SAMPLE_COMMIT,
                ),
            ):
                result = ensure_sample_repository(
                    destination,
                    DEFAULT_REPOSITORY,
                    DEFAULT_SAMPLE_BRANCH,
                    DEFAULT_SAMPLE_COMMIT,
                    content_manifest=manifest,
                    validation_cache=root / "cache.json",
                )
            self.assertEqual(result, destination.resolve())
            self.assertEqual((destination / "fixture.wav").read_bytes(), b"sample")
            receipt = json.loads(
                (destination / SAMPLE_RECEIPT_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["branch"], DEFAULT_SAMPLE_BRANCH)
            self.assertEqual(receipt["commit"], DEFAULT_SAMPLE_COMMIT)
            self.assertFalse(any(destination.parent.glob(".VSCO-2-CE.clone-*")))

    def test_user_config_is_seeded_and_revision_one_default_is_migrated(self) -> None:
        shipped = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        old = json.loads(json.dumps(shipped))
        old["config_revision"] = 1
        old["samples"].pop("repository")
        old["samples"].pop("commit")
        old["samples"].pop("branch")
        old["server"].pop("max_buffers")
        old["server"].pop("gesture_voice_limit")
        old["samples"]["vsco_root"] = "~/sample_lib/VSCO-2-CE-1.1.0"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped_path = root / "shipped.json"
            shipped_path.write_text(json.dumps(shipped), encoding="utf-8")
            user_root = root / "home"
            existing = user_root / "config" / "supercollider.json"
            existing.parent.mkdir(parents=True)
            existing.write_text(json.dumps(old), encoding="utf-8")
            target, config = prepare_user_runtime_config(
                shipped_path,
                user_root=user_root,
                install_samples=False,
            )
            persisted = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["protocol_version"], 2)
            self.assertEqual(persisted["samples"]["commit"], DEFAULT_SAMPLE_COMMIT)
            self.assertEqual(persisted["samples"]["branch"], DEFAULT_SAMPLE_BRANCH)
            self.assertEqual(persisted["samples"]["vsco_root"], "~/VSCO-2-CE")
            self.assertEqual(persisted["server"]["max_buffers"], 8192)
            self.assertEqual(persisted["server"]["gesture_voice_limit"], 64)
            self.assertEqual(config.samples.repository, DEFAULT_REPOSITORY)
            self.assertEqual(
                target,
                (user_root / "config" / "supercollider.json").resolve(),
            )

    def test_revision_one_custom_location_is_preserved(self) -> None:
        data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        data["config_revision"] = 1
        data["samples"].pop("repository")
        data["samples"].pop("commit")
        data["samples"].pop("branch")
        data["server"].pop("max_buffers")
        data["server"].pop("gesture_voice_limit")
        data["samples"]["vsco_root"] = "/media/samples/VSCO-2-CE"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(
                (FRONTEND / "config" / "supercollider.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            existing = root / "user" / "config" / "supercollider.json"
            existing.parent.mkdir(parents=True)
            existing.write_text(json.dumps(data), encoding="utf-8")
            target, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )
            self.assertEqual(config.samples.vsco_root, Path("/media/samples/VSCO-2-CE"))
            self.assertIn(
                "/media/samples/VSCO-2-CE", target.read_text(encoding="utf-8")
            )

    def test_revision_two_protocol_and_missing_buffer_capacity_are_migrated(self) -> None:
        data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        data["config_revision"] = 2
        data["protocol_version"] = 1
        data["samples"].pop("commit")
        data["samples"].pop("branch")
        data["server"].pop("max_buffers")
        data["server"].pop("gesture_voice_limit")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(
                (FRONTEND / "config" / "supercollider.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            target = root / "user" / "config" / "supercollider.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(data), encoding="utf-8")

            migrated_path, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )

            persisted = json.loads(migrated_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["protocol_version"], 2)
            self.assertEqual(persisted["samples"]["commit"], DEFAULT_SAMPLE_COMMIT)
            self.assertEqual(persisted["samples"]["branch"], DEFAULT_SAMPLE_BRANCH)
            self.assertEqual(persisted["server"]["max_buffers"], 8192)
            self.assertEqual(persisted["server"]["gesture_voice_limit"], 64)
            self.assertEqual(config.server.max_buffers, 8192)
            self.assertEqual(config.server.gesture_voice_limit, 64)

    def test_revision_four_gains_the_shipped_gesture_boundary(self) -> None:
        shipped_data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(
                encoding="utf-8"
            )
        )
        existing_data = json.loads(json.dumps(shipped_data))
        existing_data["config_revision"] = 4
        existing_data["samples"].pop("branch")
        existing_data["server"].pop("gesture_voice_limit")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(json.dumps(shipped_data), encoding="utf-8")
            target = root / "user" / "config" / "supercollider.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(existing_data), encoding="utf-8")

            migrated_path, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )

            persisted = json.loads(migrated_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["server"]["gesture_voice_limit"], 64)
            self.assertEqual(config.server.gesture_voice_limit, 64)

    def test_revision_five_old_gesture_default_is_upgraded(self) -> None:
        shipped_data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(
                encoding="utf-8"
            )
        )
        existing_data = json.loads(json.dumps(shipped_data))
        existing_data["config_revision"] = 5
        existing_data["samples"].pop("branch")
        existing_data["server"]["gesture_voice_limit"] = 24
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(json.dumps(shipped_data), encoding="utf-8")
            target = root / "user" / "config" / "supercollider.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(existing_data), encoding="utf-8")

            migrated_path, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )

            persisted = json.loads(migrated_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["server"]["gesture_voice_limit"], 64)
            self.assertEqual(config.server.gesture_voice_limit, 64)

    def test_revision_five_custom_gesture_limit_is_preserved(self) -> None:
        shipped_data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(
                encoding="utf-8"
            )
        )
        existing_data = json.loads(json.dumps(shipped_data))
        existing_data["config_revision"] = 5
        existing_data["samples"].pop("branch")
        existing_data["server"]["gesture_voice_limit"] = 48
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(json.dumps(shipped_data), encoding="utf-8")
            target = root / "user" / "config" / "supercollider.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(existing_data), encoding="utf-8")

            migrated_path, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )

            persisted = json.loads(migrated_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["server"]["gesture_voice_limit"], 48)
            self.assertEqual(config.server.gesture_voice_limit, 48)

    def test_revision_six_source_pin_moves_to_shallow_runtime_branch(self) -> None:
        shipped_data = json.loads(
            (FRONTEND / "config" / "supercollider.json").read_text(
                encoding="utf-8"
            )
        )
        existing_data = json.loads(json.dumps(shipped_data))
        existing_data["config_revision"] = 6
        existing_data["samples"].pop("branch")
        existing_data["samples"]["commit"] = (
            "440300901dfe9275fd84e0b7763af1f8443ae62e"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shipped = root / "shipped.json"
            shipped.write_text(json.dumps(shipped_data), encoding="utf-8")
            target = root / "user" / "config" / "supercollider.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(existing_data), encoding="utf-8")

            migrated_path, config = prepare_user_runtime_config(
                shipped,
                user_root=root / "user",
                install_samples=False,
            )

            persisted = json.loads(migrated_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["config_revision"], 7)
            self.assertEqual(persisted["samples"]["branch"], DEFAULT_SAMPLE_BRANCH)
            self.assertEqual(persisted["samples"]["commit"], DEFAULT_SAMPLE_COMMIT)
            self.assertEqual(config.samples.branch, DEFAULT_SAMPLE_BRANCH)
            self.assertEqual(config.samples.commit, DEFAULT_SAMPLE_COMMIT)


if __name__ == "__main__":
    unittest.main()
