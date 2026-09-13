"""Level policy for externally played pitched MIDI instruments.

AMY velocity remains the normalized MIDI velocity because patches may use it
for more than loudness.  The level correction therefore belongs at AMY's
per-synth output stage (``iV``), which changes gain without changing timbre.
"""

from __future__ import annotations


MIDI_PITCHED_REFERENCE_VELOCITY = 60
MIDI_PITCHED_REFERENCE_ROW_VOLUME = 0.30
OMNI_REFERENCE_CHORD_NOTE_LEVEL = 0.50


def normalized_midi_velocity(velocity: int) -> float:
    """Map a seven-bit MIDI velocity to AMY's ordinary 0..1 range."""
    return max(0.0, min(1.0, int(velocity) / 127.0))


def midi_pitched_synth_level(
    row_volume: float,
    instrument_level: float = 1.0,
) -> float:
    """Return the output gain which establishes the velocity-60 reference.

    A factory MIDI row at volume 0.30 and velocity 60 has the same dry output
    gain as an OMNI chord note at level 0.50.  Row volume and per-instrument
    corrections remain linear relative controls.
    """
    reference_velocity_level = MIDI_PITCHED_REFERENCE_VELOCITY / 127.0
    output_gain = OMNI_REFERENCE_CHORD_NOTE_LEVEL / (
        MIDI_PITCHED_REFERENCE_ROW_VOLUME * reference_velocity_level
    )
    return (
        max(0.0, min(1.0, float(row_volume)))
        * max(0.0, float(instrument_level))
        * output_gain
    )
