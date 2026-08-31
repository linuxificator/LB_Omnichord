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
    QT_MODULE_LOAD_ORDER,
    create_buildozer_sdk_compat,
    patch_buildozer_spec,
    pin_pyside_qt_module_order,
    release_values,
    verify_apk,
    verify_buildozer_qt_module_order,
    verify_qt_modules_present,
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
                "p4a.extra_args = --qt-libs=Gui,QuickControls2,Core "
                "--load-local-libs=plugins_platforms_qtforandroid "
                "--init-classes=\n"
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
                app["android.permissions"],
                "INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,"
                "CHANGE_WIFI_MULTICAST_STATE",
            )
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
            self.assertEqual(
                app["p4a.extra_args"],
                "--qt-libs="
                + ",".join(QT_MODULE_LOAD_ORDER)
                + " --load-local-libs=plugins_platforms_qtforandroid "
                "--init-classes=",
            )
            verify_buildozer_qt_module_order(spec)

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

    def test_pyside_qt_modules_are_pinned_in_dependency_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "pysidedeploy.spec"
            spec.write_text(
                "[qt]\n"
                "modules = Qml,QuickControls2,Core,Test,Network,Gui,Quick,OpenGL\n",
                encoding="utf-8",
            )

            pin_pyside_qt_module_order(spec)

            parser = configparser.ConfigParser(interpolation=None)
            parser.read(spec, encoding="utf-8")
            self.assertEqual(
                tuple(parser.get("qt", "modules").split(",")),
                QT_MODULE_LOAD_ORDER,
            )

    @staticmethod
    def qt_loader_resources(abi: str, modules: tuple[str, ...]) -> bytes:
        return b"\0".join(
            f"{abi};Qt6{module}_{abi}".encode("ascii")
            for module in modules
        )

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
                archive.writestr(
                    "resources.arsc",
                    self.qt_loader_resources("x86_64", QT_MODULE_LOAD_ORDER),
                )

            with self.assertRaisesRegex(ValueError, "libpython3.11.so"):
                verify_apk(apk, "x86_64")

            with zipfile.ZipFile(apk, "a") as archive:
                archive.writestr("lib/x86_64/libpython3.11.so", b"correct")
            verify_apk(apk, "x86_64")

    def test_buildozer_verifier_rejects_unsafe_qt_jni_load_order(self) -> None:
        unsafe = tuple(
            "QuickControls2"
            if module == "Quick"
            else "Quick"
            if module == "QuickControls2"
            else module
            for module in QT_MODULE_LOAD_ORDER
        )
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "buildozer.spec"
            spec.write_text(
                "[app]\n"
                "p4a.extra_args = --qt-libs="
                + ",".join(unsafe)
                + " --load-local-libs=plugins_platforms_qtforandroid\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "dependency-safe"):
                verify_buildozer_qt_module_order(spec)

    def test_apk_verifier_rejects_a_missing_qt_module(self) -> None:
        incomplete = tuple(
            module for module in QT_MODULE_LOAD_ORDER if module != "Quick"
        )

        with self.assertRaisesRegex(ValueError, "omit modules.*Quick"):
            verify_qt_modules_present(
                self.qt_loader_resources("x86_64", incomplete),
                "x86_64",
            )

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
