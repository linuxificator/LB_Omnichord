from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))

from app_core import (
    ANDROID_SMOKE_ENABLE,
    ANDROID_SMOKE_STATUS,
    configure_android_runtime,
)


def arguments(**updates: object) -> argparse.Namespace:
    values = {
        "amy_socket": None,
        "amy_local_name": None,
        "package_smoke_test": False,
    }
    values.update(updates)
    return argparse.Namespace(**values)


class AndroidRuntimeTests(unittest.TestCase):
    def test_android_defaults_to_the_aar_socket_in_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files_dir = Path(directory)
            args = arguments()

            status = configure_android_runtime(
                args,
                platform_name="android",
                files_dir=files_dir,
            )

            self.assertIsNone(status)
            self.assertEqual(args.amy_socket, str(files_dir / "amy.sock"))
            self.assertFalse(args.package_smoke_test)

    def test_explicit_transport_remains_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = arguments(amy_socket="/diagnostic/amy.sock")

            configure_android_runtime(
                args,
                platform_name="android",
                files_dir=Path(directory),
            )

            self.assertEqual(args.amy_socket, "/diagnostic/amy.sock")

    def test_android_marker_arms_existing_packaged_qml_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files_dir = Path(directory)
            marker = files_dir / ANDROID_SMOKE_ENABLE
            stale_status = files_dir / ANDROID_SMOKE_STATUS
            marker.touch()
            stale_status.write_text("stale\n", encoding="utf-8")
            args = arguments()

            status = configure_android_runtime(
                args,
                platform_name="AnDrOiD",
                files_dir=files_dir,
            )

            self.assertEqual(status, stale_status)
            self.assertTrue(args.package_smoke_test)
            self.assertFalse(marker.exists())
            self.assertFalse(stale_status.exists())

    def test_other_platforms_are_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = arguments()

            status = configure_android_runtime(
                args,
                platform_name="offscreen",
                files_dir=Path(directory),
            )

            self.assertIsNone(status)
            self.assertIsNone(args.amy_socket)
            self.assertFalse(args.package_smoke_test)


if __name__ == "__main__":
    unittest.main()
