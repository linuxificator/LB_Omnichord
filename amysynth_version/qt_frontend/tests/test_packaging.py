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
        android_smoke = (
            FRONTEND / "packaging" / "android" / "test_android_apk.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("uses: ./.github/workflows/amy-regression.yml", release)
        self.assertIn("linux-appimages:", release)
        self.assertIn("macos-dmg:", release)
        self.assertIn("needs: [tests, release-metadata]", release)
        self.assertIn("android-packages:", release)
        self.assertIn("android-emulator:", release)
        self.assertIn("android-packages, android-emulator]", release)
        self.assertIn("hdiutil attach", release)
        self.assertIn(
            "bash amysynth_version/qt_frontend/packaging/android/"
            "test_android_apk.sh",
            release,
        )
        self.assertIn("if: always()", release)
        self.assertIn("set -euo pipefail", android_smoke)
        self.assertIn("AMY backend: external socket", android_smoke)
        self.assertIn("--windowed --package-smoke-test", release)
        self.assertIn("qml-chord-hold-promoted", android_smoke)
        self.assertLess(
            android_smoke.index('am force-stop "$package"'),
            android_smoke.index("amy-audio-capture.enable"),
        )
        self.assertIn(
            "branches: [main, testing/windows_smoke, integration/android_build]",
            release,
        )
        self.assertIn("refs/heads/integration/android_build", release)
        self.assertGreaterEqual(
            release.count("if: github.ref == 'refs/heads/main'"),
            3,
        )
        self.assertIn("needs.tests.result == 'success'", release)
        self.assertIn(
            "github.ref == 'refs/heads/testing/windows_smoke'",
            release,
        )
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
        self.assertIn("Windows-x86_64.zip", release)
        self.assertIn("Android-arm64.apk", release)
        self.assertIn("## Android arm64", release)
        self.assertIn("CI debug-signed", release)
        self.assertIn("## Windows native", release)
        self.assertIn("double-click", release)
        self.assertIn("LB_Omnichord.cmd", release)
        self.assertIn("process-only execution-policy bypass", release)
        self.assertIn("## Linux x64", release)
        self.assertIn("## Raspberry Pi 4 / 5", release)
        self.assertIn("## macOS Apple Silicon", release)
        self.assertIn("not signed with an Apple Developer ID", release)
        self.assertIn("drag `LB_Omnichord.app` to `Applications`", release)
        self.assertIn("`System Settings`", release)
        self.assertIn("`Privacy & Security`", release)
        self.assertIn("`Open Anyway`", release)
        self.assertIn("available for about one hour", release)
        self.assertIn("do not disable Gatekeeper", release)
        self.assertIn("support.apple.com/en-gb/guide/mac-help/mh40616/mac", release)
        self.assertNotIn("Windows via WSL2 / WSLg", release)

    def test_native_windows_contract_is_explicit_and_not_claimed_ready(self) -> None:
        contract = (FRONTEND / "docs" / "WINDOWS_NATIVE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("amy_service.exe", contract)
        self.assertIn("Windows named pipe", contract)
        self.assertIn("QLocalSocket", contract)
        self.assertIn("no physical validation yet", contract)
        self.assertIn("WSL_APPIMAGE_TESTING.md", contract)

    def test_windows_release_build_keeps_service_and_frontend_separate(self) -> None:
        workflow = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        build = (FRONTEND / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        launcher = (
            FRONTEND / "packaging" / "windows" / "run_windows.ps1"
        ).read_text(encoding="utf-8")
        click_launcher = (
            FRONTEND / "packaging" / "windows" / "LB_Omnichord.cmd"
        ).read_text(encoding="utf-8")
        main = (FRONTEND / "code" / "main.py").read_text(encoding="utf-8")
        core = (FRONTEND / "code" / "app_core.py").read_text(
            encoding="utf-8"
        )
        service = (
            FRONTEND / "packaging" / "windows" / "amy_service.c"
        ).read_text(encoding="utf-8")
        self.assertIn("windows-native:", workflow)
        self.assertIn("windows-native,", workflow)
        self.assertIn("amy_service.exe", build)
        self.assertIn("--name LB_Omnichord", build)
        self.assertIn("LB_Omnichord.cmd", build)
        self.assertIn("--hidden-import package_smoke", build)
        self.assertIn("--hidden-import PySide6.QtTest", build)
        self.assertIn("cmake --help", build)
        self.assertIn("Visual Studio 18 2026", build)
        self.assertIn("Visual Studio 17 2022", build)
        self.assertIn("Start-Process", launcher)
        self.assertIn("--pipe-name", launcher)
        self.assertIn("--ready-file", launcher)
        self.assertIn("--amy-local-name", launcher)
        self.assertIn("CreateNamedPipeA", service)
        self.assertIn("PIPE_REJECT_REMOTE_CLIENTS", service)
        self.assertIn("ReadFile", service)
        self.assertNotIn("AF_INET", service)
        self.assertNotIn("--tcp-port", launcher)
        self.assertNotIn("--amy-socket", launcher)
        self.assertIn("$SmokeTest", launcher)
        self.assertIn("--package-smoke-test", launcher)
        self.assertIn("QT_QPA_PLATFORM", launcher)
        self.assertIn("WaitForExit(30000)", launcher)
        self.assertIn("OMNICHORD_PACKAGE_SMOKE_STATUS", launcher)
        self.assertIn("Service errors:", launcher)
        self.assertNotIn("$service.ExitCode", launcher)
        self.assertIn(
            "AMY service smoke passed: [1-9][0-9]* wire commands, "
            "[1-9][0-9]* nonzero PCM samples",
            launcher,
        )
        self.assertIn("event-loop-exited", launcher)
        self.assertIn("qml-chord-press-observed", launcher)
        self.assertIn("active-chord-visible", launcher)
        self.assertIn("qml-chord-tap-released", launcher)
        self.assertIn("qml-chord-hold-promoted", launcher)
        self.assertIn("qml-chord-hold-released", launcher)
        self.assertIn("-ExecutionPolicy Bypass", click_launcher)
        self.assertIn('"%~dp0run_windows.ps1" %*', click_launcher)
        self.assertIn("pause", click_launcher)
        self.assertIn("if sys.stdout is None:", main)
        self.assertIn("if sys.stderr is None:", main)
        self.assertIn("fatal-error", main)
        self.assertIn("resolve_frontend_asset_root", core)
        self.assertIn('Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS")', core)
        self.assertIn("amy_add_message", service)
        self.assertIn("run_self_test", service)
        self.assertIn("amy_simple_fill_buffer", service)
        self.assertIn("AMY named-pipe connect failed:", service)
        self.assertIn("AMY named-pipe read failed:", service)
        self.assertIn("AMY service smoke passed:", service)
        self.assertIn("runs-on: windows-2025", workflow)
        self.assertIn(
            '& "$root\\LB_Omnichord.cmd" -Windowed -SmokeTest',
            workflow,
        )

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
        self.assertIn("--hidden-import package_smoke", dmg_script)
        self.assertIn("--hidden-import PySide6.QtTest", dmg_script)


if __name__ == "__main__":
    unittest.main()
