# SuperCollider edition design principles

Status: authoritative baseline contract
Owner: application architecture
Applies to: `sc_version`
Last verified: 2026-09-15

## Boundaries and ownership

Qt/Python owns presentation, user interaction, external MIDI/OSC input,
catalogue choice, presets and pure immutable plan compilation. `sclang` owns
musical time, quantization, executions, gates, voice handles and timed release.
`scsynth` owns audio nodes, buffers, buses and effects. Communication crosses a
typed, versioned OSC protocol over loopback; UI code never manipulates engine
nodes or schedules musical events.

Manual chord, automatic chord, strum, bass, drum and MIDI voices have explicit
owners. Releases target the original handle. A broad all-notes-off is recovery,
not normal lifetime management.

## One active engine

The production SC graph imports and packages no AMY runtime, wire transport,
firmware builder or AMY capacity/configuration model. Compatibility with old
program selections is data migration through a checked-in alias table, not a
second engine path. Historical implementation material belongs in Git history
or the separate edition.

## Platform independence

Portable application and musical logic contain no platform branches.
Discovery, native input and runtime location live in named adapters selected at
the composition root. The supported package targets are Linux x86_64,
Raspberry Pi aarch64, macOS arm64 and Windows x86_64. Android and ESP32 are not
SC edition targets.

## Native mechanisms and simplicity

Prefer established Qt, operating-system and SuperCollider mechanisms over
custom schedulers, mixers, process watchers or gesture interpreters. Add an
abstraction only when it reduces coupling, makes ownership explicit or
prevents a demonstrated regression. Do not headbang: repeated repairs to a
growing custom mechanism are a signal to revisit the premise and use the
standard mechanism.

Current executable tests and validated configuration outrank historical notes.
Every intentional behavior change needs a focused regression test and an
update to its owning contract.
