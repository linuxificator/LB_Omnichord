"""Engine-neutral level policy for externally played MIDI instruments."""

from __future__ import annotations


MIDI_PITCHED_REFERENCE_VELOCITY = 60
MIDI_PITCHED_REFERENCE_ROW_VOLUME = 0.30
OMNI_REFERENCE_CHORD_NOTE_LEVEL = 0.50
MIDI_DRUM_REFERENCE_ROW_VOLUME = 0.28
OMNI_REFERENCE_PERCUSSION_VOLUME = 0.5
MIDI_DRUM_GAIN = 5.0


def normalized_midi_velocity(velocity: int) -> float:
    """Map a seven-bit MIDI velocity to the engine protocol's 0..1 range."""
    return max(0.0, min(1.0, int(velocity) / 127.0))


def midi_pitched_synth_level(
    row_volume: float,
) -> float:
    """Return the output gain which establishes the velocity-60 reference.

    A factory MIDI row at volume 0.30 and velocity 60 has the same dry output
    gain as an OMNI chord note at level 0.50. Row volume remains a linear
    relative control. Program-specific gain calibration is
    owned by the SuperCollider catalogue rather than frontend configuration.
    """
    reference_velocity_level = MIDI_PITCHED_REFERENCE_VELOCITY / 127.0
    output_gain = OMNI_REFERENCE_CHORD_NOTE_LEVEL / (
        MIDI_PITCHED_REFERENCE_ROW_VOLUME * reference_velocity_level
    )
    return (
        max(0.0, min(1.0, float(row_volume)))
        * output_gain
    )


def midi_drum_level(velocity: int, row_volume: float) -> float:
    """Match a factory MIDI drum hit to the OMNI percussion reference."""

    relative_row_gain = (
        max(0.0, min(1.0, float(row_volume))) / MIDI_DRUM_REFERENCE_ROW_VOLUME
    )
    return (
        normalized_midi_velocity(velocity)
        * MIDI_DRUM_GAIN
        * OMNI_REFERENCE_PERCUSSION_VOLUME
        * relative_row_gain
    )
