# SuperCollider build and release

Status: active release contract
Owner: SuperCollider package and release workflow
Applies to: `sc_version`
Last verified: 2026-09-15

The SuperCollider edition is the only actively released LB Omnichord edition.
The AMY and Sonic Pi trees remain available as historical source archives.
Android and ESP32-P4 are not part of this release.

## Continuous verification

An ordinary push to `main` or the active release-integration branch runs the
SuperCollider tests on Linux x86_64, Raspberry Pi aarch64, macOS arm64 and
Windows x86_64. It neither constructs release packages nor publishes a GitHub
release. This is intentionally the safe default.

## Explicit release

Run the `Test and release SuperCollider edition` workflow manually with
`release=true`. Only after all four platform test jobs pass does it create:

- Linux x86_64 AppImage;
- Raspberry Pi aarch64 AppImage;
- macOS arm64 DMG;
- Windows x86_64 ZIP.

The workflow verifies SuperCollider 3.14.1 archives by SHA-256, validates the
runtime in each package without opening an audio device, records a package
content audit and checksum, and publishes the complete set under one
`R<UTC timestamp>-SC` tag. A partial platform failure prevents publication.
The frozen package self-check seeds a completely empty user directory and
migrates every supported configuration revision. This guards clean first
launch and the upgrade path on Linux, Raspberry Pi, macOS and Windows,
including configuration fields added within an already published revision. It
validates the copied frontend config against the immutable schema at its real
packaged asset path; validating only the shipped config is insufficient. It
then constructs the production
dependency graph and loads the packaged instrument catalogue, catching layout
differences between source trees and PyInstaller's `_internal` asset root.
Finally it executes the packaged bootstrap through the packaged `sclang` up to
the no-audio validation boundary. This checks the real class library,
executable selection and SC API before a release can be published; checking
only that `sclang -v` starts is not an adequate runtime test. All targets must
contain and identify `supernova`; `scsynth` remains packaged for deterministic
non-realtime tooling but is not the production audio server.
Packaged `sclang` runs in its native standalone mode with one explicit private
class-library tree. A remembered build prefix or a user's SC extensions can
therefore neither duplicate nor alter the released engine.

## Runtime and samples

Each package contains Qt, the Python application, the SC language/server,
class library and plugins. SC communication remains its native OSC protocol on
loopback. Linux uses the normal host JACK/PipeWire audio-session boundary; no
package starts a competing raw JACK server.

VSCO 2 CE recordings are separate CC0 assets and are not embedded. First
launch uses the bundled Dulwich implementation to shallow-clone the pinned
`lb-omnichord-runtime-v1` branch of `linuxificator/VSCO-2-CE` to the location
selected in `~/.omnichord/config/supercollider.json` (default
`~/VSCO-2-CE`). This branch contains only source audio reachable from a
playable SFZ region or the direct PCM-drum catalogue, plus the source licence
and readmes. An existing checkout or ordinary copy is accepted when all those
required audio files match the bundled manifests.

Successful validation atomically writes `lb-omnichord-samples.json` inside
the sample directory. It records the exact repository branch and commit,
selection-manifest digest and complete relative-path/SHA-256 list. Every
startup checks this receipt and a stat-based inventory; unchanged recordings
do not need to be rehashed, while a missing or changed receipt forces full
content validation and receipt repair. No system Git executable is required.

The Raspberry Pi package does not install scheduler policy, isolate CPUs or
change machine configuration.
