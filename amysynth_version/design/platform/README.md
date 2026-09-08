# Platform and packaging design

Status: authoritative category index
Owner: platform integration
Last verified: 2026-09-08

- [`linux/`](linux/README.md): native Linux process and MIDI boundaries.
- [`raspberry_pi/`](raspberry_pi/README.md): source checkout, AppImage graphics
  and serial/service modes.
- [`windows/`](windows/README.md): native package and named-pipe boundary.
- [`android/`](android/README.md): Qt package, app-private socket and Oboe service.
- [`macos/`](macos/README.md): native arm64 package boundary.
- [`packaging.md`](packaging.md): shared release, size and provenance rules.

Detailed executable instructions remain next to their implementation under
`../../qt_frontend/` and `../../esp32p4/`; these platform pages state the
cross-cutting contracts and route to those instructions.
