from __future__ import annotations

from argparse import Namespace
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from config_loader import (
    ResolvedAmyConfig,
    apply_transport_overrides,
)
from midi_input import MidiInputPortFactory


Checkpoint = Callable[[str], None]
TransportNotice = Callable[["ClientSelection", ResolvedAmyConfig], None]
SynthFallbackNotice = Callable[[str, str, str], None]


class CommandClient(Protocol):
    def send_message(self, address: str, value: Any) -> None: ...

    def close(self) -> None: ...


class ClientFactory(Protocol):
    def __call__(self, **kwargs: Any) -> CommandClient: ...


class BackendFactory(Protocol):
    def __call__(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class FrontendPaths:
    root: Path
    config: Path
    gui: Path
    instruments: Path
    music: Path

    @classmethod
    def from_root(cls, root: Path) -> FrontendPaths:
        resolved = Path(root).resolve()
        return cls(
            root=resolved,
            config=resolved / "config",
            gui=resolved / "gui",
            instruments=resolved / "instruments",
            music=resolved / "music",
        )


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    paths: FrontendPaths
    load_resolved_config: Callable[[Path], ResolvedAmyConfig]
    load_defaults: Callable[[Path], dict[str, Any]]
    load_chords: Callable[[Path], tuple[Any, ...]]
    load_synth_catalog: Callable[[Path], tuple[Sequence[Any], int, int, int]]
    load_rhythm_catalog: Callable[[Path], tuple[Any, ...]]
    load_bass_riffs: Callable[..., Any]
    load_title_config: Callable[[Path], dict[str, Any]]
    load_intonation_table: Callable[[Path], Any]
    serial_client: ClientFactory
    socket_client: ClientFactory
    local_client: ClientFactory
    midi_input_port: MidiInputPortFactory
    backend: BackendFactory


@dataclass(frozen=True, slots=True)
class ApplicationResources:
    defaults: dict[str, Any]
    chords: tuple[Any, ...]
    synths: tuple[Any, ...]
    rhythms: tuple[Any, ...]
    bass_riffs: Any
    title: dict[str, Any]
    intonation_eq: Any
    intonation_harm: Any
    intonation_jv: Any
    default_chord_synth_index: int
    default_strum_synth_index: int
    default_bass_synth_index: int


@dataclass(frozen=True, slots=True)
class ClientSelection:
    kind: Literal["serial", "socket", "local"]
    endpoint: str | None


@dataclass(frozen=True, slots=True)
class ApplicationGraph:
    resolved_config: ResolvedAmyConfig
    client_selection: ClientSelection
    client: CommandClient
    backend: Any
    resources: ApplicationResources


def _checkpoint(callback: Checkpoint | None, label: str) -> None:
    if callback is not None:
        callback(label)


def select_config_path(
    requested: Path,
    *,
    shipped_config: Path,
    user_config: Path,
) -> Path:
    resolved = requested.expanduser().resolve()
    if resolved == shipped_config.resolve():
        return user_config
    return resolved


def load_application_resources(
    dependencies: ApplicationDependencies,
    *,
    user_config_dir: Path,
    checkpoint: Checkpoint | None = None,
    synth_fallback_notice: SynthFallbackNotice | None = None,
) -> ApplicationResources:
    paths = dependencies.paths
    defaults = dependencies.load_defaults(user_config_dir / "defaults.json")
    _checkpoint(checkpoint, "defaults-loaded")
    chords = dependencies.load_chords(paths.music / "chords.csv")
    _checkpoint(checkpoint, "chords-loaded")
    synth_list, chord_fallback, strum_fallback, bass_fallback = (
        dependencies.load_synth_catalog(paths.instruments / "synths.json")
    )
    synths = tuple(synth_list)
    _checkpoint(checkpoint, "synth-catalog-loaded")
    rhythms = dependencies.load_rhythm_catalog(paths.music / "rhythms.json")
    _checkpoint(checkpoint, "rhythm-catalog-loaded")
    bass_riffs = dependencies.load_bass_riffs(
        paths.music / "omnichord_bass_riffs.json",
        rhythm_ids=(rhythm.key for rhythm in rhythms),
        chord_suffixes=(chord.suffix for chord in chords),
    )
    _checkpoint(checkpoint, "bass-riff-catalog-loaded")
    title = dependencies.load_title_config(user_config_dir / "title.json")
    _checkpoint(checkpoint, "title-config-loaded")
    intonation_eq = dependencies.load_intonation_table(
        paths.music / "intonation_eq.json"
    )
    _checkpoint(checkpoint, "equal-intonation-loaded")
    intonation_harm = dependencies.load_intonation_table(
        paths.music / "intonation_harm.json"
    )
    _checkpoint(checkpoint, "harmonic-intonation-loaded")
    intonation_jv = dependencies.load_intonation_table(
        paths.music / "intonation_jv.json"
    )
    _checkpoint(checkpoint, "just-intonation-loaded")

    by_key = {str(synth.key): index for index, synth in enumerate(synths)}

    def selected(role: str, fallback: int) -> int:
        key = str(cast(dict[str, Any], defaults.get("synths", {})).get(role, ""))
        index = by_key.get(key)
        if index is not None:
            return index
        if synth_fallback_notice is not None:
            synth_fallback_notice(role, key, str(synths[fallback].key))
        return fallback

    resources = ApplicationResources(
        defaults=defaults,
        chords=chords,
        synths=synths,
        rhythms=rhythms,
        bass_riffs=bass_riffs,
        title=title,
        intonation_eq=intonation_eq,
        intonation_harm=intonation_harm,
        intonation_jv=intonation_jv,
        default_chord_synth_index=selected("chord", chord_fallback),
        default_strum_synth_index=selected("strum", strum_fallback),
        default_bass_synth_index=selected("bass", bass_fallback),
    )
    _checkpoint(checkpoint, "startup-synths-selected")
    return resources


def address_map(args: Namespace) -> dict[str, str]:
    return {
        "chord_state": str(args.chord_state_address),
        "manual_chord": str(args.chord_manual_address),
        "chord_amp": str(args.chord_amp_address),
        "strum_amp": str(args.strum_amp_address),
        "bass_amp": str(args.bass_amp_address),
        "percussion_amp": str(args.percussion_amp_address),
        "reverb": str(args.reverb_address),
        "master_volume": str(args.master_volume_address),
        "chord_synth": str(args.chord_synth_address),
        "chord_params": str(args.chord_params_address),
        "strum_synth": str(args.strum_synth_address),
        "strum_params": str(args.strum_params_address),
        "bass_synth": str(args.bass_synth_address),
        "bass_params": str(args.bass_params_address),
        "bass_running": str(args.bass_running_address),
        "strum_note": str(args.strum_note_address),
        "rhythm_config": str(args.rhythm_config_address),
        "rhythm_running": str(args.rhythm_running_address),
        "rhythm_chord_enabled": str(args.rhythm_chord_enabled_address),
        "panic": str(args.panic_address),
    }


def select_client(args: Namespace) -> ClientSelection:
    if args.amy_socket and args.amy_local_name:
        raise ValueError("select either --amy-socket or --amy-local-name")
    if args.amy_local_name:
        return ClientSelection("local", str(args.amy_local_name))
    if args.amy_socket:
        return ClientSelection(
            "socket",
            str(Path(args.amy_socket).expanduser()),
        )
    return ClientSelection("serial", None)


def _create_client(
    selection: ClientSelection,
    dependencies: ApplicationDependencies,
    *,
    resolved: ResolvedAmyConfig,
    addresses: dict[str, str],
) -> CommandClient:
    if selection.kind == "local":
        return dependencies.local_client(
            config=None,
            addresses=addresses,
            server_name=selection.endpoint,
            resolved_config=resolved,
        )
    if selection.kind == "socket":
        return dependencies.socket_client(
            config=None,
            addresses=addresses,
            socket_path=selection.endpoint,
            resolved_config=resolved,
        )
    return dependencies.serial_client(
        config=None,
        addresses=addresses,
        resolved_config=resolved,
    )


def compose_application_graph(
    args: Namespace,
    dependencies: ApplicationDependencies,
    resources: ApplicationResources,
    *,
    user_config_dir: Path,
    checkpoint: Checkpoint | None = None,
    transport_notice: TransportNotice | None = None,
) -> ApplicationGraph:
    requested = Path(args.amy_config)
    _checkpoint(checkpoint, "amy-config-path-resolved")
    config_path = select_config_path(
        requested,
        shipped_config=dependencies.paths.config / "amy_config.json",
        user_config=user_config_dir / "amy_config.json",
    )
    _checkpoint(checkpoint, "amy-config-path-selected")
    resolved = dependencies.load_resolved_config(config_path)
    resolved = apply_transport_overrides(
        resolved,
        serial_port=args.serial_port,
        serial_baud=args.serial_baud,
    )
    _checkpoint(checkpoint, "amy-config-loaded")
    selection = select_client(args)
    if transport_notice is not None:
        transport_notice(selection, resolved)
    if selection.kind == "local":
        _checkpoint(checkpoint, "amy-local-connect-started")
    elif selection.kind == "socket":
        _checkpoint(checkpoint, "amy-socket-connect-started")
    client = _create_client(
        selection,
        dependencies,
        resolved=resolved,
        addresses=address_map(args),
    )
    if selection.kind == "local":
        _checkpoint(checkpoint, "amy-local-connected")
    elif selection.kind == "socket":
        _checkpoint(checkpoint, "amy-socket-connected")

    backend = dependencies.backend(
        chords=resources.chords,
        synths=resources.synths,
        rhythms=resources.rhythms,
        bass_riffs=resources.bass_riffs,
        intonation_eq=resources.intonation_eq,
        intonation_harm=resources.intonation_harm,
        intonation_jv=resources.intonation_jv,
        default_chord_synth_index=resources.default_chord_synth_index,
        default_strum_synth_index=resources.default_strum_synth_index,
        default_bass_synth_index=resources.default_bass_synth_index,
        defaults=resources.defaults,
        client=client,
        chord_state_address=args.chord_state_address,
        chord_manual_address=args.chord_manual_address,
        chord_amp_address=args.chord_amp_address,
        strum_amp_address=args.strum_amp_address,
        bass_amp_address=args.bass_amp_address,
        percussion_amp_address=args.percussion_amp_address,
        reverb_address=args.reverb_address,
        master_volume_address=args.master_volume_address,
        chord_synth_address=args.chord_synth_address,
        chord_params_address=args.chord_params_address,
        strum_synth_address=args.strum_synth_address,
        strum_params_address=args.strum_params_address,
        bass_synth_address=args.bass_synth_address,
        bass_params_address=args.bass_params_address,
        bass_running_address=args.bass_running_address,
        strum_note_address=args.strum_note_address,
        rhythm_config_address=args.rhythm_config_address,
        rhythm_running_address=args.rhythm_running_address,
        rhythm_chord_enabled_address=args.rhythm_chord_enabled_address,
        panic_address=args.panic_address,
        debug_enabled=bool(args.debug or args.debug_file is not None),
        debug_file=args.debug_file,
        midi_input_port_factory=dependencies.midi_input_port,
    )
    return ApplicationGraph(
        resolved_config=resolved,
        client_selection=selection,
        client=client,
        backend=backend,
        resources=resources,
    )
