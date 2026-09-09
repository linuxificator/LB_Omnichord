# ESP32-P4 release and physical acceptance

Status: authoritative release integration record
Owner: ESP32-P4 packaging
Last verified: 2026-09-08

The normal LB release publishes one versioned ESP32-P4 ZIP containing separate
`v1/` and `v3/` images, checksums, build metadata and flashers for esptool 4
underscore syntax and esptool 5 hyphen syntax.

- `v1` targets revisions 1.0-1.99 and is physically validated on revision 1.3.
- `v3` targets revision 3.x and is compile/package tested only.

Never force a v3 image onto v1 silicon; that was reproduced as an illegal-
instruction boot loop. Current firmware uses Gamma9001, 336 oscillators, 11
buses, the sequence capacities listed in `performance.md`, two shared SRAM
reverbs and 2 x 128 DMA frames.

Release `R20260907T231243` was built from LB commit `c191e651` with AMY commit
`5e3cd575` on `releases/amy_omnichord_R20260909T140940`. Every platform job,
Android emulator and both P4 profiles passed. The published Pi AppImage and P4
v1 image were then physically tested together:

- esptool 5.3.1 detected the connected chip as revision 1.3 and verified every
  flashed segment;
- the 2 GiB Pi 4 ran both bundled-AMY and `/dev/serial0` modes on Wayland/V3D
  at 120 Hz;
- both modes captured valid 1920 x 850 OMNI and MIDI screens;
- a UART-triggered P4 snapshot after the packaged serial run reported 126,175
  blocks, maximum total 1,959 us, zero misses/debt/yields and valid SRAM arenas.

Local esptool 4.7 identified this early P4 incorrectly as revision 0.0 and
refused the image before writing. The current esptool-5 path is therefore the
physically validated release route.
