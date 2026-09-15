# Supernova multicore audio graph

Status: active engine performance contract
Owner: SuperCollider runtime and audio graph
Applies to: `sc_version`
Last verified: 2026-09-15

## Runtime choice

Production uses Supernova, SuperCollider's standard parallel audio server.
Source builds enable it and source launch plus all four packaged targets require
it. There is no silent `scsynth` fallback: accepting a single-core server would
make the tested graph and its performance contract differ between machines.
`scsynth` remains in the runtime for deterministic non-realtime test tools.

The server's default worker count follows the available CPU cores. LB Omnichord
does not duplicate that operating-system and SuperCollider policy in its JSON
configuration. A configurable worker override should be added only after a
measured platform needs one.

## Linux realtime startup

Process separation does not by itself imply realtime scheduling. Under the
PipeWire JACK bridge, the audio callback can receive realtime priority through
RealtimeKit while Supernova's independently created DSP helpers remain normal
`SCHED_OTHER` threads when the login session has an `RLIMIT_RTPRIO` of zero.
The audio graph then has low average CPU use but can still miss a deadline when
a desktop compositor briefly schedules work ahead of any one helper.

The Linux launcher therefore performs one bounded startup action after it has
created its private process session. Source and packaged launchers share this
same Python supervisor rather than duplicating shell lifecycle code. It resolves
the exact Supernova executable
inside that owned session, enumerates only its `DSP Thread *` tasks through
`/proc`, asks the existing system RealtimeKit service for its configured maximum
priority, applies that policy to the pool and verifies the result. It then
exits; it is neither a persistent process watcher nor a process-name search.
If the host already granted Supernova realtime access, no RealtimeKit call is
made. Other platforms retain SuperCollider's native scheduling policy.

The supervisor also owns restart safety. It rejects an occupied coordinator
port before launch, while the SC bootstrap treats a bind race as fatal before
creating OSC handlers or an audio server. Application close and OS termination
signals synchronously stop the exact private process tree. A quick restart can
therefore either start cleanly or report that the previous instance is still
finishing; it cannot silently talk to an older coordinator.

Failure to obtain host realtime service is reported explicitly but does not
silently select another engine or prevent startup. Linux package qualification
keeps this a host capability boundary because a build container need not have
an active audio session.

## Graph structure

Parallelism is explicit and limited to nodes that do not depend on one
another:

```text
parallel sources
      |
parallel channel strips and room sends
      |
parallel room effects
      |
serial master limiter and hardware output
```

The four stages retain a strict order. A native voice that needs a source node
followed by an output adapter owns an ordinary child `Group` inside the source
stage. Sample-player lifetime groups are serial for the same reason. Supernova
may schedule separate voices on separate workers, but it may not reorder nodes
within one dependent voice chain.

## Behavioral boundary

This changes server execution placement, not musical behavior. Python still
publishes immutable plans and semantic live actions. `sclang` still owns the
clock, quantization, event ordering, note lifetime and exact release handles.
The bus layout, two room effects, master limiter, protocol and UI remain
unchanged.

Supernova correctly interprets string-valued Synth controls as audio/control
bus mappings and is stricter than the former server when such a value is not a
valid mapping. The SCLOrk adapter therefore normalizes every admitted scalar
control to a float before creating a node. Native third-party voices also cross
a `Sanitize` boundary before reaching shared buses. This prevents one unstable
or non-finite source from poisoning a room effect and every other instrument;
it does not alter finite source audio.

Parallel execution provides headroom when several independent synths and
effects run together. It does not prove that every possible load is free from
audio underruns, nor does it hide an invalid graph or excessive single-node
cost. Release qualification therefore still needs the representative live
endurance workload in addition to structural and package tests.

## Evidence

Executable contracts verify that:

- source builds enable and install Supernova;
- Linux, Raspberry Pi, macOS and Windows runtimes contain it;
- the supervisor selects its exact bundled executable;
- source, mix and effect stages are parallel groups;
- the master and dependent per-voice chains remain serial;
- SCLOrk controls crossing the server boundary are numeric and non-finite
  third-party output is contained before shared effects;
- an incomplete runtime is rejected before application launch.

The SC compiler and audio suites remain authoritative for graph syntax and
signal behavior. Platform workflow tests validate the executable in each
pinned SuperCollider 3.14.1 runtime.

The separate-process live endurance driver selects Supernova explicitly and
records its native PipeWire outputs. Server node-creation exceptions are fatal
test results rather than ignored console text.

The same driver records the one-shot realtime setup result and has a focused
top-edge scenario. The QML regression keeps one held mouse grab while crossing
outside the top of the production strum surface. It verifies that the pointer
path is clamped without creating a second gesture; PipeWire's error counter is
the authority for distinguishing an audio deadline miss from a musical click.
