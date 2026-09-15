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

The launcher or frozen entry supervises one headless `sclang` process group;
`sclang` owns `scsynth`:

```text
launcher / frozen entry
├── Qt/Python frontend
└── sclang coordinator
    └── scsynth audio server
```

Shutdown targets only the owned process group and never searches by executable
name.

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
room effects and a master limiter. Voice owners remain distinct even when they
share a mix bus. Native SCLOrk programs, four acid programs and manifest-driven
VSCO sample programs use stable IDs. Sample preparation is off the audio path,
reference-counted and bounded; failure leaves the prior program intact.

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
