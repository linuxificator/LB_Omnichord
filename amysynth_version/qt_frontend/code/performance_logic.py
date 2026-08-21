from __future__ import annotations

from collections.abc import Iterable


def clamp_bass_voicing_shift(value: int | float, *, limit: int = 6) -> int:
    """Return the nearest supported bass-voicing rotation step."""
    limit = max(0, int(limit))
    return max(-limit, min(limit, int(round(float(value)))))


def roll_bass_voicing(notes: Iterable[int], steps: int) -> list[int]:
    """Rotate chord tones through adjacent inversions, one octave at a time.

    A negative step moves the current highest tone down one octave.  A
    positive step moves the current lowest tone up one octave.  Sorting after
    each move makes repeated steps equivalent to walking through adjacent
    chord inversions rather than transposing the complete bass pattern.
    """
    rolled = sorted(int(note) for note in notes)
    if not rolled:
        return []

    steps = int(steps)
    if steps < 0:
        for _ in range(-steps):
            rolled.append(rolled.pop() - 12)
            rolled.sort()
    else:
        for _ in range(steps):
            rolled.append(rolled.pop(0) + 12)
            rolled.sort()
    return rolled


def roll_chord_indexes(
    indexes: Iterable[int],
    chord_count: int,
    direction: int,
) -> list[int]:
    """Roll all chord-type rows together by one catalogue position.

    Positive direction corresponds to the UI's DWN button, i.e. the next
    entry in chords.csv.  Negative direction corresponds to UP.
    """
    chord_count = int(chord_count)
    if chord_count <= 0:
        return [int(index) for index in indexes]
    delta = 1 if int(direction) > 0 else -1
    return [
        (int(index) + delta) % chord_count
        for index in indexes
    ]
