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
    MidiInputConfig,
    ResolvedAmyConfig,
    RuntimeCapacities,
    SynthBusLayout,
    TransportConfig,
    VoiceCapacities,
    load_resolved_amy_config,
    resolve_amy_config_data,
)


def load_amy_config(path: Path) -> dict[str, Any]:
    """Return the isolated legacy view of validated, typed configuration."""

    return load_resolved_amy_config(path).compatibility_dict()


__all__ = (
    "CHORD_VOICE_CAPACITY",
    "CONFIG_SCHEMA_REVISION",
    "ConfigIssue",
    "ConfigProvenance",
    "ConfigValidationError",
    "DebugConfig",
    "MidiInputConfig",
    "ResolvedAmyConfig",
    "RuntimeCapacities",
    "SynthBusLayout",
    "TransportConfig",
    "VoiceCapacities",
    "load_amy_config",
    "load_resolved_amy_config",
    "resolve_amy_config_data",
)
