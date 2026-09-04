# Active AMY implementation

`amysynth_version` is the actively maintained LB Omnichord implementation.
Its Qt frontend produces AMY wire commands for either a separate local AMY
service or an ESP32-P4 target.

The repository's Sonic Pi implementation is retained only as historical legacy
material. It is not an alternative backend for this application, is outside the
active design and test contracts, and must not be modified as part of AMY work.
New behavior, fixes, documentation and tests belong under `amysynth_version`.

Start with `design/README.md` for behavioral contracts,
`design/testing.md` for the test/CI structure and `qt_frontend/INSTALL.md` for
installation and launch instructions.

Platform packages are published under the repository's
[GitHub Releases](https://github.com/linuxificator/LB_Omnichord/releases) after
the complete AMY regression matrix passes. Each release contains Linux x86_64
and Raspberry Pi 4/5 aarch64 AppImages, a macOS Apple Silicon DMG and an
experimental native Windows x86_64 zip, plus an experimental Android arm64
APK. Every package contains the Qt frontend and compatible AMY runtime while
preserving their separate-process wire-protocol boundary. Windows uses a
private named pipe; Android embeds the lifecycle AAR and uses its app-private
`amy.sock`; neither target runs the Linux AppImage through a compatibility
layer.

The complete release also publishes a separately attested ESP32-P4 v1 firmware
image for the physically observed revision-1.3 board. It uses the same pinned
Gamma9001 AMY release and wire protocol as the hosted applications, with 11
buses and 1024 sequence groups. The firmware can also be built independently;
see [`esp32p4/README.md`](esp32p4/README.md).

The first four-platform release is `R20260826T230234`: all frontend suites and
all four native package jobs passed before publication. The Windows job proved
offline AMY rendering and the packaged Qt/named-pipe/service boundary. The
Linux x64 package has separate physical UI/audio validation; Raspberry Pi,
macOS and Windows still need physical-device/audio validation, and native
Windows MIDI input and low-latency tuning remain outstanding. Android's gate
adds emulator QML/socket/audio validation but does not replace a physical
touchscreen, route-change, speaker or latency test.
