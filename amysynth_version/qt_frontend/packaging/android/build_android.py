#!/usr/bin/env python3
"""Build a staged PySide6 Android APK containing the separate AMY AAR."""

from __future__ import annotations

import argparse
import calendar
import configparser
import hashlib
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from prune_pyside_wheel import prune_wheel


PYSIDE_VERSION = "6.11.2"
P4A_COMMIT = "3762c88c56e3443efb8eba2a02a2604b680240fd"
APP_ID = "org.linuxificator.lb_omnichord"
QT_MODULE_LOAD_ORDER = (
    "Core",
    "Gui",
    "Network",
    "OpenGL",
    "Qml",
    "Quick",
    "QuickControls2",
    "Test",
)
ARCHITECTURES = {
    "x86_64": ("x86_64", "x86_64"),
    "aarch64": ("arm64-v8a", "arm64"),
}
ASSET_DIRECTORIES = ("config", "gui", "instruments", "music")
SOURCE_EXTENSIONS = "py,qml,js,json,csv,png,jpg,jpeg"
PORTABLE_REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements-portable.txt"


def run(command: list[str], *, cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def reset_staging_directory(path: Path, frontend: Path) -> None:
    resolved = path.resolve()
    frontend = frontend.resolve()
    if resolved == frontend or frontend in resolved.parents:
        raise ValueError("Android staging directory must be outside the frontend tree")
    if resolved == resolved.parent or len(resolved.parts) < 3:
        raise ValueError(f"refusing unsafe Android staging directory {resolved}")
    build_cache = resolved / ".buildozer"
    preserved_cache = resolved.with_name(f"{resolved.name}-preserved-build-cache")
    if preserved_cache.exists():
        shutil.rmtree(preserved_cache)
    if build_cache.exists():
        if build_cache.is_symlink() or not build_cache.is_dir():
            raise ValueError(f"unsafe Android build cache {build_cache}")
        build_cache.rename(preserved_cache)
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    if preserved_cache.exists():
        preserved_cache.rename(build_cache)


def stage_frontend(frontend: Path, staging: Path) -> None:
    reset_staging_directory(staging, frontend)
    for source in sorted((frontend / "code").glob("*.py")):
        shutil.copy2(source, staging / source.name)
    if not (staging / "main.py").is_file():
        raise FileNotFoundError("frontend code/main.py was not staged")
    for name in ASSET_DIRECTORIES:
        shutil.copytree(frontend / name, staging / name)


def create_buildozer_sdk_compat(sdk: Path, destination: Path) -> Path:
    """Expose the modern SDK manager at Buildozer 1.5's legacy path."""
    sdk = sdk.resolve()
    command_line_tools = sdk / "cmdline-tools"
    candidates = [command_line_tools / "latest" / "bin" / "sdkmanager"]
    versioned = sorted(
        command_line_tools.glob("*/bin/sdkmanager"),
        key=lambda path: tuple(
            int(component)
            for component in re.findall(r"\d+", path.parent.parent.name)
        ),
        reverse=True,
    )
    candidates.extend(versioned)
    sdkmanager = next((path for path in candidates if path.is_file()), None)
    if sdkmanager is None:
        raise FileNotFoundError(
            f"modern sdkmanager not found below {command_line_tools}"
        )
    if destination.exists():
        raise FileExistsError(destination)

    destination.mkdir(parents=True)
    for source in sdk.iterdir():
        if source.name == "tools":
            continue
        (destination / source.name).symlink_to(source.resolve())
    legacy_bin = destination / "tools" / "bin"
    legacy_bin.mkdir(parents=True)
    (legacy_bin / "sdkmanager").symlink_to(sdkmanager.resolve())
    return destination.resolve()


def release_values(stamp: str) -> tuple[str, str]:
    match = re.fullmatch(r"R(\d{8})(\d{6})", stamp)
    if match is None:
        raise ValueError("release stamp must have form RYYYYMMDDHHMMSS")
    instant = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    version = f"{instant.year}.{instant.month}.{instant.day}"
    numeric_version = str(calendar.timegm(instant.timetuple()))
    return version, numeric_version


def portable_python_requirements(
    path: Path = PORTABLE_REQUIREMENTS,
) -> tuple[str, ...]:
    requirements = tuple(
        line
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    )
    if not requirements or any(line.startswith("-") for line in requirements):
        raise ValueError("portable Android requirements must be explicit packages")
    return requirements


def patch_buildozer_spec(
    spec_path: Path,
    *,
    aar: Path,
    architecture: str,
    stamp: str,
    sdk_path: Path,
) -> None:
    android_arch, _ = ARCHITECTURES[architecture]
    version, numeric_version = release_values(stamp)
    parser = configparser.ConfigParser(
        comment_prefixes=("#",),
        interpolation=None,
        strict=False,
    )
    parser.read(spec_path, encoding="utf-8")
    if not parser.has_section("app") or not parser.has_section("buildozer"):
        raise ValueError("pyside6-android-deploy generated an invalid buildozer.spec")

    p4a_extra_args = shlex.split(parser.get("app", "p4a.extra_args", fallback=""))
    qt_libs_argument = "--qt-libs=" + ",".join(QT_MODULE_LOAD_ORDER)
    qt_libs_indices = [
        index
        for index, argument in enumerate(p4a_extra_args)
        if argument.startswith("--qt-libs=")
    ]
    if len(qt_libs_indices) != 1:
        raise ValueError(
            "pyside6-android-deploy generated no unique --qt-libs argument"
        )
    p4a_extra_args[qt_libs_indices[0]] = qt_libs_argument

    app_values = {
        "title": "LB Omnichord",
        "package.name": "lb_omnichord",
        "package.domain": "org.linuxificator",
        "source.include_exts": SOURCE_EXTENSIONS,
        "source.exclude_dirs": "deployment,__pycache__",
        "version": version,
        "requirements": ",".join(
            ("python3", "shiboken6", "PySide6", *portable_python_requirements())
        ),
        "orientation": "landscape",
        "fullscreen": "1",
        "android.api": "36",
        "android.minapi": "26",
        "android.ndk": "27c",
        "android.sdk_path": str(sdk_path.resolve()),
        "android.archs": android_arch,
        "android.numeric_version": numeric_version,
        "android.allow_backup": "False",
        "android.permissions": "INTERNET",
        "android.manifest.orientation": "landscape",
        "android.add_aars": str(aar.resolve()),
        "android.add_gradle_repositories": "flatDir { dirs 'libs' }",
        "android.gradle_dependencies": "com.google.oboe:oboe:1.10.0",
        "android.add_packaging_options": "pickFirst 'lib/**/libc++_shared.so'",
        "android.debug_artifact": "apk",
        "android.release_artifact": "apk",
        "p4a.commit": P4A_COMMIT,
        "p4a.extra_args": " ".join(p4a_extra_args),
    }
    for key, value in app_values.items():
        parser.set("app", key, value)
    parser.set("buildozer", "bin_dir", str((spec_path.parent / "bin").resolve()))

    with spec_path.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def pin_pyside_qt_module_order(spec_path: Path) -> None:
    """Replace deployer's set-derived module order with dependency order."""

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(spec_path, encoding="utf-8")
    if not parser.has_section("qt") or not parser.has_option("qt", "modules"):
        raise ValueError("pyside6-android-deploy generated no Qt module list")
    modules = tuple(
        module.strip()
        for module in parser.get("qt", "modules").split(",")
        if module.strip()
    )
    expected = set(QT_MODULE_LOAD_ORDER)
    actual = set(modules)
    if actual != expected:
        raise ValueError(
            "unexpected Qt module set: "
            f"missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    parser.set("qt", "modules", ",".join(QT_MODULE_LOAD_ORDER))
    with spec_path.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def verify_buildozer_qt_module_order(spec_path: Path) -> None:
    """Require python-for-android's final Qt module input to be ordered."""

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(spec_path, encoding="utf-8")
    arguments = shlex.split(parser.get("app", "p4a.extra_args", fallback=""))
    module_arguments = [
        argument.removeprefix("--qt-libs=")
        for argument in arguments
        if argument.startswith("--qt-libs=")
    ]
    if len(module_arguments) != 1:
        raise ValueError("buildozer.spec has no unique --qt-libs argument")
    modules = tuple(module_arguments[0].split(","))
    if modules != QT_MODULE_LOAD_ORDER:
        raise ValueError(
            "python-for-android Qt module load order is not dependency-safe: "
            + ",".join(modules)
        )


def verify_qt_modules_present(resources: bytes, abi: str) -> None:
    """Require every configured Qt module to be present in the APK resources."""

    tokens = [
        f"{abi};Qt6{module}_{abi}".encode("ascii")
        for module in QT_MODULE_LOAD_ORDER
    ]
    missing = [
        QT_MODULE_LOAD_ORDER[index]
        for index, token in enumerate(tokens)
        if token not in resources
    ]
    if missing:
        raise ValueError(f"APK Qt loader resources omit modules {missing}")


def verify_inputs(aar: Path, wheel_pyside: Path, wheel_shiboken: Path, arch: str) -> None:
    wheel_arch = "android_aarch64" if arch == "aarch64" else "android_x86_64"
    for wheel, component in (
        (wheel_pyside, "PySide6"),
        (wheel_shiboken, "shiboken6"),
    ):
        if not wheel.is_file() or wheel_arch not in wheel.name:
            raise ValueError(f"{component} wheel does not match {arch}: {wheel}")
        if PYSIDE_VERSION not in wheel.name:
            raise ValueError(f"{component} wheel is not pinned to {PYSIDE_VERSION}")

    if not aar.is_file():
        raise FileNotFoundError(aar)
    with zipfile.ZipFile(aar) as archive:
        names = set(archive.namelist())
        required = {
            "AndroidManifest.xml",
            "jni/arm64-v8a/libamy_android.so",
            "jni/x86_64/libamy_android.so",
        }
        missing = required.difference(names)
        if missing:
            raise ValueError(f"AMY AAR is missing {sorted(missing)}")


def verify_apk(apk: Path, architecture: str) -> None:
    abi, _ = ARCHITECTURES[architecture]
    with zipfile.ZipFile(apk) as archive:
        names = set(archive.namelist())
        resources = archive.read("resources.arsc")
    required = {
        "AndroidManifest.xml",
        f"lib/{abi}/libamy_android.so",
        f"lib/{abi}/liboboe.so",
        f"lib/{abi}/libpython3.11.so",
        f"lib/{abi}/libshiboken6.abi3.so",
    }
    missing = required.difference(names)
    if missing:
        raise ValueError(f"packaged APK is missing {sorted(missing)}")
    forbidden = [name for name in names if "c_amy" in name or "libamy.so" in name]
    if forbidden:
        raise ValueError(f"frontend APK contains an in-process AMY binding: {forbidden}")
    verify_qt_modules_present(resources, abi)


def build(args: argparse.Namespace) -> Path:
    frontend = args.frontend.resolve()
    staging = args.build_dir.resolve()
    aar = args.aar.resolve()
    wheel_pyside = args.wheel_pyside.resolve()
    wheel_shiboken = args.wheel_shiboken.resolve()
    verify_inputs(aar, wheel_pyside, wheel_shiboken, args.arch)

    derived_inputs = staging.parent / f"{staging.name}-derived-inputs"
    derived_inputs.mkdir(parents=True, exist_ok=True)
    pruned_pyside = derived_inputs / wheel_pyside.name
    prune_report = derived_inputs / "pyside-wheel-prune.json"
    prune_wheel(
        source=wheel_pyside,
        output=pruned_pyside,
        report=prune_report,
    )
    wheel_pyside = pruned_pyside
    stage_frontend(frontend, staging)

    deploy = shutil.which("pyside6-android-deploy")
    if deploy is None:
        raise RuntimeError("pyside6-android-deploy is not installed")
    deploy_command = [
        deploy,
        "--init",
        "--keep-deployment-files",
        "--name",
        "LB_Omnichord",
        "--wheel-pyside",
        str(wheel_pyside),
        "--wheel-shiboken",
        str(wheel_shiboken),
        "--ndk-path",
        str(args.ndk.resolve()),
        "--sdk-path",
        str(args.sdk.resolve()),
        "--extra-modules",
        "QtQuick,QtQuickControls2",
    ]
    run(deploy_command, cwd=staging)
    pyside_spec = staging / "pysidedeploy.spec"
    if not pyside_spec.is_file():
        raise FileNotFoundError(
            "pyside6-android-deploy did not create pysidedeploy.spec"
        )
    pin_pyside_qt_module_order(pyside_spec)
    # Recreate recipes from the ordered list. PySide 6.11.2 otherwise derives
    # this through sets, so QuickControls2 can be loaded before Quick and crash
    # inside Qt's JNI_OnLoad.
    run(
        [*deploy_command, "--config-file", str(pyside_spec)],
        cwd=staging,
    )
    sdk_compat = create_buildozer_sdk_compat(
        args.sdk,
        staging / "deployment" / "android-sdk-compat",
    )
    spec = staging / "buildozer.spec"
    if not spec.is_file():
        raise FileNotFoundError("pyside6-android-deploy did not create buildozer.spec")
    patch_buildozer_spec(
        spec,
        aar=aar,
        architecture=args.arch,
        stamp=args.release_stamp,
        sdk_path=sdk_compat,
    )
    verify_buildozer_qt_module_order(spec)
    run([sys.executable, "-m", "buildozer", "android", args.mode], cwd=staging)

    candidates = sorted((staging / "bin").glob("*.apk"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one generated APK, found {candidates}")
    verify_apk(candidates[0], args.arch)

    _, platform_arch = ARCHITECTURES[args.arch]
    output_dir = frontend / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (
        f"LB_Omnichord.{args.release_stamp}.Android-{platform_arch}.apk"
    )
    shutil.copy2(candidates[0], output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="ascii",
    )
    prune_evidence = output.with_suffix(output.suffix + ".pyside-prune.json")
    shutil.copy2(prune_report, prune_evidence)
    package_audit = output.with_suffix(output.suffix + ".package-audit.json")
    run(
        [
            sys.executable,
            str(frontend / "packaging" / "package_audit.py"),
            "--platform",
            f"Android-{platform_arch}",
            "--package",
            str(output),
            "--output",
            str(package_audit),
        ],
        cwd=frontend,
    )
    print(f"Android package: {output}", flush=True)
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--aar", type=Path, required=True)
    parser.add_argument("--wheel-pyside", type=Path, required=True)
    parser.add_argument("--wheel-shiboken", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--arch", choices=tuple(ARCHITECTURES), required=True)
    parser.add_argument("--release-stamp", required=True)
    parser.add_argument("--mode", choices=("debug", "release"), default="debug")
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_arguments())
