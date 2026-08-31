# Codex handover: architecture and responsibility boundaries

Status: analysis and refactoring direction; no behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Existing architectural strengths

The product-level boundaries are clearer than the current Python composition:

- Qt emits AMY wire commands and does not own the synthesizer;
- AMY owns audio generation through a platform service/backend;
- OMNI and MIDI have separate user-facing state and presets;
- platform transports are capability-specific;
- AMY remains generic and Omnichord musical policy remains in LB;
- native/package tests prove the boundary on all release targets.

These rules must remain true during refactoring. The goal is to make the code
shape reflect them, not to introduce a new framework.

## Current dependency shape

There is no detected Python import cycle, which is a valuable starting point.
The difficult coupling is dynamic and object-level:

- `code/main.py` wildcard-imports `app_core`, then assigns alternate loader,
  client and backend implementations into `app_core` globals;
- `code/amy_serial.py` dynamically republishes almost every name from
  `amy_transport`;
- three classes named `InstrumentBackend` form an inheritance stack across
  `app_core.py`, `performance_backend.py` and `midi_integration.py`;
- the 3,333-line base constructor calls overridable methods, forcing subclasses
  to establish selected fields before `super().__init__` and tolerate partial
  construction;
- `MidiPlayerBackend` accepts broad `owner` and `client` objects typed as
  `Any`, then reads/writes many private fields and methods such as `_synths`,
  `_runtime`, `_rhythm`, `_chord_volume`, `_bass_voicing_shift` and tuning
  tables;
- `AmySerialClient` is both transport facade and a substantial musical/rhythm
  compiler.

This produces temporal coupling: correct initialization depends on assignment
order, construction order and private knowledge that no interface describes.

## Change scenarios

Following the SEI approach, architecture improvements should be judged by
specific changes:

1. Add a MIDI input adapter without changing musical engines or QML layout.
2. Add a new AMY transport without duplicating priority scheduling or command
   compilation.
3. Add a preset field without editing unrelated screen/controller code.
4. Change a drum bank without changing transport framing.
5. Test rhythm planning without constructing QApplication, serial hardware or
   a user directory.
6. Replace a QML view without exposing mutable backend internals.

The current system can accomplish these changes, but often through the large
facades and broad fixtures. The desired architecture reduces the set of files
and runtime states touched by each scenario.

Primary references:

- [SEI quality-attribute scenarios](https://insights.sei.cmu.edu/library/reasoning-about-software-quality-attributes/)
- [SEI modifiability tactics: coupling, cohesion and change cost](https://www.sei.cmu.edu/library/modifiability-tactics/)
- [SEI Architecture Tradeoff Analysis Method](https://sei.cmu.edu/library/the-architecture-tradeoff-analysis-method/)

## Proposed dependency direction

Use a pragmatic ports-and-adapters shape, implemented with ordinary Python
modules and `Protocol`/dataclass types:

```
QML views
   |
Qt view-model/facade adapters
   |
application use cases / session coordinators
   |
pure musical and control domain services
   |
small outbound ports (AMY command sink, clock, store, MIDI input)
   |
serial / Unix socket / named pipe / ALSA / JSON adapters
```

The arrows represent allowed knowledge. Domain code must not import PySide,
serial, sockets, filesystem paths or package-smoke flags. Adapters may depend
inward on port contracts. QML should only know stable view-model properties and
semantic operations.

This is a dependency rule, not a demand for directories named `domain`,
`application` and `infrastructure`. Start with clear modules inside the current
package; reorganize directories only when the seams have proven useful.

## Candidate components

### Pure domain/value layer

- immutable voice, synth, bus and tag identities;
- chord/tuning transforms;
- rhythm/fill/bass-riff definitions and plans;
- control target and MIDI binding values;
- preset data and migration transforms;
- AMY command value or validated wire line.

These are deterministic and should have no QObject state or I/O.

### Application services

- `OmniSession`: coordinates manual performance and visible OMNI state;
- `MidiSession`: coordinates MIDI-screen rows and input routing;
- `PresetService`: load/apply/save orchestration over a store;
- `BindingService`: MIDI learn/takeover state machine;
- `RhythmService`: selection/activation and pure plan creation;
- `TransportSupervisor`: owns lifecycle and observable health of one command
  sink.

Names are illustrative. Do not create empty wrapper classes. Extract only a
coherent operation with a clear input/output contract and tests.

### Ports

- `AmyCommandSink.send`, priority/cancellation and health;
- `MidiInputPort.start/stop` plus immutable input events;
- `PresetStore` and `ConfigStore`;
- monotonic `Clock`/bounded scheduler where timing is application policy;
- `DiagnosticsSink` with explicit retention/backpressure.

Avoid one enormous repository-wide service interface. Ports should be the
smallest behavior a use case needs.

### Adapters

- serial, Unix socket and QLocalSocket AMY writers;
- ALSA raw/sequencer, OSS and platform MIDI readers;
- JSON filesystem stores;
- QObject view models and QML components;
- native package and test-control adapters.

## Composition root

`main.py` should become the only composition root. It should:

1. parse arguments;
2. load and validate typed config;
3. select platform adapters explicitly;
4. construct domain/application services;
5. construct the Qt facade with explicit dependencies;
6. expose it to QML;
7. own ordered shutdown and error reporting.

It should not wildcard-import or assign into another module's globals. Tests
should construct the same objects with fake ports, not use a separate hidden
composition model.

## Inheritance versus composition

The `InstrumentBackend` extension stack should be retired incrementally.
Replacing it in one rewrite is too risky because QML, presets, performance and
native tests depend on its public surface.

Safe strangler sequence:

1. Freeze the QML-visible property/signal/slot contract with introspection and
   behavioral tests.
2. Extract one pure collaborator from the base class and delegate to it.
3. Move overrides into explicit collaborators supplied by the composition
   root.
4. Keep a thin QObject facade with the old QML API.
5. Remove an inheritance layer only when no override remains.

Never let a constructor call a method intended for subclass override. Avoid
objects that are deliberately half initialized.

## State ownership rules

Each mutable state item needs one owner:

- the Qt thread owns view-model state;
- a transport worker owns its socket/serial QObject and queue mechanics;
- immutable events cross thread boundaries;
- the musical domain returns new values/plans rather than mutating view state;
- AMY voice/tag ownership remains declared in validated config;
- persistence stores serialized snapshots, not live QObject dictionaries.

MIDI and OMNI may intentionally exchange a defined snapshot (for example,
tuning when coupling is enabled). They should not traverse each other's private
fields. Add a narrow read-only `OmniPerformanceSnapshot` or explicit signal for
each allowed dependency.

## Error model

Use typed failures at boundaries:

- configuration errors are complete, path-specific startup errors;
- transport failures transition a supervisor to failed and notify the UI;
- invalid musical data identifies file, item and invariant;
- user-store errors preserve the previous file and expose a recoverable error;
- programming invariants fail loudly in tests rather than being swallowed by a
  broad `except`.

Do not create an all-purpose result/error framework. A small exception type per
boundary and one application error-reporting path is sufficient.

## Architecture decision records

Decisions that constrain several subsystems should have short ADRs or an ADR
section in the owning design contract: context, decision, alternatives,
consequences and verification. Good candidates are:

- wire-only Qt/AMY process split;
- one authoritative resolved config;
- QObject thread-affinity policy;
- frozen public QML facade during backend extraction;
- package acceptance/release provenance policy.

Behavioral contracts remain authoritative; ADRs explain why and do not copy
every behavior statement.

## Non-goals

- no rewrite;
- no dependency-injection framework or event bus;
- no AMY-specific policy moved into QML;
- no generic AMY change for an Omnichord-only concern;
- no merger of OMNI and MIDI preset/state ownership;
- no replacement of real native/package tests with mocks;
- no speculative plugin architecture before a second implementation needs it.

## Success measures

- new adapters change one adapter module plus composition and targeted tests;
- pure rhythm/tuning/preset tests need no Qt or I/O;
- mypy can describe cross-module dependencies without pervasive `Any`;
- QML public behavior and AMY wire output remain byte/sequence compatible;
- startup and shutdown order are explicit and covered;
- each extraction reduces methods/private-field reach in the large facades;
- the full five-platform release remains green after every incremental phase.
