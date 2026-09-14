# AMY v3.2 changes

This revision addresses the first hardware test of the AMY serial port.

## Fixed

- Five permanent and independent AMY synth instances:
  - 0 drums
  - 1 bass
  - 2 strum
  - 3 manual chords
  - 4 rhythm chords
- Replaced legacy GM drum patch 258 with a four-voice, one-PCM-oscillator-per-voice drum synth. Rhythm hits send the PCM preset/native-note pairs taken from AMY's own patch-258 table.
- Reduced the strum pool to one voice. Together with the direct PCM drums this caps the worst-case Juno/DX7 allocation at 108 of AMY's standard 120 oscillators.
- No normal-runtime `iv0` synth deallocation.
- Manual and rhythm chords share patch/settings but not voices or note lifetime.
- Bass is sequencer-gated on its own monophonic synth.
- Every accompaniment rebuild explicitly stops bass and rhythm chords before
  clearing their scheduled events, preventing lost note-offs/hanging notes.
- Active-chord changes rebuild bass even when rhythm chords are disabled.
- Strum uses its own synth and explicit delayed note-offs. Delayed releases are generation-guarded so a release from before Panic or a patch change cannot silence a newer note.
- Fixed first rhythm start: chord-gate state is published before transport,
  avoiding a second rebuild which used to cancel the first queued `zY1`.
- Every live sequencer rebuild now finishes with `zY1`, even when it is not a
  phase-reset rebuild.
- One fixed manual-chord synth correctly retriggers the previous still-held
  chord when a newer chord is released.
- Panic now stops all five synths and the sequencer, invalidates stale delayed
  releases, and then unconditionally recreates all five synth definitions.

## Instruments

- Replaced Sonic Pi synth catalogue with 123 curated AMY factory patches:
  103 Juno patches and 20 DX7 patches.
- Factory AMY names are shown in the UI.
- Juno controls: filter cutoff, resonance, portamento.
- DX7 controls: feedback, algorithm, portamento.
- `-1` on patch-level controls means leave the factory patch setting intact.
- Converted all 18 factory presets to AMY selections.
- Old on-disk Sonic Pi preset keys are migrated invisibly when loaded.

## Verification

- Python files compile with `py_compile`.
- All JSON files parse.
- Worst rhythm remains within the configured 256-entry sequencer budget:
  242 entries (46 drums + 56 bass + 140 rhythm chords).
- Mock UART verifies:
  - drum initialization is `i0iv4in1Z` plus PCM wave setup, with no patch 258;
  - drum hits are direct PCM `preset + native note` events;
  - no `iv0` or `iv11` commands;
  - strum note-ons use synth 2;
  - Panic recreates synths 0 through 4;
  - manual chords are never sequenced;
  - rhythm rebuilds never all-off manual synth 3;
  - each live rebuild places `zY1` after all new `H...` definitions.
