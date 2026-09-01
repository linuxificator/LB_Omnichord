# T13 result: MIDI platform adapters and one event boundary

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: MIDI input ports, platform adapters and QObject thread ownership
Applicability: Linux, macOS, Windows, Android and unsupported package profiles

## Outcome

- Added a frozen normalized `MidiInputEvent` for note, control, translated
  button and activity events. One lock-protected emitter assigns a total
  sequence across simultaneous native readers and stops accepting events before
  adapter shutdown.
- Added the small `MidiInputPort` lifecycle/capability contract: immutable
  technology descriptions, `start`, typed status snapshots, lifecycle state and
  idempotent `close`.
- Moved raw device discovery/readers, ALSA sequencer `ctypes` integration,
  `/dev` knowledge and native reader threads out of `midi_player.py` into the
  Linux adapter. The byte-stream parser remains portable and now uses explicit
  per-stream state values.
- Added explicit unavailable adapters for CoreMIDI, WinMM and Android MIDI.
  They expose the existing labels/red status without importing or pretending to
  implement an unbundled native API. Unknown profiles expose no technology.
- Application composition now injects the selected MIDI-port factory through
  the integrated backend. Platform resolution occurs once at that edge; the
  portable MIDI player imports no resolver or concrete adapter.
- Replaced three event-specific callbacks/signals and the direct note callback
  with one non-QObject relay and one queued Qt signal. The QObject receiver
  drains by sequence number before calling musical/control handlers.
- Retained the product rule that ordinary Note On/Off is musical input and never
  becomes a controller button implicitly. The event contract can carry a button
  only after an explicit future translation/whitelist adapter classifies it.

## Behavior and architecture proof

- The existing platform labels, disabled/unavailable/listening/activity
  meanings, ALSA raw + ALSA sequencer + OSS discovery and legacy raw-glob
  override are unchanged.
- The parser characterization still proves split messages, running status,
  velocity-zero Note Off, SysEx/realtime filtering, CC and 14-bit Pitch Bend.
- New shared tests cover immutable ordered events, independent parser state,
  no callback after close, lifecycle/idempotent close, all package profile
  selections, disabled Linux startup, exact two-raw/one-sequencer construction,
  readable-device activity and explicit unavailable adapters.
- A real Qt worker-thread test proves the relay's receiver slot executes only
  on its QObject thread. A receiver-order test submits sequence 2 before 1 and
  proves note/control/button/activity are dispatched in sequence order.
- An AST/source test rejects native imports, `/dev` probes and the old direct
  `process_midi_note` callback from the portable module. The repository quality
  policy permits `ctypes` only in `midi_linux.py`.
- Existing MIDI engine, refactor characterization, sound-balance, application
  composition, packaging and Android packaging tests pass. Frontend integration
  passes with the real production composition path.
- The complete quality, unit, frontend, serial, preset, native-control and
  native-rhythm suite passes.
- Quality passes with all three new production modules strict-mypy clean. The
  legacy mypy inventory fell from 46 to 43 errors because native code left the
  broad legacy module.

## Findings and progressive insight

- Moving only the reader classes would have preserved the unsafe direct note
  callback. Extracting the lifecycle and changing the callback shape together
  avoided touching the same boundary twice and made shutdown filtering
  enforceable in one place.
- Qt queues emissions from foreign threads correctly, but independent sender
  threads do not by themselves define a musical total order. Serializing signal
  emission and retaining a sequence-aware receiver makes that ordering an
  application contract rather than an incidental scheduler outcome.
- ALSA raw and ALSA sequencer can fail independently. The port therefore stays
  ready while individual technology statuses report availability; one missing
  native endpoint must not disable other MIDI inputs.
- The shipped config still carries Linux path override fields for backward
  compatibility. They are frozen typed input consumed only by the Linux
  adapter, so they no longer contaminate portable code. Removing the historical
  fields from the common schema would require a versioned config migration that
  distinguishes untouched defaults from intentional user overrides; that is
  not safe to hide inside this platform extraction.

## Follow-up task effects

No new prerequisite is inserted into T14-T25. A later explicitly versioned
configuration task may replace the legacy Linux path fields with optional
adapter-scoped overrides, but only with preservation tests for customized user
configs. T14 can now apply the same injected-small-port pattern to runtime
paths/diagnostics without creating a broad platform service locator.
