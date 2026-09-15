# SuperCollider edition architecture

Status: authoritative architecture contract
Owner: application, process and engine boundary
Applies to: `sc_version`
Last verified: 2026-09-15

## Composition

`qt_frontend/code/main.py` is the sole production composition root. It loads
one validated frontend configuration, constructs one `SuperColliderClient` and
injects that semantic client into the application backend. There is no runtime
transport selector and no serial, socket or in-process synth fallback.

Source and frozen entry points use the same Python supervisor for one headless
`sclang` process group; `sclang` owns the Supernova audio server:

```text
launcher / frozen entry
├── Qt/Python frontend
└── sclang coordinator
    └── Supernova multicore audio server
```

Startup first verifies that the configured language UDP endpoint is available;
the SC bootstrap repeats that check before it installs any OSC handler, closing
the unavoidable check-to-bind race. A collision therefore fails before the UI
can connect to a stale coordinator. Normal application exit and termination
signals both stop the complete owned process group with a bounded graceful
then forced fallback. Shutdown never searches by executable name.

## Protocol and execution

`engine_protocol.py` owns immutable typed actions and validation.
`musical_sequence_plan.py` is a pure compiler. `supercollider_client.py` owns
OSC delivery, sessions, indexed transactions, acknowledgements/retry, program
preparation and live voices. The protocol carries musical meaning rather than
raw node IDs.

The coordinator schedules on one `TempoClock`. Definitions publish atomically;
an execution keeps its captured snapshot. Stable same-beat ordering is control,
child launch, release, voice change, then attack. Root definitions may launch
one finite child level; authored recursive nesting is rejected. Python never
polls phase or follows beats.

## Audio and program graph

Logical role IDs are not raw SC buses. Sources feed channel strips, sends, two
room effects and a master limiter. Supernova runs the independent source nodes,
channel strips and room effects in three ordered parallel groups. The master
output follows those groups. A dependent source/output pair for one voice stays
in an ordinary serial group, so multicore execution cannot reverse its signal
flow. Voice owners remain distinct even when they share a mix bus. Native
SCLOrk programs, four acid programs and manifest-driven VSCO sample programs
use stable IDs. Sample preparation is off the audio path, reference-counted
and bounded; failure leaves the prior program intact.

## Configuration and packaging

`config/frontend.json` owns frontend/input/layout policy.
`config/supercollider.json` owns engine process, protocol and sample-memory
policy. External source identities live in `supercollider/source-lock.json` and
`packaging/supercollider_release_inputs.json`. Packages contain only this
frontend, SC sources and a pinned SC 3.14.1 runtime. VSCO recordings remain a
separate verified CC0 asset.

Integration senders, frontend and fake/real coordinator use distinct processes.
NRT audio tests do not take a live device. Package verification exercises a
clean user directory, configuration migrations, the production graph, runtime
executables and bootstrap without opening audio.
