from __future__ import annotations

"""Explicit compatibility surface for AMY command clients.

New production code imports concrete program-aware clients from program_amy and
configuration from config_loader. This module preserves the documented client
names and the two private sequencer helpers used by regression tests without
republishing amy_transport dynamically.
"""

from amy_transport import (
    AMY_PPQ,
    RESET_ALL_NOTES,
    RESET_ALL_OSCS,
    RESET_SEQUENCER,
    RESET_TIMEBASE,
    SYNTH_FLAGS_NO_NOTE_WARNINGS,
    _TaggedSequencerLane,
    _compact_repeating_events,
)
from config_loader import load_amy_config, load_resolved_amy_config
from program_amy import (
    ProgramAmyLocalClient as AmyLocalClient,
    ProgramAmySerialClient as AmySerialClient,
    ProgramAmySocketClient as AmySocketClient,
)

__all__ = (
    "AMY_PPQ",
    "AmyLocalClient",
    "AmySerialClient",
    "AmySocketClient",
    "RESET_ALL_NOTES",
    "RESET_ALL_OSCS",
    "RESET_SEQUENCER",
    "RESET_TIMEBASE",
    "SYNTH_FLAGS_NO_NOTE_WARNINGS",
    "load_amy_config",
    "load_resolved_amy_config",
)
