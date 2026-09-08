# Rejected ESP32-P4 reverb prototypes

Status: diagnostic branch only; superseded and intentionally not production-ready
Branch: `diagnostics/esp32p4-rejected-prototypes`
Recorded: 2026-09-08

This branch preserves the final uncommitted prototype state from the physical
ESP32-P4 reverb investigation. It exists only so the experiments remain easy
to inspect without leaving a dirty working tree.

The prototype combines several independently rejected or superseded ideas:

- a PIE/SIMD Hadamard microbenchmark;
- split early/feedback reverb placement across SRAM and PSRAM;
- an obsolete `max_reverb_groups` AMY interface;
- the obsolete 2 x 64-frame DMA configuration;
- source preparation against an older AMY branch.

Do not merge or release this branch. The production implementation is on
`main` and uses two shared reverb rooms in complete, exclusive 128 KiB SRAM
banks, 2 x 128 DMA frames and the immutable AMY release selected by
`qt_frontend/packaging/release_inputs.json`. The measured conclusions are
consolidated in the active design documentation on
`rework/cleanup_and_details`.

