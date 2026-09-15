from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from functools import partial
import os
from pathlib import Path
from typing import Any, cast

import app_core
from application_composition import (
    ApplicationDependencies,
    BackendFactory,
    ClientFactory,
    FrontendPaths,
)
from bass_riffs import load_bass_riff_catalog as _load_bass_riff_catalog
from sc_bass_articulation import load_sc_bass_articulation
from sc_music_catalog import load_sc_music_catalog
from catalog_extensions import load_synth_catalog as load_extended_synth_catalog
from catalog_extensions import resolve_supercollider_asset_root
from frontend_config import load_frontend_config
from midi_integration import InstrumentBackend
from midi_platform_adapters import production_midi_input_port
from osc_input import production_osc_input_port
from osc_discovery_platform_adapters import production_osc_service_advertiser
from runtime_diagnostics import display_diagnostic_lines
from runtime_paths import qt_private_files_dir
from runtime_platform_adapters import resolve_package_runtime
from supercollider_client import SuperColliderClient
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


def load_bass_riff_catalog(
    path: Path,
    *,
    rhythm_ids: Sequence[str],
    chord_suffixes: Sequence[str],
) -> Any:
    """Use the SC articulation catalogue while retaining the shared loader API."""

    return _load_bass_riff_catalog(
        path,
        rhythm_ids=rhythm_ids,
        chord_suffixes=chord_suffixes,
    )


def load_synth_catalog(
    path: Path,
    *,
    supercollider_root: Path | None = None,
) -> tuple[list[Any], int, int, int]:
    """Load only canonical SuperCollider and sample programs for this edition."""

    return load_extended_synth_catalog(
        path,
        supercollider_root=supercollider_root,
    )


def parse_arguments(arguments: Sequence[str] | None = None) -> Namespace:
    return app_core.parse_arguments(
        arguments,
        default_config_path=CONFIG_DIR / "frontend.json",
    )


def production_dependencies(
    *,
    asset_root: Path | None = None,
) -> ApplicationDependencies:
    """Construct the one production dependency graph without mutating modules."""

    paths = FrontendPaths.from_root(asset_root or FRONTEND_DIR)
    frontend_loader = partial(
        load_frontend_config,
        schema_path=paths.config / "schema" / "frontend_v1.schema.json",
    )
    supercollider_root = resolve_supercollider_asset_root(paths.root)
    runtime_config_path = Path(
        os.environ.get(
            "OMNICHORD_SC_CONFIG",
            str(paths.config / "supercollider.json"),
        )
    ).expanduser()
    sc_client = partial(
        SuperColliderClient,
        runtime_config_path=runtime_config_path,
        asset_root=paths.root,
    )
    sc_music_root = paths.music / "sc_expansion"
    backend = partial(
        InstrumentBackend,
        bass_articulation=load_sc_bass_articulation(
            sc_music_root / "sc_bass_contexts_v1.json"
        ),
        sc_drum_catalog=load_sc_music_catalog(
            sc_music_root / "sc_kit_grooves_v1.json"
        ),
    )
    return ApplicationDependencies(
        paths=paths,
        load_frontend_config=frontend_loader,
        load_defaults=app_core.load_defaults,
        load_chords=app_core.load_chords,
        load_synth_catalog=partial(
            load_synth_catalog,
            supercollider_root=supercollider_root,
        ),
        load_rhythm_catalog=app_core.load_rhythm_catalog,
        load_bass_riffs=load_bass_riff_catalog,
        load_title_config=app_core.load_title_config,
        load_intonation_table=app_core.load_intonation_table,
        client_factory=cast(ClientFactory, sc_client),
        midi_input_port=production_midi_input_port,
        osc_input_port=partial(
            production_osc_input_port,
            advertiser_factory=production_osc_service_advertiser,
        ),
        private_files_dir=qt_private_files_dir,
        resolve_package_runtime=resolve_package_runtime,
        display_diagnostics=display_diagnostic_lines,
        backend=cast(BackendFactory, backend),
        engine_label="SuperCollider",
    )


def main(
    arguments: Sequence[str] | None = None,
    *,
    asset_root: Path | None = None,
) -> int:
    dependencies = production_dependencies(asset_root=asset_root)
    args = app_core.parse_arguments(
        arguments,
        default_config_path=dependencies.paths.config / "frontend.json",
    )
    return app_core.run_application(args, dependencies)


if __name__ == "__main__":
    raise SystemExit(main())
