from __future__ import annotations

from pathlib import Path
from typing import Any

from resolved_config import (
    CHORD_VOICE_CAPACITY,
    CONFIG_SCHEMA_REVISION,
    ConfigIssue,
    ConfigProvenance,
    ConfigValidationError,
    DebugConfig,
    DrumRuntimeConfig,
    MidiInputConfig,
    ResolvedAmyConfig,
    RuntimeCapacities,
    PerformanceTimingConfig,
    RhythmRuntimeConfig,
    SynthBusLayout,
    SynthDefaults,
    TransportConfig,
    VoiceCapacities,
    apply_transport_overrides,
    load_resolved_amy_config,
    resolve_amy_config_data,
)


def load_amy_config(path: Path) -> dict[str, Any]:
    """Explicit compatibility API returning an isolated validated JSON view."""

    return load_resolved_amy_config(path).compatibility_dict()


__all__ = (
    "CHORD_VOICE_CAPACITY",
    "CONFIG_SCHEMA_REVISION",
    "ConfigIssue",
    "ConfigProvenance",
    "ConfigValidationError",
    "DebugConfig",
    "DrumRuntimeConfig",
    "MidiInputConfig",
    "ResolvedAmyConfig",
    "RuntimeCapacities",
    "PerformanceTimingConfig",
    "RhythmRuntimeConfig",
    "SynthBusLayout",
    "SynthDefaults",
    "TransportConfig",
    "VoiceCapacities",
    "apply_transport_overrides",
    "load_amy_config",
    "load_resolved_amy_config",
    "resolve_amy_config_data",
)
