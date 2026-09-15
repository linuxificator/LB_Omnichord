# Strum pressure and native voice lifetime

Status: implemented performance and lifetime contract
Owner: SuperCollider gesture playback
Applies to: `sc_version`
Last verified: 2026-09-15

## Failure that was reproduced

The production QML strum was driven as one held pointer gesture through 200
alternating full-height sweeps, with drums, bass and chord arpeggios active.
The test deliberately ran for about one minute without releasing the pointer.
A second continuous gesture also exposed the effect of queued GUI events being
delivered in a short burst.

Before the fix, gesture attacks had no engine-side admission boundary. Every
native attack allocated a source node, output node, owned group, stereo audio
bus and control bus. The burst reached 36,513 UGens, 1,007 synth nodes and
11,024 groups. At `strum/1784`, the language-side audio-bus allocator was
exhausted. Subsequent attacks tried to use a `nil` bus and produced an 18 MiB
error log. Average DSP use before the burst was low; this was resource pressure
from unbounded graph mutation, not ordinary sustained Supernova CPU load.

## Implemented boundary

The frontend still has no voice-stealing implementation and does not own note
lifetimes. Every accepted gesture attack keeps its exact handle and its normal
engine-timed tail. SuperCollider now admits at most
`server.gesture_voice_limit` live handles per gesture owner; the shipped value
is 24. One complete triad strum across the seven-octave surface fits inside
that boundary.

When a caller exceeds the boundary, SuperCollider releases the oldest handle
first. Only this overload release is shortened to four server control blocks,
with a 5 ms floor. This is long enough to avoid a discontinuous hard free while
preventing stale release tails from recreating an unbounded resource spike.
Normal strum notes retain the configured 450 ms tail and the selected
instrument's output release.

The limit is per owner. OMNI strum, MIDI preview and any future gesture caller
therefore cannot evict each other's voices. Chords, sequencer events, drums and
ordinary MIDI note ownership are unchanged.

## Verification

Run the production-QML pressure scenario with:

```bash
./.venv/bin/python sc_version/qt_frontend/tests/endurance/sc_endurance.py \
  --cycles 2 --chunk-seconds 90 --scenario strum-pressure --gui
```

The scenario uses real Qt mouse events against `StrumPad.qml`, holds one press
for each minute-long cycle and records Supernova output from a separate
PipeWire process. Audio-bus allocation failure and the resulting `nil.index`
error are fatal test results.

With the 24-voice boundary, the same two-cycle overload completed without SC
errors, clipping or a long audio dropout and returned to 31 synth nodes after
the gesture load drained. The deliberately bunched test injector still caused
a short transient of 458 synth nodes because already-releasing voices retain a
5 ms fade; it no longer exhausted buses or left the graph at that size. This
synthetic peak is not the steady physical-input load.

The local desktop could not grant realtime priority to Supernova, but its
PipeWire error counter remained unchanged after graph activation during the
successful pressure run. Realtime scheduling remains a host configuration
concern and is not substituted by increasing audio latency here.
