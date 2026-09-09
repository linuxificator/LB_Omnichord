"""General MIDI percussion identities resolved to LB's lightweight PCM path.

The Gamma9001 mapping mirrors AMY patch 384 without allocating that patch's
38-child synth.  The few sounds that patch 384 does not define are explicit,
documented Gamma9001 substitutions instead of silent missing notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from drum_gamma9001 import GAMMA9001_DIRECT_PCM


GM_PERCUSSION_MIN = 35
GM_PERCUSSION_MAX = 81
MIDI_DRUM_REFERENCE_VELOCITY = 60
MIDI_DRUM_REFERENCE_ROW_VOLUME = 0.28
OMNI_REFERENCE_PERCUSSION_VOLUME = 0.5


class _Sample(Protocol):
    preset: int
    note: int


@dataclass(frozen=True)
class GmPercussionSound:
    name: str
    preset: int
    note: int
    substitution: str | None = None


_NAMES = (
    "Acoustic Bass Drum", "Bass Drum 1", "Side Stick", "Acoustic Snare",
    "Hand Clap", "Electric Snare", "Low Floor Tom", "Closed Hi-Hat",
    "High Floor Tom", "Pedal Hi-Hat", "Low Tom", "Open Hi-Hat",
    "Low-Mid Tom", "Hi-Mid Tom", "Crash Cymbal 1", "High Tom",
    "Ride Cymbal 1", "Chinese Cymbal", "Ride Bell", "Tambourine",
    "Splash Cymbal", "Cowbell", "Crash Cymbal 2", "Vibraslap",
    "Ride Cymbal 2", "Hi Bongo", "Low Bongo", "Mute Hi Conga",
    "Open Hi Conga", "Low Conga", "High Timbale", "Low Timbale",
    "High Agogo", "Low Agogo", "Cabasa", "Maracas", "Short Whistle",
    "Long Whistle", "Short Guiro", "Long Guiro", "Claves",
    "Hi Wood Block", "Low Wood Block", "Mute Cuica", "Open Cuica",
    "Mute Triangle", "Open Triangle",
)
GM_PERCUSSION_NAMES = {
    note: name for note, name in enumerate(_NAMES, GM_PERCUSSION_MIN)
}


# Gamma9001 has no dedicated guiro or cuica samples.  Keep these deliberate
# approximations visible to tests and documentation rather than hiding them in
# hit-path fallback logic.
_GAMMA9001_EXTENSIONS = {
    58: (382, 60, None),
    71: (374, 60, None),
    72: (374, 55, None),
    73: (352, 64, "short shaker used for short guiro"),
    74: (353, 60, "longer shaker used for long guiro"),
    78: (342, 63, "high conga used for mute cuica"),
    79: (342, 57, "low conga used for open cuica"),
    80: (371, 60, None),
    81: (372, 60, None),
}

# Tiny/general-MIDI compatibility uses the existing configured sample map.
# Every note still has an intentional family instead of disappearing.
_LEGACY_SAMPLE_KEYS = {
    **{note: "drum_bass_hard" for note in (35, 36)},
    37: "elec_tick", 38: "drum_snare_hard", 39: "perc_snap",
    40: "drum_snare_soft",
    **{note: "drum_tom_lo_soft" for note in (41, 43, 45)},
    42: "drum_cymbal_closed", 44: "drum_cymbal_pedal",
    46: "drum_cymbal_open",
    **{note: "drum_tom_mid_soft" for note in (47, 48)},
    **{note: "drum_tom_hi_soft" for note in (50,)},
    **{note: "perc_bell" for note in (49, 51, 52, 53, 55, 57, 59)},
    54: "drum_cymbal_closed", 56: "perc_bell", 58: "perc_snap",
    **{note: "drum_tom_hi_soft" for note in (60, 62, 63, 65, 67, 69, 71, 73, 75, 76, 78, 80)},
    **{note: "drum_tom_lo_soft" for note in (61, 64, 66, 68, 70, 72, 74, 77, 79, 81)},
}


def resolve_gm_percussion(
    midi_note: int,
    *,
    kit: str,
    configured_samples: Mapping[str, _Sample],
) -> GmPercussionSound | None:
    note = int(midi_note)
    name = GM_PERCUSSION_NAMES.get(note)
    if name is None:
        return None
    if str(kit) == "gamma9001":
        direct = GAMMA9001_DIRECT_PCM.get((384, note))
        if direct is not None:
            return GmPercussionSound(name, *direct)
        preset, native_note, substitution = _GAMMA9001_EXTENSIONS[note]
        return GmPercussionSound(name, preset, native_note, substitution)
    key = _LEGACY_SAMPLE_KEYS[note]
    sample = configured_samples.get(key)
    if sample is None:
        return None
    return GmPercussionSound(
        name,
        int(sample.preset),
        int(sample.note),
        f"{key} compatibility substitute",
    )


def midi_drum_amplitude(
    velocity: int,
    row_volume: float,
    velocity_gain: float,
) -> float:
    """Match equal-velocity OMNI hits at the shipped MIDI-row reference.

    At the M1 factory row volume (0.28), a velocity-60 MIDI hit and a
    velocity-60 OMNI sequence hit have identical effective gain after the
    latter's shipped percussion bus volume (0.5).  The row remains an ordinary
    relative gain control and velocity remains linear above and below 60.
    """
    velocity_level = max(0.0, min(1.0, int(velocity) / 127.0))
    relative_row_gain = (
        max(0.0, min(1.0, float(row_volume)))
        / MIDI_DRUM_REFERENCE_ROW_VOLUME
    )
    return (
        velocity_level
        * max(0.0, float(velocity_gain))
        * OMNI_REFERENCE_PERCUSSION_VOLUME
        * relative_row_gain
    )
