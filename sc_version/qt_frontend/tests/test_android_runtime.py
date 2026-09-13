from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))

from runtime_paths import resolve_frontend_asset_root  # noqa: E402
from runtime_platform_adapters import resolve_package_runtime  # noqa: E402


class AndroidRuntimeTests(unittest.TestCase):
    def test_flat_android_stage_is_the_frontend_asset_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            for name in ("config", "gui", "instruments", "music"):
                (stage / name).mkdir()

            self.assertEqual(
                resolve_frontend_asset_root(stage, stage / "frozen"),
                stage,
            )

            source_code = stage / "source" / "code"
            source_code.mkdir(parents=True)
            frozen = stage / "frozen"
            self.assertEqual(
                resolve_frontend_asset_root(source_code, frozen),
                frozen,
            )

    def test_android_defaults_to_the_aar_socket_in_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files_dir = Path(directory)
            runtime = resolve_package_runtime(
                platform_name="android",
                private_files_dir=files_dir,
                amy_socket=None,
                amy_local_name=None,
            )

            self.assertEqual(runtime.amy_socket, str(files_dir / "amy.sock"))

    def test_explicit_transport_remains_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = resolve_package_runtime(
                platform_name="android",
                private_files_dir=Path(directory),
                amy_socket="/diagnostic/amy.sock",
                amy_local_name=None,
            )

            self.assertEqual(runtime.amy_socket, "/diagnostic/amy.sock")

    def test_other_platforms_are_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = resolve_package_runtime(
                platform_name="offscreen",
                private_files_dir=Path(directory),
                amy_socket=None,
                amy_local_name=None,
            )

            self.assertIsNone(runtime.amy_socket)


if __name__ == "__main__":
    unittest.main()
