# T16 result: bounded scheduler, byte sinks and transport health

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: AMY command delivery and debug logging

## Outcome

- Replaced the serial-writer inheritance tree with `CommandScheduler`
  composition. `SerialByteSink`, `UnixByteSink` and `QtLocalByteSink` implement
  only open/write/close and framing capability; no socket writer inherits a
  serial resource model.
- One worker now owns each sink for its complete lifetime. This retains
  QLocalSocket thread affinity and prevents `close()` from closing a resource
  while a blocked worker still uses it.
- Added hard queue bounds. Critical/high work has priority and full admission
  raises `BufferError`, so a safety command never disappears silently.
  Replaceable lane work is generation-coalesced; at the hard capacity only its
  oldest queued item is dropped and the loss counter increases.
- Added immutable `TransportHealth`: lifecycle, depths/high-water marks,
  replaceable drops, stale coalescing, terminal error and shutdown timeout.
  Submission after terminal sink failure raises `TransportFailed`.
- Made close idempotent: pending critical work drains in order, replaceable
  work is cancelled, and sink close happens in the worker's `finally` block.
- Bounded the asynchronous debug queue, exposed dropped-record count and rotate
  a four-MiB log to one `.1` predecessor. Log overload never blocks musical
  command delivery.

## Compatibility and proof

- Scheduler tests cover high-before-low ordering, generation cancellation,
  explicit critical overflow, bounded replaceable overflow, terminal failure,
  repeated close and blocked close without premature resource destruction.
- Serial tests prove synchronous open failure, exact LF/ASCII framing and one
  close. Real Unix `SEQPACKET`/stream and QLocalSocket tests prove the existing
  packet/framing contracts.
- Debug tests prove rotation and visible non-blocking queue loss.
- The allocation-guard proof is split at the correct boundaries: the serial
  integration test verifies that startup places a 10 ms guard between synth 4
  allocation and its next command, while a scheduler test measures the two
  physical sink writes around a guard. A PTY read timestamp is deliberately
  not used for write timing because the kernel may return separately timed
  writes in one buffered read after reader-thread scheduling latency.
- Existing sequencer tag tests retain ordering and cancellation expectations.
- Both new modules pass strict mypy. Whole-project quality passes with 37/42
  legacy mypy errors (five below the ceiling) and 18 strict modules. The full
  unit/frontend behavior runner, including real serial-PTY MIDI, Unix socket,
  QLocalSocket, sequencer and packaging contracts, passes.

## Findings and progressive insight

- Queue capacity is a non-negotiable implementation safety limit, not musical
  configuration. Its single authority is therefore the scheduler module; it
  is deliberately not exposed as a user setting that could disable the bound.
  The 65,536-record critical bound is sized above the characterized startup
  burst that authors more than 700 fills; tests use deliberately tiny injected
  capacities to prove overload behavior.
- “Low priority” means replaceable generation-owned plan work, not permission
  to lose arbitrary commands. The lane/generation contract is what makes
  coalescing safe and measurable.
- A close timeout cannot force safe resource reclamation in Python. The safe
  result is a visible timeout with a still-owned live sink; the worker closes
  it only after the blocked operation returns.
- A terminal audio-transport failure must not abort the Qt batch carrying
  unrelated MIDI/UI state. Direct scheduler submission still fails explicitly;
  the application adapter reports the first failure once and retains immutable
  failed health while allowing the input event batch to finish.

## Follow-up task effects

T17 should schedule application delays above this boundary and must not put a
timer facility back into byte sinks. Release/runtime diagnostics may surface
`TransportHealth` later without changing its immutable contract. No new task
is required.
