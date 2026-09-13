# SuperCollider edition testing

Status: authoritative test and package validation contract

Owner: frontend and SC engine

Applies to: `sc_version`

Last verified: 2026-09-14

`qt_frontend/tests/run_tests.py` is the single local and CI runner. Every test
runs as an isolated script and writes an atomic machine-readable report.
Coverage is navigational branch coverage and does not use an arbitrary global
percentage as a quality substitute.

## SuperCollider suites

| Suite | Evidence |
| --- | --- |
| `quality` | compile/JSON/Markdown guards, QML warning ratchet, Ruff and strict-new-module mypy |
| `sc-frontend` | typed protocol, pure plan compiler, client, config, program catalogue, runtime ownership and separate frontend/fake-engine process |
| `sc-compiler` | syntax/core definitions and all pinned SCLOrk source/adapters compile |
| `sc-sequencer` | receiver validation, immutable snapshots, root/finite lifetime, gate overlap, aligned replacement coalescing, same-beat ordering and a real separate `sclang` transaction process |
| `sc-audio` | acid definitions and NRT render audit of every SCLOrk program |
| `sc-banks` | SFZ compiler, complete VSCO manifest shape, loader and GM percussion mapping |
| `sc-packaged` | independent workflow/runtime/package/release contract |
| `platform-input-linux` | a separate controller process drives the real SC frontend through Linux MIDI input and a separate fake engine |

The generic portable MIDI/OSC and discovery process suites remain applicable
because they test frontend boundaries rather than AMY. The visual and
catalogue unit contracts remain applicable unchanged.

## Process separation

Integration senders and receivers are not embedded in production modules.
MIDI/OSC sender, frontend and fake or real engine use distinct processes and
normal production protocols. A unit test may directly exercise one narrow
object, but a package/process claim requires the real process boundary.

`test_supercollider_frontend_process.py` waits for the fake engine to bind
before launching the frontend, then verifies health before sending actions.
Premature process exit includes captured child output in the failure so CI
reports the actual missing library or startup fault rather than a later
connection-refused symptom.

## Legacy characterization

The copied `frontend`, `serial`, `presets`, `native-controls` and
`native-rhythm` suites preserve the established AMY behavior baseline during
migration. Their harness explicitly launches the original
`amysynth_version` frontend as a frozen oracle. Passing them does not mean SC
uses AMY, and they are not part of the independent SC package gate.

The `unit` suite intentionally continues to discover all top-level tests. It
is useful for a full local regression run where the pinned AMY test dependency
is installed. The SC GitHub workflow uses the bounded `sc-frontend` suite so
the package build has no AMY runtime dependency.

## Audio evidence

Compiler success is necessary but does not prove a useful instrument. NRT
tests render without taking a desktop audio device and verify finite,
non-silent output. They are deterministic smoke evidence, not a substitute for
program-specific register/dynamic calibration, tail behavior, long live runs
or physical latency/load acceptance. Those limitations remain explicit in
`../sc/STATUS.md`.

## GitHub workflow

`.github/workflows/supercollider-linux.yml` builds pinned headless
SuperCollider 3.14.1, runs the SC and Linux input suites, constructs the Linux
x86_64 AppImage, verifies its runtime without opening audio and uploads it as a
short-lived artifact. That artifact includes a package checksum, a release
manifest tying the binary to the tested source revision and pinned runtime
inputs, and SPDX 2.3 evidence. The VSCO bank is identified as an external asset
rather than falsely listed as package content. The pinned runtime cache is
keyed by version and build inputs, allowing package-only repairs without
rebuilding SC while invalidating correctly after a runtime recipe change.

An ordinary push or merge never publishes an SC release. Manual dispatch with
`release=true` publishes exactly the tested artifact under an independent
`R<UTC timestamp>-SC` tag. The AMY release workflow also requires its own
explicit release flag; neither engine's build starts or replaces the other.
