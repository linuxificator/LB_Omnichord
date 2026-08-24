from __future__ import annotations

import re
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]


class PackagingContracts(unittest.TestCase):
    def test_release_is_gated_by_complete_reusable_test_workflow(self) -> None:
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        regression = (
            REPOSITORY / ".github" / "workflows" / "amy-regression.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("uses: ./.github/workflows/amy-regression.yml", release)
        self.assertIn("linux-appimages:", release)
        self.assertIn("macos-dmg:", release)
        self.assertIn("needs: [tests, release-metadata]", release)
        self.assertIn("needs: [release-metadata, linux-appimages, macos-dmg]", release)
        self.assertIn("hdiutil attach", release)
        self.assertIn("AMY backend: external socket", release)
        self.assertIn("workflow_call:", regression)
        self.assertIn("ALSA_CONFIG_PATH:", regression)
        self.assertTrue((FRONTEND / "tests" / "alsa-null.conf").is_file())
        for suite in (
            "unit",
            "frontend",
            "serial",
            "presets",
            "native-controls",
            "native-rhythm",
        ):
            self.assertIn(f"- {suite}", regression)

    def test_release_names_and_assets_follow_the_timestamp_contract(self) -> None:
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("date -u +%Y%m%dT%H%M%S", release)
        self.assertIn('echo "tag=R${instant}"', release)
        self.assertIn('echo "stamp=R${instant/T/}"', release)
        self.assertIn("gh release create", release)
        self.assertIn("Linux-x86_64.AppImage", release)
        self.assertIn("RaspberryPi-aarch64.AppImage", release)
        self.assertIn("macOS-arm64.dmg", release)
        self.assertIn("## Linux x64", release)
        self.assertIn("## Raspberry Pi 4 / 5", release)
        self.assertIn("## macOS Apple Silicon", release)

    def test_appimage_launcher_preserves_the_process_boundary(self) -> None:
        entry = (FRONTEND / "packaging" / "appimage_entry.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("subprocess.Popen", entry)
        self.assertIn('"--amy-service"', entry)
        self.assertIn('"--amy-socket"', entry)
        self.assertIn("local_amy_service.main()", entry)
        self.assertIn("configure_frontend_asset_paths(app_core)", entry)
        self.assertLess(entry.index("import app_core"), entry.index("import main"))
        self.assertNotIn("amy.live(", entry)

    def test_release_stamp_validation_matches_asset_format(self) -> None:
        build_script = (FRONTEND / "packaging" / "build_appimage.sh").read_text(
            encoding="utf-8"
        )
        match = re.search(r"R(?:\[0-9\]){14}", build_script)
        self.assertIsNotNone(match)
        self.assertIn(
            "LB_Omnichord.${release_stamp}.${platform_name}.AppImage",
            build_script,
        )
        dmg_script = (FRONTEND / "packaging" / "build_macos_dmg.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("LB_Omnichord.${release_stamp}.macOS-arm64.dmg", dmg_script)


if __name__ == "__main__":
    unittest.main()
