from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]


class PackagingContracts(unittest.TestCase):
    def test_catalogue_schemas_and_provenance_ship_on_every_platform(self) -> None:
        appimage = (
            FRONTEND / "packaging" / "build_appimage.sh"
        ).read_text(encoding="utf-8")
        macos = (
            FRONTEND / "packaging" / "build_macos_dmg.sh"
        ).read_text(encoding="utf-8")
        windows = (
            FRONTEND / "packaging" / "build_windows.ps1"
        ).read_text(encoding="utf-8")
        android = (
            FRONTEND / "packaging" / "android" / "build_android.py"
        ).read_text(encoding="utf-8")

        self.assertIn('--add-data "$frontend_dir/music:music"', appimage)
        self.assertIn('--add-data "$frontend_dir/music:music"', macos)
        self.assertIn("'music');music", windows)
        self.assertIn('ASSET_DIRECTORIES = ("config", "gui", "instruments", "music")', android)
        self.assertTrue((FRONTEND / "music" / "catalogue_provenance.json").is_file())
        self.assertEqual(
            len(tuple((FRONTEND / "music" / "schema").glob("*.schema.json"))),
            5,
        )

    def test_network_permissions_match_current_release_targets(self) -> None:
        macos = (
            FRONTEND / "packaging" / "build_macos_dmg.sh"
        ).read_text(encoding="utf-8")
        android = (
            FRONTEND / "packaging" / "android" / "build_android.py"
        ).read_text(encoding="utf-8")

        self.assertIn("NSLocalNetworkUsageDescription", macos)
        self.assertLess(
            macos.index("NSLocalNetworkUsageDescription"),
            macos.index("codesign --force"),
        )
        self.assertIn('"android.api": "36"', android)
        self.assertIn('"android.permissions": "INTERNET"', android)
        self.assertNotIn("ACCESS_LOCAL_NETWORK", android)

    def test_every_platform_uses_one_amy_release_branch_and_commit(self) -> None:
        workflows = [
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml",
            REPOSITORY / ".github" / "workflows" / "amy-regression.yml",
        ]
        release_inputs = json.loads(
            (FRONTEND / "packaging" / "release_inputs.json").read_text(
                encoding="utf-8"
            )
        )
        release_branch = release_inputs["amy"]["release_branch"]
        release_commit = release_inputs["amy"]["commit"]
        pcm_bank = release_inputs["amy"]["pcm_bank"]

        for workflow_path in workflows:
            workflow = workflow_path.read_text(encoding="utf-8")
            self.assertIn("packaging/release_inputs.py", workflow)
            self.assertIn("packaging/checkout_amy.py", workflow)
            self.assertNotIn(release_branch, workflow)
            self.assertNotIn(release_commit, workflow)
            self.assertNotIn(
                "25213785696dd40e6cce59ab428e560a410d240f",
                workflow,
            )
            self.assertNotIn(
                "20f714a6ed309077a2a4fcca1f998e552cc7510a",
                workflow,
            )

        checkout_helper = (
            FRONTEND / "packaging" / "checkout_amy.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"merge-base",', checkout_helper)
        self.assertIn('"--is-ancestor",', checkout_helper)
        self.assertIn('"rev-parse", "HEAD"', checkout_helper)

        release = workflows[0].read_text(encoding="utf-8")
        self.assertIn("## Build provenance", release)
        self.assertIn("\\`$AMY_RELEASE_BRANCH\\`", release)
        self.assertIn("\\`$AMY_COMMIT\\`", release)
        self.assertEqual(pcm_bank, "gamma9001")
        self.assertIn('AMY_PCM_BANK="$AMY_PCM_BANK"', release)
        for workflow_path in workflows:
            workflow = workflow_path.read_text(encoding="utf-8")
            self.assertIn("amy_set_gamma9001_pcm", workflow)
            self.assertIn("gamma9001_pcm_data", workflow)
        shipped_config = json.loads(
            (FRONTEND / "config" / "amy_config.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(shipped_config["drums"]["kit"], pcm_bank)
        self.assertNotIn("amy-tiny-bank.patch", release)
        self.assertFalse(
            (FRONTEND / "packaging" / "amy-tiny-bank.patch").exists()
        )

        contract = (FRONTEND / "packaging" / "AMY_RELEASE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(release_branch, contract)
        self.assertIn(release_commit, contract)
        self.assertIn("every supported platform succeeds", contract)

    def test_platform_logic_is_limited_to_runtime_adapters(self) -> None:
        core = (FRONTEND / "code" / "app_core.py").read_text(
            encoding="utf-8"
        )
        architecture = (
            REPOSITORY / "amysynth_version" / "design" / "architecture.md"
        ).read_text(encoding="utf-8")
        runtime_adapter = (
            FRONTEND / "code" / "runtime_platform_adapters.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('casefold() != "android"', core)
        self.assertEqual(runtime_adapter.count('casefold() != "android"'), 1)
        self.assertNotIn("sys.platform", core)
        self.assertNotIn("platform.system", core)
        self.assertIn("named adapters supplied by the", architecture)
        self.assertIn("single composition root", architecture)
        self.assertRegex(architecture, r"Asset-root\s+discovery")

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
        self.assertIn("Audio capture armed: 384000 frames", android_smoke)
        self.assertIn("--min-peak-dbfs -26.0", android_smoke)
        self.assertIn("smoke-audio-levels-full", android_smoke)
        self.assertIn("--windowed --package-smoke-test", release)
        self.assertIn("qml-chord-hold-promoted", android_smoke)
        self.assertIn("qml-slider-release-visible", android_smoke)
        self.assertLess(
            android_smoke.index('am force-stop "$package"'),
            android_smoke.index("amy-audio-capture.enable"),
        )
        self.assertIn("warmup_ready=0", android_smoke)
        self.assertIn("for warmup_attempt in {1..3}", android_smoke)
        self.assertIn('pidof "$package"', android_smoke)
        self.assertIn("break 2", android_smoke)
        self.assertIn("'python:I' '*:S'", android_smoke)
        self.assertIn('test "$warmup_ready" -eq 1', android_smoke)
        self.assertIn(
            "branches: [main, testing/windows_smoke, integration/android_build]",
            release,
        )
        self.assertIn("refs/heads/integration/android_build", release)
        self.assertGreaterEqual(
            release.count("github.event_name == 'workflow_dispatch'"),
            5,
        )
        self.assertIn(
            "publish-release:\n    if: github.ref == 'refs/heads/main'",
            release,
        )
        self.assertIn(
            "refresh-readme-screenshots:\n"
            "    if: github.ref == 'refs/heads/main'",
            release,
        )
        self.assertIn("needs.tests.result == 'success'", release)
        self.assertIn(
            "github.ref == 'refs/heads/testing/windows_smoke'",
            release,
        )
        self.assertIn("workflow_call:", regression)
        self.assertIn("default: matrix", regression)
        self.assertIn(
            "if: inputs.suite == '' || inputs.suite == 'matrix'",
            regression,
        )
        self.assertIn(
            "if: inputs.suite != '' && inputs.suite != 'matrix'",
            regression,
        )
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

    def test_midi_input_tech_contracts_are_in_build_unit_suite(self) -> None:
        runner = (FRONTEND / "tests" / "run_tests.py").read_text(
            encoding="utf-8"
        )
        regression = (
            REPOSITORY / ".github" / "workflows" / "amy-regression.yml"
        ).read_text(encoding="utf-8")
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        midi_tests = (
            FRONTEND / "tests" / "test_midi_input_adapters.py"
        ).read_text(encoding="utf-8")

        self.assertIn('TESTS.glob("test_*.py")', runner)
        self.assertIn("- unit", regression)
        self.assertIn(
            "python tests/run_tests.py --suite '${{ matrix.suite }}'",
            regression,
        )
        self.assertIn("uses: ./.github/workflows/amy-regression.yml", release)
        for expected in (
            "test_package_profiles_select_only_their_capability_data",
            "test_enabled_linux_port_starts_two_raw_and_one_sequencer_reader",
            "test_unavailable_adapters_share_lifecycle_and_status_contract",
            "test_disabled_linux_port_starts_no_native_readers",
            "test_qt_boundary_drains_out_of_order_delivery_before_dispatch",
        ):
            self.assertIn(expected, midi_tests)

    def test_every_frontend_package_runs_external_input_acceptance(self) -> None:
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        windows = (
            FRONTEND / "packaging" / "windows" / "run_windows.ps1"
        ).read_text(encoding="utf-8")
        android = (
            FRONTEND / "packaging" / "android" / "test_android_apk.sh"
        ).read_text(encoding="utf-8")
        package_test = (
            FRONTEND / "tests" / "test_package_chord_input.py"
        ).read_text(encoding="utf-8")

        self.assertGreaterEqual(release.count("--package-smoke-test"), 2)
        for checkpoint in (
            "midi-native-capability-verified",
            "osc-external-process-rotary-observed",
            "osc-external-process-button-observed",
            "osc-external-process-activity-observed",
        ):
            with self.subTest(checkpoint=checkpoint):
                self.assertGreaterEqual(release.count(checkpoint), 2)
                self.assertIn(checkpoint, windows)
                self.assertIn(checkpoint, android)
                self.assertIn(checkpoint, package_test)
        self.assertGreaterEqual(
            release.count("tests/support/external_input_peer.py osc"),
            2,
        )
        self.assertIn("external_input_peer.py", android)
        self.assertIn("toybox nc -u", android)

    def test_screenshots_refresh_only_after_a_successful_release(self) -> None:
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("refresh-readme-screenshots:", release)
        self.assertIn("needs: [publish-release, release-metadata]", release)
        self.assertNotIn("validation_only:", release)
        self.assertNotIn("inputs.validation_only", release)
        self.assertNotIn("actions: write", release)
        self.assertIn("contents: write", release)
        self.assertIn(
            "python amysynth_version/qt_frontend/capture_screenshots.py",
            release,
        )
        self.assertIn(
            "python amysynth_version/qt_frontend/tools/"
            "update_release_screenshots.py",
            release,
        )
        self.assertIn("--release-tag", release)
        self.assertIn("README.md", release)
        self.assertIn("amysynth_version/qt_frontend/screenshots", release)
        self.assertIn('git add -A -- "${changed_files[@]}"', release)
        self.assertIn("git diff --quiet --", release)
        self.assertIn("git push origin HEAD:main", release)
        self.assertIn("-m 'skip-rebuild: README screenshots only'", release)
        self.assertIn("-m 'skip-checks:true'", release)
        self.assertNotIn("gh workflow run desktop-release.yml", release)
        self.assertEqual(
            release.count("git commit -m 'Refresh README screenshots'"),
            1,
        )

    def test_release_names_and_assets_follow_the_timestamp_contract(self) -> None:
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("date -u +%Y%m%dT%H%M%S", release)
        self.assertIn('echo "tag=R${instant}"', release)
        self.assertIn('echo "stamp=R${instant/T/}"', release)
        self.assertIn("gh release create", release)
        self.assertIn("release-manifest.json", release)
        self.assertIn("release_sbom.py", release)
        self.assertIn("https://spdx.dev/Document/v2.3", release)
        self.assertIn("actions/attest@", release)
        self.assertEqual(release.count("actions/attest@"), 2)
        self.assertIn("gh attestation verify", release)
        self.assertIn("provenance.sigstore.json", release)
        self.assertIn("sbom.sigstore.json", release)
        self.assertIn("id-token: write", release)
        self.assertIn("attestations: write", release)
        self.assertEqual(release.count("id-token: write"), 1)
        self.assertEqual(release.count("attestations: write"), 1)
        self.assertIn("release_inputs.py", release)
        self.assertIn("release-manifest", release)
        self.assertIn("published-assets.txt", release)
        self.assertIn("diff -u expected-assets.txt published-assets.txt", release)
        self.assertNotIn("gh release create \"$RELEASE_TAG\" dist/*", release)
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
        windows_adapter = (
            FRONTEND / "code" / "windows_launcher.py"
        ).read_text(encoding="utf-8")
        runtime_paths = (FRONTEND / "code" / "runtime_paths.py").read_text(
            encoding="utf-8"
        )
        service = (
            FRONTEND / "packaging" / "windows" / "amy_service.c"
        ).read_text(encoding="utf-8")
        cmake = (
            FRONTEND / "packaging" / "windows" / "CMakeLists.txt"
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
        self.assertIn("qml-slider-drag-visible", launcher)
        self.assertIn("qml-slider-release-visible", launcher)
        self.assertIn("-ExecutionPolicy Bypass", click_launcher)
        self.assertIn('"%~dp0run_windows.ps1" %*', click_launcher)
        self.assertIn("pause", click_launcher)
        self.assertIn("prepare_windowed_console_streams()", main)
        self.assertIn("guarded_package_main(main)", main)
        self.assertIn("if sys.stdout is None:", windows_adapter)
        self.assertIn("if sys.stderr is None:", windows_adapter)
        self.assertIn("fatal-error", windows_adapter)
        self.assertIn("resolve_frontend_asset_root", runtime_paths)
        self.assertIn('getattr(sys, "_MEIPASS", None)', runtime_paths)
        self.assertIn("amy_add_message", service)
        self.assertIn("run_self_test", service)
        self.assertIn("amy_simple_fill_buffer", service)
        self.assertIn("AMY named-pipe connect failed:", service)
        self.assertIn("AMY named-pipe read failed:", service)
        self.assertIn("AMY service smoke passed:", service)
        self.assertIn("GAMMA9001=1", cmake)
        self.assertIn("gamma9001-blob-c", cmake)
        self.assertIn("${GAMMA9001_PCM_C}", cmake)
        self.assertIn("amy_set_gamma9001_pcm(gamma9001_pcm_data)", service)
        self.assertEqual(service.count("configure_pcm_bank();"), 2)
        self.assertIn("runs-on: windows-2025", workflow)
        self.assertIn(
            '& "$root\\LB_Omnichord.cmd" -Windowed -SmokeTest',
            workflow,
        )

    def test_appimage_launcher_preserves_the_process_boundary(self) -> None:
        entry = (FRONTEND / "packaging" / "appimage_entry.py").read_text(
            encoding="utf-8"
        )
        build = (FRONTEND / "packaging" / "build_appimage.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("subprocess.Popen", entry)
        self.assertIn('"--amy-service"', entry)
        self.assertIn('"--amy-socket"', entry)
        self.assertIn("local_amy_service.main()", entry)
        self.assertIn(
            'frontend_arguments = ["--amy-socket", str(socket), *arguments]',
            entry,
        )
        self.assertIn("main.main(frontend_arguments, asset_root=APP_ROOT)", entry)
        for asset in (
            "drum_activity_timing.json",
            "drum_fills_timing.json",
            "drum_fill_continuation_roles.json",
            "drum_activity_instruments_tiny.json",
            "drum_fills_instruments_tiny.json",
            "drum_activity_instruments_gamma9001.json",
            "drum_fills_instruments_gamma9001.json",
            "drum_activity_instruments_general_midi.json",
            "drum_fills_instruments_general_midi.json",
        ):
            self.assertIn(asset, entry)
        self.assertNotIn("core.FRONTEND_DIR =", entry)
        self.assertNotIn("amy.live(", entry)
        self.assertIn("--hidden-import package_smoke", build)
        self.assertIn("--hidden-import PySide6.QtTest", build)

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
