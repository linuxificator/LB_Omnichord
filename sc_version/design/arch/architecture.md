# SuperCollider edition architecture

Status: authoritative architecture contract

Owner: application, process and engine boundary

Applies to: `sc_version`

Last verified: 2026-09-14

## Composition

`qt_frontend/code/main.py` is the sole frontend composition root. It supplies
the existing Qt application with `SuperColliderClient` for every historical
transport factory slot, so frontend behavior cannot accidentally choose AMY,
serial or a local synth implementation. The engine label makes diagnostics
explicit without branching musical policy.

`supercollider_platform_adapter.py` owns runtime discovery and one process
group. Source startup is performed by `run_local.sh`; the frozen entry owns the
same lifecycle for its bundled runtime. Both launch `sclang -D bootstrap.scd`.
The bootstrap selects the exact packaged `scsynth` and plugin directory, boots
the server, creates the audio graph, loads the initial GM percussion sample
program and only then announces readiness.

The current process graph is:

```text
launcher / frozen entry
├── Qt/Python frontend
└── headless sclang
    └── scsynth
```

Shutdown targets only this owned process group. It never kills unrelated SC
processes by executable name.

## Typed protocol

`engine_protocol.py` owns frozen actions and validation.
`musical_sequence_plan.py` is a pure compiler. `supercollider_client.py` owns
OSC delivery, session IDs, indexed transactions, acknowledgement/retry,
program preparation and live voice commands. It does not translate AMY wire
syntax.

The protocol is loopback-only in the current trust model. Large lane updates
are indexed transactions: definitions and events are staged, validated and
published atomically. Duplicate delivery is idempotent; incomplete delivery is
retried; invalid input receives an explicit error. Live notes use exact
application handles and separate owner identities.

## Musical execution

Python publishes immutable root and finite definitions. One SC coordinator
uses a `TempoClock` and schedules only the next due logical beat. It preserves
stable same-beat ordering: controls and gates, child launches, releases,
existing-voice changes, then attacks. Child definitions are captured when an
execution starts, so republishing changes future starts without mutating a
running phrase.

The authored nesting boundary is root to one finite child. Internal lifecycle
controls do not permit recursive musical definitions. Finite children own
their releases. Stopping a root prevents future launches but does not destroy
already-running child phrases or their release events.

## Audio graph and programs

Logical bus IDs preserve the established eleven-role layout but are not raw SC
bus indexes or node IDs. Source groups precede channel strips, sends, two room
effects and the master stage. Manual and automatic chords share a logical mix
bus while retaining separate voice owners.

Programs have stable catalogue IDs and revisions. A sample program is prepared
off the audio path, becomes selectable only after a ready status, and stays
alive while program or voice references exist. Admission uses an explicit RAM
budget and reports failure without partially replacing the old program.

The SC tree contains three native acid voices, adapters for the pinned 109
SCLOrk definitions and a manifest-driven VSCO sampler. The implementation
status document lists sound-bank semantics that are not yet complete.

## Configuration and packaging

`config/supercollider.json` owns protocol, port, server and sample-memory
settings. `packaging/supercollider_release_inputs.json` and
`supercollider/source-lock.json` own pinned external source identities. The SC
package excludes AMY modules and contains the frontend, engine sources and a
pinned headless SC 3.14.1 runtime. VSCO recordings remain a separately
installed CC0 asset bank.

The independent SC workflow currently builds Linux x86_64 only. Ordinary
pushes test and upload an artifact. Publication requires manual
`release=true`; tags end in `-SC`. The AMY workflow follows the same explicit
release rule but otherwise remains independent.

## Test boundary

Unit tests may instantiate narrow objects. Integration senders, the Qt
frontend and fake/real SC coordinator run in distinct processes. NRT audio
tests render without taking a live audio device. The package smoke verifies the
bundled runtime without opening audio. Legacy AMY integration tests run the
original AMY frontend explicitly as a frozen behavioral oracle and are never
mistaken for SC runtime evidence.
