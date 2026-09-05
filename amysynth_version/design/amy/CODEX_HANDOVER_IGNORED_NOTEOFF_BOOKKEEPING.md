# Ignored note-off bookkeeping repair

Status: implemented and awaiting physical musical regression testing
Date: 2026-09-05

## Symptom and reproduction

Repeated rhythm changes while fills and arpeggios were active eventually
printed many messages of this form:

```text
**_instrument_push_forgotten_note: forgotten pool overflow synth 0 note 263/60
```

The value before the slash is a PCM preset and the value after it is the MIDI
note. These were Gamma9001 percussion events, not out-of-range MIDI notes.

The failure was reproduced on unmodified Shorepine `main` without reusable
sequences. A four-voice synth receiving 64 different one-shot note-ons while
declaring `SYNTH_FLAGS_IGNORE_NOTE_OFFS` filled AMY's 16-entry forgotten-note
pool. Therefore rhythm switching and reusable sequences only made an existing
instrument-lifecycle mismatch visible; they did not cause it.

## Root cause

AMY records a stolen or retriggered note so a later note-off can be absorbed.
That bounded record is correct for ordinary instruments. It is unnecessary for
a synth which explicitly ignores note-offs: there is no future release event
to match, so an indefinitely running percussion stream eventually fills the
pool.

Suppressing the warning with `SYNTH_FLAGS_NO_NOTE_WARNINGS` would hide the
symptom while retaining the invalid state model. Increasing the pool would
only postpone an unbounded problem. Sending periodic all-notes-off commands
from the application could truncate percussion tails and would move a generic
voice-policy concern into musical application code.

## Implemented boundary

The generic repair is isolated on AMY fork branch
`fix/ignore-noteoff-bookkeeping`, implementation commit `084247ae` with the
portable state-based test completed at `57c92c2d`:

- ignored-note-off synths do not add stolen/retriggered notes to the forgotten
  pool;
- unmatched late note-offs for such a synth are silently accepted; and
- enabling the flag clears entries accumulated under the earlier policy.

Ordinary synths retain their existing forgotten-note behavior. The fix adds no
new public API, flag, wire syntax or sequencer behavior. It uses the existing
`SYNTH_FLAGS_IGNORE_NOTE_OFFS` contract and has a dedicated C regression test
which failed before the repair and passes afterward. The complete AMY C suite
also passes.

The fix deliberately remains outside the Shorepine-facing reusable-sequence
PR because the standalone reproduction proves it is not part of that patch.
It can be considered later as a small independent upstream fix.

## Omnichord integration

Both direct-PCM percussion synths now explicitly send synth flag `if2` when
allocated:

- the main rhythm/fill synth 0; and
- the MIDI screen's preview/playback drum synth 11.

General-MIDI patch 258 already declares flags `if3` internally, which includes
ignored note-offs, so its setup is unchanged. The application still sends
only AMY wire commands and does not track PCM tail or stolen-note state.

The authoritative downstream release is
`releases/amy_omnichord_R20260905T133309` at
`f3d72dfcec453a274d726869d5bf32533c3cca3b`. During diagnosis the preceding
`R20260905T104903` branch was advanced once with the generic merge; it is no
longer the pinned build input. The new branch restores the immutable consumer
boundary and records the repair in its release contract.

## Validation contract

Required before declaring the issue closed:

1. AMY `make ctest`, including `test_ignore_note_offs`, stays green.
2. Omnichord unit and integration tests prove both direct-PCM drum synths send
   `if2`.
3. The exact new AMY SHA is installed with Gamma9001 and all Omnichord suites
   pass.
4. Physical testing repeats rhythm changes with fills and overlapping
   arpeggios long enough to exceed the old 16-entry limit, with no overflow
   messages and no shortened percussion tails.
