# Platform and packaging design

Status: authoritative category index
Owner: platform integration
Applies to: `sc_version`
Last verified: 2026-09-15

Supported packages are Linux x86_64 AppImage, Raspberry Pi aarch64 AppImage,
macOS arm64 DMG and Windows x86_64 ZIP. They share the same Python/QML and typed
SC protocol. Platform differences are limited to runtime discovery, native
input capability, audio-session integration and package layout.

Android and ESP32-P4 are not SC release targets. The Android feasibility audit
and its explicit stop decision are in
[`android/supercollider_feasibility.md`](android/supercollider_feasibility.md).
See also `packaging.md` and
[`../sc/BUILD_AND_RELEASE.md`](../sc/BUILD_AND_RELEASE.md).
