from __future__ import annotations

import configparser
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "packaging" / "android"))

from build_android import (  # noqa: E402
    APP_ID,
    P4A_COMMIT,
    PYSIDE_VERSION,
    create_buildozer_sdk_compat,
    patch_buildozer_spec,
    release_values,
    verify_apk,
)


class AndroidPackagingTests(unittest.TestCase):
    def test_release_stamp_maps_to_android_version_without_overflow(self) -> None:
        version, numeric = release_values("R20260830123456")
        self.assertEqual(version, "2026.8.30")
        self.assertEqual(numeric, "1788093296")
        self.assertLess(int(numeric), 2_100_000_000)

    def test_generated_spec_gets_the_service_and_reproducible_qt_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = root / "buildozer.spec"
            aar = root / "amy-service-debug.aar"
            aar.touch()
            spec.write_text(
                "[app]\n"
                "title = generated\n"
                "requirements = python3,shiboken6,PySide6\n"
                "p4a.extra_args = --qt-libs=Core\n"
                "\n[buildozer]\n"
                "bin_dir = bin\n",
                encoding="utf-8",
            )

            patch_buildozer_spec(
                spec,
                aar=aar,
                architecture="aarch64",
                stamp="R20260830123456",
                sdk_path=root / "sdk-compat",
            )

            parser = configparser.ConfigParser(interpolation=None)
            parser.read(spec, encoding="utf-8")
            app = parser["app"]
            buildozer = parser["buildozer"]
            self.assertEqual(
                f"{app['package.domain']}.{app['package.name']}", APP_ID
            )
            self.assertEqual(app["android.archs"], "arm64-v8a")
            self.assertEqual(app["android.ndk"], "27c")
            self.assertEqual(
                app["android.sdk_path"], str((root / "sdk-compat").resolve())
            )
            self.assertEqual(app["p4a.commit"], P4A_COMMIT)
            self.assertIn("pyserial", app["requirements"])
            self.assertEqual(app["android.add_aars"], str(aar.resolve()))
            self.assertEqual(
                app["android.add_gradle_repositories"], "flatDir { dirs 'libs' }"
            )
            self.assertIn("com.google.oboe:oboe:1.10.0", app["android.gradle_dependencies"])
            self.assertEqual(
                app["android.add_packaging_options"],
                "pickFirst 'lib/**/libc++_shared.so'",
            )
            self.assertEqual(buildozer["bin_dir"], str((root / "bin").resolve()))
            self.assertIn("json", app["source.include_exts"])

    def test_buildozer_sdk_compat_uses_modern_sdkmanager(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk"
            modern = sdk / "cmdline-tools" / "16.0" / "bin" / "sdkmanager"
            stale = sdk / "tools" / "bin" / "sdkmanager"
            modern.parent.mkdir(parents=True)
            stale.parent.mkdir(parents=True)
            modern.touch()
            stale.touch()
            (sdk / "platform-tools").mkdir()

            compat = create_buildozer_sdk_compat(sdk, root / "compat")

            resolved_manager = (compat / "tools" / "bin" / "sdkmanager").resolve()
            self.assertEqual(resolved_manager, modern)
            self.assertEqual(
                (compat / "platform-tools").resolve(), sdk / "platform-tools"
            )
            self.assertNotEqual(resolved_manager, stale)

    def test_apk_verifier_rejects_a_python_abi_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "frontend.apk"
            required = {
                "AndroidManifest.xml",
                "lib/x86_64/libamy_android.so",
                "lib/x86_64/liboboe.so",
                "lib/x86_64/libshiboken6.abi3.so",
            }
            with zipfile.ZipFile(apk, "w") as archive:
                for name in required:
                    archive.writestr(name, b"test")
                archive.writestr("lib/x86_64/libpython3.14.so", b"wrong")

            with self.assertRaisesRegex(ValueError, "libpython3.11.so"):
                verify_apk(apk, "x86_64")

            with zipfile.ZipFile(apk, "a") as archive:
                archive.writestr("lib/x86_64/libpython3.11.so", b"correct")
            verify_apk(apk, "x86_64")

    def test_documented_toolchain_is_pinned(self) -> None:
        readme = (
            FRONTEND / "packaging" / "android" / "README.md"
        ).read_text(encoding="utf-8")
        self.assertIn(PYSIDE_VERSION, readme)
        self.assertIn(P4A_COMMIT, readme)
        self.assertIn("Cython 0.29.36", readme)
        self.assertIn("debug-signed", readme)
        self.assertIn("V10", readme)
        self.assertIn("LB's maximum is `V1`", readme)
        self.assertIn("at least -26 dBFS peak", readme)
        self.assertIn("QLocalSocket", readme)
        self.assertIn("does not use PulseAudio", readme)
        self.assertIn("AmyAndroid: Oboe output", readme)

    def test_workflow_installs_pyside_android_deploy_requirements(self) -> None:
        repository = FRONTEND.parents[1]
        workflow = (repository / ".github" / "workflows" / "desktop-release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("requirements-android.txt", workflow)
        self.assertIn("Cython==0.29.36", workflow)


if __name__ == "__main__":
    unittest.main()
