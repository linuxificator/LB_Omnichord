# Current backlog

Status: active backlog; not implementation authorization
Owner: application architecture
Last verified: 2026-09-08

## Technical work

1. Surface transport failure/recovery state through one application boundary.
2. Continue cohesive extraction from `InstrumentBackend`.
3. Separate MIDI performance/note ownership from its Qt view model.
4. Separate AMY runtime selection state from command submission.
5. Tighten typed ports after those boundaries stabilize.
6. Continue QML section/facade and accessibility work.
7. Replace remaining implementation-location tests with semantic tests.
8. Publish one structured platform-capability authority.
9. Generate the Gamma9001 mapping deterministically from the pinned AMY input.
10. Deepen captured dependency/toolchain hashes without claiming reproducible
    builds until rebuild comparison proves it.
11. Add maintained CoreMIDI, WinMM and Android MIDI adapters if product scope
    requires them.
12. Physically validate the ESP32-P4 v3 profile on revision-3 hardware.
13. Capture physical ESP32-P4 output across the full instrument catalogue.

## Product, evidence and governance decisions

- Decide live-parameter behavior for already sounding notes.
- Decide voice priority when MIDI preview and external input fill one row.
- Audit catalogue authorship/licence provenance; do not infer legal approval.
- Decide compatibility/deprecation policy before removing public loaders.
- Define distribution trust/key ownership before production signing.
- Decide whether mutation testing provides enough value to add a dependency.

