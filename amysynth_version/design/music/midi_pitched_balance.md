# Pitched MIDI level contract

Status: authoritative runtime contract

Every melodic MIDI row follows one level policy, independently of the selected
Juno, DX7 or physical-string program. At the reference MIDI row volume of
`0.30`, an incoming note with velocity 60 has the same dry output gain as one
manually played OMNI chord note at the reference chord level of `0.50`.

The comparison is deliberately per note, not against the sum of an entire
chord. A three- or four-note chord retains its natural aggregate energy, while
a MIDI player can still add polyphony and use the MIDI-row and MIDI-master
controls to choose the musical balance.

## Gain staging

MIDI velocity continues to be sent to AMY as the ordinary `velocity / 127`
value. This matters because a patch may use velocity for timbre as well as
amplitude. Replacing velocity 60 with an artificial full-velocity event would
therefore change the instrument instead of merely correcting its level.

The calibration is applied once through AMY's per-synth output level (`iV`):

```text
output gain = row volume * instrument correction
              * 0.50 / (0.30 * (60 / 127))
```

`iV` is an output multiplier and is intentionally allowed to exceed 1.0. It
does not modify a patch's velocity response. The UI row value itself remains
bounded to 0..1, stays linear, and retains all relative differences authored
in the factory MIDI presets. The existing per-instrument correction is applied
at the same output stage. MIDI master volume is still applied exactly once on
the row's bus.

This is fixed reference calibration, not automatic gain control. It does not
measure individual notes, alter attacks, compress peaks, or continuously
change gain while somebody plays.

## Verification

`tests/test_midi_engine.py` proves the exact velocity-60 equality, preserves
the standard AMY velocity in emitted note commands, checks that output gain is
not accidentally clipped at 1.0, retains per-instrument correction, and
enumerates all 90 pitched rows in the 18 shipped MIDI presets through the same
policy. Percussion has its separate same-sample reference contract in
`midi_percussion.md` because its one-shot PCM path does not use a pitched row
synth.
