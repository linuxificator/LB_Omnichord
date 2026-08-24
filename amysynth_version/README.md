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

Desktop packages are published under the repository's
[GitHub Releases](https://github.com/linuxificator/LB_Omnichord/releases) after
the complete AMY regression matrix passes. Each release contains Linux x86_64
and Raspberry Pi 4/5 aarch64 AppImages plus a macOS Apple Silicon DMG. Every
package contains the Qt frontend and compatible AMY runtime while preserving
their separate-process wire-protocol boundary.
