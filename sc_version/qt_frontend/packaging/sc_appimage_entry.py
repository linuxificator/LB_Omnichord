#!/usr/bin/env python3
"""Frozen Linux entry point supervising bundled SuperCollider processes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ASSET_DIRECTORIES = ("config", "gui", "instruments", "music", "supercollider")


def packaged_asset_root() -> Path:
    packaged = getattr(sys, "_MEIPASS", None)
    candidates: list[Path] = []
    if packaged is not None:
        root = Path(str(packaged))
        candidates.extend((root, root / "_internal"))
    executable = Path(sys.executable).resolve().parent
    candidates.extend((executable / "_internal", executable))
    for candidate in candidates:
        if all((candidate / name).is_dir() for name in ASSET_DIRECTORIES):
            return candidate
    raise RuntimeError("packaged SuperCollider frontend assets are unavailable")


def packaged_runtime_root() -> Path:
    configured = os.environ.get("OMNICHORD_SC_RUNTIME_ROOT")
    if configured:
        return Path(configured).expanduser()
    executable = Path(sys.executable).resolve().parent
    candidates = (
        # PyInstaller's macOS executable lives in App.app/Contents/MacOS;
        # bundled resources are its sibling Contents/Resources directory.
        executable.parent / "Resources" / "sc-runtime" / "SuperCollider.app",
        executable / "sc-runtime" / "SuperCollider.app",
        executable.parent / "sc-runtime" / "SuperCollider.app",
        executable / "sc-runtime",
        executable.parent / "sc-runtime",
    )
    from supercollider_platform_adapter import (
        SuperColliderProcessError,
        locate_supercollider_runtime,
    )

    for candidate in candidates:
        try:
            locate_supercollider_runtime(candidate)
        except SuperColliderProcessError:
            continue
        else:
            return candidate
    raise RuntimeError("packaged SuperCollider runtime is unavailable")


def verify_config_migrations(root: Path) -> None:
    """Exercise historic user configs through the frozen package boundary."""

    from sample_repository import LEGACY_SAMPLE_ROOT, prepare_user_runtime_config

    shipped_path = root / "config" / "supercollider.json"
    shipped = json.loads(shipped_path.read_text(encoding="utf-8"))
    expected_buffers = shipped["server"]["max_buffers"]
    for revision in (1, 2):
        legacy = json.loads(json.dumps(shipped))
        legacy["config_revision"] = revision
        legacy["server"].pop("max_buffers")
        if revision == 1:
            legacy["samples"].pop("repository")
            legacy["samples"]["vsco_root"] = LEGACY_SAMPLE_ROOT
        with tempfile.TemporaryDirectory() as directory:
            user_root = Path(directory) / "user"
            user_config = user_root / "config" / "supercollider.json"
            user_config.parent.mkdir(parents=True)
            user_config.write_text(json.dumps(legacy), encoding="utf-8")
            migrated_path, migrated = prepare_user_runtime_config(
                shipped_path,
                user_root=user_root,
                install_samples=False,
            )
            persisted = json.loads(migrated_path.read_text(encoding="utf-8"))
            if (
                persisted["config_revision"] != shipped["config_revision"]
                or persisted["server"]["max_buffers"] != expected_buffers
                or migrated.server.max_buffers != expected_buffers
            ):
                raise RuntimeError(
                    f"packaged config migration failed for revision {revision}"
                )


def verify_package(root: Path, runtime: Path) -> int:
    """Validate frozen assets and executables without opening an audio device."""

    from supercollider_platform_adapter import locate_supercollider_runtime

    executables = locate_supercollider_runtime(runtime)
    environment = os.environ.copy()
    runtime_library = runtime / "lib"
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        part
        for part in (
            str(runtime_library),
            environment.get("LD_LIBRARY_PATH", ""),
        )
        if part
    )
    for executable in (executables.sclang, executables.scsynth):
        result = subprocess.run(
            [str(executable), "-v"],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or "3.14.1" not in result.stdout + result.stderr:
            raise RuntimeError(
                f"packaged runtime check failed for {executable}: "
                f"{result.stdout}{result.stderr}"
            )
    verify_config_migrations(root)
    print(
        "LB_OMNICHORD_SC_PACKAGE_OK "
        f"root={root} runtime={runtime} config_migrations=1,2"
    )
    return 0


def main_entry() -> int:
    root = packaged_asset_root()
    runtime = packaged_runtime_root()
    if sys.argv[1:] == ["--verify-package"]:
        return verify_package(root, runtime)
    import main
    from sample_repository import prepare_user_runtime_config
    from supercollider_platform_adapter import SuperColliderSupervisor

    config_path, config = prepare_user_runtime_config(
        root / "config" / "supercollider.json"
    )
    os.environ["OMNICHORD_SC_CONFIG"] = str(config_path)
    with SuperColliderSupervisor(
        engine_root=root / "supercollider",
        config=config,
        runtime_root=runtime,
    ):
        return int(main.main(sys.argv[1:], asset_root=root))


if __name__ == "__main__":
    raise SystemExit(main_entry())
