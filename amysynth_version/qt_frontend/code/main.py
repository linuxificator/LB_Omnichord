from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import app_core
from application_composition import (
    ApplicationDependencies,
    BackendFactory,
    ClientFactory,
    FrontendPaths,
)
from bass_riffs import load_bass_riff_catalog
from catalog_extensions import load_synth_catalog as load_extended_synth_catalog
from config_loader import (
    load_amy_config as load_amy_config,
    load_resolved_amy_config,
)
from midi_integration import InstrumentBackend
from midi_platform_adapters import production_midi_input_port
from osc_input import production_osc_input_port
from program_amy import (
    ProgramAmyLocalClient,
    ProgramAmySerialClient,
    ProgramAmySocketClient,
)
from runtime_diagnostics import display_diagnostic_lines
from runtime_paths import qt_private_files_dir
from runtime_platform_adapters import resolve_package_runtime
from windows_launcher import prepare_windowed_console_streams


prepare_windowed_console_streams()


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
        midi_input_port=production_midi_input_port,
        osc_input_port=production_osc_input_port,
        private_files_dir=qt_private_files_dir,
        resolve_package_runtime=resolve_package_runtime,
        display_diagnostics=display_diagnostic_lines,
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


if __name__ == "__main__":
    raise SystemExit(main())
