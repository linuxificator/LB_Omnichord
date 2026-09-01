from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))

from runtime_paths import resolve_frontend_asset_root  # noqa: E402
from runtime_platform_adapters import (  # noqa: E402
    ANDROID_SMOKE_ENABLE,
    ANDROID_SMOKE_STATUS,
    resolve_package_runtime,
)


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
                package_smoke_test=False,
            )

            self.assertIsNone(runtime.smoke_status)
            self.assertEqual(runtime.amy_socket, str(files_dir / "amy.sock"))
            self.assertFalse(runtime.package_smoke_test)

    def test_explicit_transport_remains_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = resolve_package_runtime(
                platform_name="android",
                private_files_dir=Path(directory),
                amy_socket="/diagnostic/amy.sock",
                amy_local_name=None,
                package_smoke_test=False,
            )

            self.assertEqual(runtime.amy_socket, "/diagnostic/amy.sock")

    def test_android_marker_arms_existing_packaged_qml_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files_dir = Path(directory)
            marker = files_dir / ANDROID_SMOKE_ENABLE
            stale_status = files_dir / ANDROID_SMOKE_STATUS
            marker.touch()
            stale_status.write_text("stale\n", encoding="utf-8")
            runtime = resolve_package_runtime(
                platform_name="AnDrOiD",
                private_files_dir=files_dir,
                amy_socket=None,
                amy_local_name=None,
                package_smoke_test=False,
            )

            self.assertEqual(runtime.smoke_status, stale_status)
            self.assertTrue(runtime.package_smoke_test)
            self.assertFalse(marker.exists())
            self.assertFalse(stale_status.exists())

    def test_other_platforms_are_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = resolve_package_runtime(
                platform_name="offscreen",
                private_files_dir=Path(directory),
                amy_socket=None,
                amy_local_name=None,
                package_smoke_test=False,
            )

            self.assertIsNone(runtime.smoke_status)
            self.assertIsNone(runtime.amy_socket)
            self.assertFalse(runtime.package_smoke_test)


if __name__ == "__main__":
    unittest.main()
