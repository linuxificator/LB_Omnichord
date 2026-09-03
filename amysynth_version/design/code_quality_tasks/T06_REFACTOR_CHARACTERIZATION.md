# T06 result: refactor characterization contracts

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: LB Omnichord maintainers
Applicability: public Qt API, configuration entrypoints, MIDI normalization,
AMY commands, writer lifecycle and QML slider interactions

## Outcome

- Added a machine-readable characterization manifest for every behavior
  boundary that T07-T21 intends to move.
- Froze the complete inherited public Qt meta-object surface, not merely the
  members declared in the final subclass. `InstrumentBackend` currently has
  57 properties and 138 public signals/slots; `MidiPlayerBackend` has 17 and
  55. The test reports the actual name list when a digest changes.
- Proved that the source entrypoint, public compatibility module, application
  core after composition and headless integration entrypoint all reach
  `config_loader.load_amy_config`. All callable routes return the same resolved
  shipped configuration.
- Loaded the untouched shipped configuration while resolving Linux, macOS,
  Windows, Android and an unsupported profile. Profile resolution does not
  mutate configuration data.
- Characterized MIDI packet splitting, running status, Note On velocity-zero
  normalization, real-time-byte handling, SysEx suppression, CC and centered
  14-bit pitch bend.
- Characterized current writer priority, low-lane generation cancellation,
  close/idempotence behavior, post-close rejection, ASCII/LF framing and the
  current open/write exception seams.
- Made the existing byte-exact OMNI, MIDI, fill and arpeggio tests, plus the
  six critical slider regression tests, explicit members of the refactor
  characterization manifest. A structured test rejects stale test routes.
- Changed no production behavior or configuration.

## Existing wire behavior now routed as a refactor contract

The authoritative manifest points at executable tests for:

- sparse OMNI parameter updates and adjacent dual-synth restoration;
- complete MIDI patch/guard/compatibility/parameter/bus/volume order;
- 270 preloaded one-shot fills and generic role-tag mute commands;
- tagged sequencer clearing and exact one-level arpeggio pattern commands;
- mouse/touch multi-move, delayed backend echo, model replacement during a
  press, bound-control track clicks and manual unlink behavior.

This preserves independent literal AMY protocol expectations. Later command
compiler work must satisfy these tests; it must not regenerate its expected
output from the implementation being tested.

## Verification

- `test_refactor_characterization.py`: 6 passed
- `test_transport_characterization.py`: 5 passed
- complete unit suite: passed, including real Unix packet/stream socket tests
- quality suite and complete integration/native suite: passed as part of the
  final T06 gate
- `git diff --check`

The local socket suite was run outside the filesystem sandbox because the
sandbox forbids binding Unix sockets. This is an execution constraint, not a
product skip.

## Findings and progressive insight

- The shipped `midi_input.tech_profile` still selects Linux explicitly. The
  five-profile test therefore calls the current platform capability function
  with an explicit profile; T07 must change ordinary shipped selection to
  automatic and add a separate override seam. The test intentionally freezes
  capability presentation, not this known defect.
- `main.py` obtains the canonical loader but installs it into `app_core` by
  global assignment. T11 must preserve the proven loader identity while
  replacing this composition-time mutation.
- `amy_transport.py` still contains an older internal loader implementation.
  It is not used by the supported entrypoints, but remains a second code
  authority until T12 removes it.
- The current writer accepts every high/low item into unbounded deques. Worker
  exceptions have no explicit health channel; construction and direct writes
  are the only observable exception seams characterized here. T16 must add
  bounds and terminal health without changing priority or valid byte order.
- Close invalidates and clears replaceable low work while allowing already
  accepted high-priority work to drain. T16 must preserve that safety intent
  while proving the worker/resource shutdown ordering explicitly.
- Public QObject hashes are ratchets, not an instruction to preserve accidental
  internals forever. T21 may deliberately revise the manifest only when QML
  call sites and compatibility policy prove a reviewed public API change.

## Follow-up task effects

No new task is required. Findings sharpen existing tasks:

- T07 owns automatic MIDI platform selection;
- T11 owns composition-time global assignments;
- T12 owns the obsolete transport config loader;
- T13 owns normalized immutable MIDI events and queued thread delivery;
- T15 owns pure command plans while keeping the manifested wire output;
- T16 owns bounded queues, health and robust shutdown;
- T20/T21 own UI/facade moves under the slider and QObject contracts.
