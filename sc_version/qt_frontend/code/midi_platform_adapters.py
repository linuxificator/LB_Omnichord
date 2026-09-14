from __future__ import annotations

from midi_input import (
    MidiInputEventSink,
    MidiInputLifecycle,
    MidiInputPort,
    MidiInputTechnology,
    MidiInputTechnologyStatus,
)
from midi_platform_profile import current_midi_tech_profile
from resolved_config import MidiInputConfig


_UNSUPPORTED_TECHNOLOGIES: dict[str, tuple[str, str, str]] = {
    "darwin": (
        "coremidi",
        "CoreMIDI",
        "native CoreMIDI bridge is not bundled",
    ),
    "win32": (
        "winmm",
        "WinMM MIDI",
        "native WinMM MIDI bridge is not bundled",
    ),
    "android": (
        "android_midi",
        "Android MIDI",
        "native Android MIDI bridge is not bundled",
    ),
}


def _normalized_profile(profile: str) -> str:
    value = str(profile).strip().casefold()
    if value.startswith("win"):
        return "win32"
    if value.startswith("android"):
        return "android"
    if value.startswith("darwin"):
        return "darwin"
    if value.startswith("linux"):
        return "linux"
    return value


class UnavailableMidiInputPort:
    """Explicit capability result for an unbundled or unknown native adapter."""

    def __init__(self, profile: str, config: MidiInputConfig) -> None:
        self._profile = _normalized_profile(profile)
        self._config = config
        definition = _UNSUPPORTED_TECHNOLOGIES.get(self._profile)
        self._definition = (
            MidiInputTechnology(definition[0], definition[1])
            if definition is not None
            else None
        )
        self._reason = definition[2] if definition is not None else "unsupported platform"
        self._lifecycle: MidiInputLifecycle = "constructed"

    @property
    def lifecycle(self) -> MidiInputLifecycle:
        return self._lifecycle

    @property
    def technologies(self) -> tuple[MidiInputTechnology, ...]:
        return (self._definition,) if self._definition is not None else ()

    def start(self) -> None:
        if self._lifecycle == "constructed":
            self._lifecycle = "ready"

    def status_snapshot(
        self,
        activity_until: dict[str, float] | None = None,
        now: float | None = None,
    ) -> tuple[MidiInputTechnologyStatus, ...]:
        del activity_until, now
        if self._definition is None:
            return ()
        reason = (
            "MIDI input disabled in configuration"
            if not self._config.enabled
            else self._reason
        )
        return (
            MidiInputTechnologyStatus(
                self._definition.key,
                self._definition.label,
                "unavailable",
                reason,
            ),
        )

    def close(self) -> None:
        self._lifecycle = "closed"


def midi_input_technologies(
    config: MidiInputConfig,
    profile: str,
) -> tuple[MidiInputTechnology, ...]:
    """Describe a package profile without starting or probing native readers."""

    normalized = _normalized_profile(profile)
    if normalized == "linux":
        from midi_linux import linux_technologies

        return tuple(
            MidiInputTechnology(item.key, item.label)
            for item in linux_technologies(config)
        )
    definition = _UNSUPPORTED_TECHNOLOGIES.get(normalized)
    if definition is None:
        return ()
    return (MidiInputTechnology(definition[0], definition[1]),)


def create_midi_input_port(
    event_sink: MidiInputEventSink,
    config: MidiInputConfig,
    *,
    profile: str | None = None,
) -> MidiInputPort:
    """Select one native adapter once, at the application composition edge."""

    selected = _normalized_profile(
        profile or current_midi_tech_profile(config.configured_profile)
    )
    if selected == "linux":
        from midi_linux import LinuxMidiInputPort

        return LinuxMidiInputPort(event_sink, config)
    return UnavailableMidiInputPort(selected, config)


def production_midi_input_port(
    event_sink: MidiInputEventSink,
    config: object,
) -> MidiInputPort:
    """Typed production factory exposed to the application composition root."""

    if not isinstance(config, MidiInputConfig):
        raise TypeError("MIDI input port requires resolved MidiInputConfig")
    return create_midi_input_port(event_sink, config)
