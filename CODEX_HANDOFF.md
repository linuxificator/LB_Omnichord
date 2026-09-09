# Current work handoff

Updated: 2026-09-09

- Active branch: `bass_refresh`, based on `main` at `8fef088`.
- The ranked, C-normalized bass catalogue is implemented without TB-303
  behavior. APG/LDR pitch-pool selection, fixed riff ranks and running-pattern
  continuity are covered by unit, integration and sequencer-capacity tests.
- The reported MIDI regressions are repaired: complete GM percussion mapping,
  endpoint-only CC pushbutton detection, clock-only traffic suppression and
  factory channels `2,3,4,5,6,10` with chord input on channel 1.
- AMY `5e3cd57` fixes disabled shared-reverb returns leaking a second dry path.
  The full local `tests/run_tests.py --suite all` matrix passed on this branch.
- Rejected P4 prototypes are preserved on the non-production branch
  `diagnostics/esp32p4-rejected-prototypes`; never merge it into production.
- Released baseline: LB `R20260907T231243` (`c191e65`). The active development
  pin is AMY `releases/amy_omnichord_R20260909T140940` (`5e3cd57`).
- The complete release matrix passed. The Pi AppImage was physically accepted
  on a 2 GiB Pi 4 with bundled AMY and with serial ESP32-P4.

Resume through `amysynth_version/design/README.md`. It routes to the current
contracts and open work; Git history is the archive for removed handovers.
