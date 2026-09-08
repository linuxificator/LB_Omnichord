# ESP32-P4 design

Status: authoritative category index
Owner: ESP32-P4 firmware integration
Last verified: 2026-09-08

- `performance.md` records the current reverb architecture, timing fix,
  measured capacity envelope and rejected optimization paths.
- `release.md` records firmware profiles, packaging and physical acceptance.
- `../../esp32p4/README.md` owns build settings, wiring and commands.
- `../../esp32p4/CI_FLASH.md` owns standalone artifact flashing.

The firmware remains a separate AMY wire-command target. Omnichord musical
policy never moves into the firmware.

