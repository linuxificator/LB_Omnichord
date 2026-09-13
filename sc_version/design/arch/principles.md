# SuperCollider edition design principles

Status: authoritative baseline contract

Owner: application architecture

Applies to: `sc_version`

Last verified: 2026-09-14

## Engine boundary

The Qt process does not synthesize audio, own the musical clock, or import an
audio-engine implementation. It produces validated immutable plans and typed
live actions. A versioned OSC adapter transports them to a separately
supervised headless `sclang` process; `scsynth` is a child of that engine
process.

```text
Qt -> application policy -> typed plan/action -> loopback OSC
   -> sclang coordinator and clock -> scsynth audio graph
```

The internal protocol contains musical meaning, not AMY wire strings and not
raw scsynth node IDs. The UI-facing semantic API remains stable while the
engine adapter changes.

## Explicit ownership

Python owns UI state, MIDI/OSC input, catalogue selection, presets and pure
plan compilation. `sclang` owns sequence phase, quantization, immutable
definition snapshots, execution state, note handles, musical gates and timed
releases. `scsynth` owns audio nodes, buffers, buses and effects.

Manual chord, automatic chord, strum, bass, drum and MIDI voices have distinct
owners even where they share an audio bus. A release addresses the original
handle; pitch lookup and broad all-notes-off operations are not substitutes.

## No frontend musical timing

Python never polls sequence phase, follows beats or schedules musical note
events. UI timers may classify gestures and animate presentation. Seconds-
based performance tails are delegated to the engine once they affect note
lifetime. Beat-based work stays on one SuperCollider `TempoClock`.

## Behavioral preservation

Screen changes do not change sound. OMNI and MIDI preset ownership remains
separate. Running preset/rhythm changes preserve the established live state
and transport continuity. Catalogue data is not rewritten merely to make an
engine migration easier.

Legacy AMY tests may remain as explicit characterization oracles during the
migration. They do not authorize importing AMY into the SC production graph or
shipping AMY in the SC package.

## Platform scope

Platform-specific discovery, process and package behavior lives in named
adapters. The current supported SC target is Linux x86_64. Do not infer SC
support for Raspberry Pi, macOS, Windows, Android or ESP32-P4 from the AMY
edition's support for those targets.

On Linux, use the distribution's audio-session mechanism. A PipeWire desktop
uses its JACK compatibility wrapper; application code must not secretly start
a competing raw JACK server.

## Simplicity and native mechanisms

Use native SuperCollider concepts—`TempoClock`, server groups, buses,
SynthDefs and immutable application records—before inventing parallel clocks,
mixers or lifetime systems. Add an abstraction only when it reduces coupling,
makes ownership explicit or prevents a demonstrated regression.

Do not headbang: repeated repairs to a growing custom mechanism are evidence
to revisit the design and established platform/framework solution, not a
reason to add another compensating layer.

## Code-quality non-regression

Portable application logic contains no operating-system branches, packaging
drivers, synthetic inputs or integration-test receivers. External-input and
process tests use separate processes across production boundaries. Generic
tests are shared; unavoidable platform capability setup is isolated in a
named platform adapter.

Current executable tests, validated configuration and typed records outrank
historical Git prose. Any intentional behavior change needs an executable
contract and an updated owning design document.
