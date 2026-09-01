# Codex handover: concurrency, real-time behavior and I/O

Status: analysis; no runtime behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Quality objective

Audio, MIDI, UI and transport remain responsive under load; resource ownership
is single-threaded and explicit; queues are bounded; failures and shutdown have
defined outcomes. Musical event ordering must not depend on incidental Python
thread scheduling.

## Existing strengths

- File logging is offloaded from the UART writer.
- Serial/socket commands use high and cancellable low-priority lanes.
- QLocalSocket is created, connected, written and closed on its worker thread,
  respecting QObject affinity.
- CC/button/activity MIDI callbacks are queued into the Qt object through
  signals.
- Unix socket and Windows named-pipe services are local/private boundaries.
- Generation tokens cancel stale queued rhythm work without changing AMY's
  internal sequencer.
- One-shot patterns give musical notes explicit ownership and normal release.

## Finding R1 — MIDI note callbacks bypass the Qt queue

`MidiPlayerBackend` constructs `_MidiInputTechManager` with
`self.process_midi_note` directly. Reader adapters call that callback from their
background thread. In contrast, CC/button/activity use Qt signals and are
processed in the QObject's thread.

`process_midi_note` reads mutable backend/owner tuning and chord state and
mutates the MIDI AMY engine. This creates an undocumented race with UI/preset/
tuning changes and shutdown.

Qt documents that direct cross-thread calls on QObjects are unsafe and that a
queued signal/slot invokes the receiver in its owning thread.

Primary references:

- [Qt Threads and QObjects](https://doc.qt.io/qt-6/threads-qobject.html)
- [Qt Synchronizing Threads](https://doc.qt.io/qt-6/threads-synchronizing.html)

Recommendation:

- normalize all reader output to immutable `MidiInputEvent` values;
- emit a queued signal to the Qt/application owner for notes as well as
  controls;
- preserve event order with one queue/sequence counter per input stream;
- if latency measurement later proves Qt queuing insufficient, hand immutable
  snapshots to a dedicated non-QObject engine rather than sharing view state;
- test note/control ordering, close races and tuning changes during input.

This is a correctness fix first, performance decision second. Measure MIDI
latency before introducing a more complex real-time queue.

## Finding R2 — transport queues were unbounded (resolved by T16)

`_SerialWriter`, `_UnixSocketWriter` and `_QtLocalSocketWriter` formerly used
unbounded deques, while `_DebugLog` used `queue.SimpleQueue`. T16 replaced them
with one bounded scheduler, concrete byte sinks and a bounded rotating debug
queue. See `code_quality_tasks/T16_TRANSPORT_HEALTH_BOUNDS.md` for proof.

Recommendation:

- define queue capacity and overload policy per lane;
- high-priority control must either be accepted within a bound or fail visibly;
- replaceable low-priority lane work should coalesce/drop stale generations;
- log queue may drop/coalesce records with a counted warning rather than block
  musical output;
- rotate or cap the log by size/count;
- export queue depth/high-water mark and dropped/coalesced count to diagnostics.

Do not use one policy for every message. A note-off/control stop is not
equivalent to replaceable bulk pattern preload.

## Finding R3 — worker failures are not consistently observable

Serial `_run` does not catch a write exception to transition a shared health
state. A worker can terminate while callers continue enqueueing. The Qt writer
records `_connect_error`, but a later `_write` failure is caught in `_run` and
does not have a uniform UI-facing failure path.

Recommendation: a transport supervisor exposes `starting`, `ready`, `failed`,
`closing`, `closed`, terminal error and queue stats. Worker boundaries catch
`BaseException` only to:

1. store the terminal failure;
2. reject/clear pending work by documented policy;
3. notify the owning application thread;
4. close resources on the correct thread;
5. terminate.

Programming exceptions must remain visible in logs/tests. Reconnect is a
separate policy and should not be automatic unless the transport supports
state reconstruction safely.

## Finding R4 — shutdown can outlive its timeout

Writers join for one second and then close the serial/socket resource even if
the worker is still alive. The worker could still use that resource. Debug-log
shutdown similarly abandons a live thread after a one-second join.

Define shutdown semantics:

- stop accepting work;
- invalidate replaceable low lanes;
- decide whether safety-critical high messages are drained or abandoned;
- wake/cancel blocking I/O;
- join to a measured, explicit deadline;
- if still alive, report a terminal shutdown failure and avoid concurrent
  resource close;
- make repeated `close()` idempotent.

Tests should simulate blocked write/read and assert bounded outcome.

## Finding R5 — delayed actions create many independent timers

The code creates `threading.Timer` objects for several delayed note/strum/
preview releases. Generation tokens reduce stale effects, but bursty input can
create many threads and separate timing domains.

Recommendation:

- AMY owns precise musical timing whenever a scheduled wire event can express
  it;
- Qt `QTimer` owns UI-thread presentation timing;
- application-only delayed work uses one bounded monotonic scheduler, not one
  OS thread per event;
- cancellation token ownership remains explicit;
- existing note-off duration behavior must be characterized before migration.

Never move audio timing into QML or use wall-clock `datetime` for sequencing.

## Finding R6 — local stream framing needs bounds

`local_amy_service.py` appends stream data until a newline; a client can cause
unbounded buffering by never sending one. The Windows native service is better:
it accumulates into a fixed `SERVICE_MAX_LINE` buffer and rejects overlong/non-Z
lines.

Recommendation:

- define one maximum AMY wire line length shared by wrappers/tests;
- reject non-ASCII, overlong or unterminated frames deterministically;
- set connection idle/read limits appropriate to the local service;
- retain packet-preserving Unix behavior when available;
- fuzz framing/parser boundaries independently from AMY synthesis.

The service is private/local, so this is primarily reliability and defense in
depth, not a claim of remote exposure.

## Finding R7 — logging has lifecycle and privacy costs

The append-only command log can grow indefinitely and records detailed musical
use. It appears not to contain credentials, but disk exhaustion and unexpected
retention remain concerns.

Recommendation:

- default normal releases to minimal diagnostics unless command logging is
  needed by product policy;
- rotate/cap logs and state retention in docs/config;
- redact filesystem/user details where unnecessary;
- make logging failure non-blocking but visible via a counter/state;
- ensure package-smoke diagnostics can opt in explicitly.

## Real-time budgets

Define measurable scenarios rather than “fast enough”:

- maximum input-event-to-enqueue latency under a documented load;
- maximum Qt frame handler time for control movement;
- maximum transport queue depth during full fill catalogue preload;
- maximum shutdown duration after transport failure;
- zero lost eventual note-offs for accepted note-ons;
- bounded stale low-priority work after a generation change;
- audio callback never waits on Python, filesystem or network I/O.

Profile before optimizing. Qt recommends asynchronous/event-driven work and
warns against long blocking work in a frame; AMY/Oboe audio ownership already
provides the correct hard real-time boundary.

## Acceptance criteria

- all MIDI input event types cross one documented thread boundary in order;
- no QObject method is invoked directly from a foreign reader thread;
- all queues have capacity, overload behavior and diagnostics;
- worker failure reaches the application deterministically;
- close is idempotent and cannot close a resource still used by a live worker;
- malformed local frames cannot grow memory without bound;
- current note duration, slider responsiveness and native audio tests remain
  unchanged.
