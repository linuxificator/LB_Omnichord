# T15 result: pure AMY command plans

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: AMY parameter and musical command compilation

## Outcome

- Added `amy_parameter_plan.py` as the single deterministic compiler for the
  Juno and DX7 controls that OMNI and MIDI actually share. The OMNI adapter
  supplies an explicit changed-key set for selective updates; MIDI supplies a
  complete row state. DX7 envelope ownership remains explicit: changing one
  envelope member emits the complete application-owned output envelope.
- Added `rhythm_command_plan.py` with immutable result values for tagged lanes,
  chord/arpeggio one-shots and fill scheduling. Bass activity/riffs, drum
  activity patterns and immutable fill definitions are pure functions as
  well. They accept all musical policy and capacity values as arguments.
- Reduced `AmySerialClient` to state selection and plan submission. It still
  owns catalogue lookup, current rhythm state, queue selection and wire I/O;
  it no longer implements the actual event-to-command algorithms.
- Preserved compatibility adapters for the private helpers exercised by older
  characterization tests. Those adapters delegate directly and contain no
  second algorithm.

## Compatibility and proof

- Independent pure tests assert exact Juno/DX7 commands, selective updates,
  tagged replacement/clearing, arpeggio note ownership, bass activity/riff
  conversion, drum activity, fill definition and fill-cycle scheduling.
- An AST dependency test proves both pure modules import no PySide6, serial,
  socket, `amy_transport` or `midi_player` module.
- Existing drum catalogue, sequencer-tag, MIDI engine and sound-control suites
  retain their exact command expectations. This proves that the extraction did
  not alter native AMY command streams at the established public entry points.
- Both pure modules pass strict mypy independently. The complete project
  quality suite passes with 40/42 legacy mypy errors (two fewer than the
  ceiling) and 16 strict modules. The complete unit/frontend behavior runner,
  including native rhythm and transport characterization, passes.

## Findings and progressive insight

- The former OMNI and MIDI parameter compilers were nearly identical but had
  already started to drift in presentation and clamping detail. A shared pure
  compiler is appropriate only because patch semantics match; lifecycle,
  row/synth selection and partial-update policy deliberately remain separate.
- Fill mute commands are part of the immutable fill definition, whereas
  quantization belongs to the root schedule. Keeping those plans separate
  makes this important musical distinction executable and directly testable.
- Arpeggio one-shots own both note-on and note-off. Replacing a root schedule
  can therefore prevent old-rate future notes without truncating a note that
  is already sounding.
- Tagged-lane high-water state is the one stateful exception around a pure
  plan: the compiler receives and returns it explicitly, so cancellation-safe
  clearing remains visible rather than hidden in a transport helper.

## Follow-up task effects

T16 can now build scheduler and sink contracts around opaque complete command
records; it must not absorb parameter or musical compilation again. T17 may
move suitable delayed musical events into AMY time, but must preserve the
one-shot note-ownership invariant characterized here. No additional task is
needed beyond those already ordered.
