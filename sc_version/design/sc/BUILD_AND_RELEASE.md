# SuperCollider build and release

Status: active release contract

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
The frozen package self-check also migrates representative revision-1 and
revision-2 user configurations. This guards the first-launch upgrade path on
Linux, Raspberry Pi, macOS and Windows, including configuration fields added
within an already published revision. It then constructs the production
dependency graph and loads the packaged instrument catalogue, catching layout
differences between source trees and PyInstaller's `_internal` asset root.

## Runtime and samples

Each package contains Qt, the Python application, the SC language/server,
class library and plugins. SC communication remains its native OSC protocol on
loopback. Linux uses the normal host JACK/PipeWire audio-session boundary; no
package starts a competing raw JACK server.

VSCO 2 CE recordings are separate CC0 assets and are not embedded. First
launch uses the bundled Dulwich implementation to clone the verified
`linuxificator/VSCO-2-CE` repository to `~/VSCO-2-CE`. The selected location is
stored in `~/.omnichord/config/supercollider.json`; an alternative directory is
accepted only if its Git origin identifies the required repository. No system
Git executable is required.

The Raspberry Pi package does not install scheduler policy, isolate CPUs or
change machine configuration.
