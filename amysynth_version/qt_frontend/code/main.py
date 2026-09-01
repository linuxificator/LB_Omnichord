from __future__ import annotations

import os
import sys
from argparse import Namespace
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

# PyInstaller's Windows `--windowed` bootloader deliberately supplies no
# console streams. Install harmless sinks before importing modules which write
# diagnostics during application startup.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import app_core
from application_composition import (
    ApplicationDependencies,
    BackendFactory,
    ClientFactory,
    FrontendPaths,
)
from bass_riffs import load_bass_riff_catalog
from catalog_extensions import load_synth_catalog as load_extended_synth_catalog
from config_loader import load_amy_config, load_resolved_amy_config
from midi_integration import InstrumentBackend
from program_amy import (
    ProgramAmyLocalClient,
    ProgramAmySerialClient,
    ProgramAmySocketClient,
)


# Explicit compatibility exports for the supported headless integration
# entrypoint. There is no wildcard import and no assignment into app_core.
FRONTEND_DIR = app_core.FRONTEND_DIR
CONFIG_DIR = FRONTEND_DIR / "config"
GUI_DIR = FRONTEND_DIR / "gui"
INSTRUMENT_DIR = FRONTEND_DIR / "instruments"
MUSIC_DIR = FRONTEND_DIR / "music"
load_defaults = app_core.load_defaults
load_chords = app_core.load_chords
load_rhythm_catalog = app_core.load_rhythm_catalog
load_intonation_table = app_core.load_intonation_table


def load_synth_catalog(path: Path) -> tuple[list[Any], int, int, int]:
    """Load the public catalogue including non-ROM synth programs."""

    return load_extended_synth_catalog(app_core.load_synth_catalog, path)


def parse_arguments(arguments: Sequence[str] | None = None) -> Namespace:
    return app_core.parse_arguments(
        arguments,
        default_config_path=CONFIG_DIR / "amy_config.json",
    )


def production_dependencies(
    *,
    asset_root: Path | None = None,
) -> ApplicationDependencies:
    """Construct the one production dependency graph without mutating modules."""

    paths = FrontendPaths.from_root(asset_root or FRONTEND_DIR)
    return ApplicationDependencies(
        paths=paths,
        load_resolved_config=load_resolved_amy_config,
        load_defaults=app_core.load_defaults,
        load_chords=app_core.load_chords,
        load_synth_catalog=load_synth_catalog,
        load_rhythm_catalog=app_core.load_rhythm_catalog,
        load_bass_riffs=load_bass_riff_catalog,
        load_title_config=app_core.load_title_config,
        load_intonation_table=app_core.load_intonation_table,
        serial_client=cast(ClientFactory, ProgramAmySerialClient),
        socket_client=cast(ClientFactory, ProgramAmySocketClient),
        local_client=cast(ClientFactory, ProgramAmyLocalClient),
        backend=cast(BackendFactory, InstrumentBackend),
    )


def main(
    arguments: Sequence[str] | None = None,
    *,
    asset_root: Path | None = None,
) -> int:
    dependencies = production_dependencies(asset_root=asset_root)
    args = app_core.parse_arguments(
        arguments,
        default_config_path=dependencies.paths.config / "amy_config.json",
    )
    return app_core.run_application(args, dependencies)


def _guarded_main() -> int:
    if not os.environ.get("OMNICHORD_PACKAGE_SMOKE_STATUS"):
        return main()
    try:
        return main()
    except Exception as exc:
        # A --windowed PyInstaller executable otherwise displays an error
        # dialog that cannot be dismissed on a headless CI runner.
        status = Path(os.environ["OMNICHORD_PACKAGE_SMOKE_STATUS"])
        with status.open("a", encoding="utf-8") as handle:
            handle.write(f"fatal-error {type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(_guarded_main())
