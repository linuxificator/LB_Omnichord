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
is 64. This covers the natural overlap produced by several fast complete
triad sweeps across the seven-octave surface and the configured 450 ms gesture
tail.

When a caller exceeds the boundary, SuperCollider releases the oldest handle
first. Only this overload release is shortened, with a 50 ms floor. Release
gain and release time use one stable two-channel control bus, so changing the
fade never races a node that has already ended. Normal strum notes retain the
configured 450 ms tail and the selected instrument's output release.

An earlier development value of 24 voices with a 5 ms overload fade prevented
resource exhaustion but introduced a new audible click in preset 16. With only
a selected C chord and uninterrupted strumming, its recorded waveform had an
isolated 0.1254 full-scale adjacent-sample step. The same reproduction with the
64-voice boundary had no transition above 0.0600, matching the natural pluck
attacks. Configuration revision 6 upgrades only the exact revision-5 default
of 24; a user-selected alternative remains unchanged.

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

The smaller preset-16 click reproduction is:

```bash
./.venv/bin/python sc_version/qt_frontend/tests/endurance/sc_endurance.py \
  --cycles 1 --chunk-seconds 30 --scenario strum-click --gui --keep-audio
```

It selects preset 16, taps C on the upper row, explicitly leaves rhythm, bass
and chord accompaniment off, then performs 30 uninterrupted sweeps. Keeping
the WAV makes short discontinuities available for waveform inspection; this
closes the gap left by checks that only detected clipping or long dropouts.

With the 64-voice boundary and 50 ms saturation fade, the same 160-second,
two-cycle overload completed without SC errors, clipping or a long audio
dropout. The deliberately bunched test injector can still create short-lived
releasing nodes, but it no longer exhausts buses or leaves the graph enlarged.
This synthetic pressure is not the steady physical-input load.

The local desktop could not grant realtime priority to Supernova, but its
PipeWire error counter remained unchanged after graph activation during the
successful pressure run. Realtime scheduling remains a host configuration
concern and is not substituted by increasing audio latency here.
