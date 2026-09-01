# Post-T25: restore the Gamma9001 release lineage

Status: implemented release-profile correction
Owner: LB Omnichord configuration and AMY release integration
Applies to: `rework/code_quality` and the next hosted-platform release
Recorded: 2026-09-01

## Finding

The intended product line used Gamma9001, and `features/gamma9001` implemented
that profile in commit `0026f4989743654eb2d571b7bd5e71b40fdfa9d5`.
Repository history proves that this branch was not merged into `main`.
Published main tags from `R20260830T224834` through `R20260831T210652`
therefore still selected `AMY_PCM_BANK=tiny` and shipped a Tiny sample map.

This distinction matters because a Gamma9001 sample map sent to a Tiny AMY
binary does not fail structurally: the same preset numbers select unrelated
sounds. The observed symptom was every drum role becoming a similar sweeping
timbre while bass and chords remained correct. Source configuration, exact AMY
pin, compiled PCM symbols and package workflow must consequently be checked as
one invariant; inspecting only one of them is insufficient.

## Correction

Hosted targets now pin AMY fork branch
`releases/amy_omnichord_R20260901T201533` at exact commit
`7c34aa514f10c33f02692f735166d65f4e20374a`. This release is based on the
preceding Omnichord release, incorporates Shorepine AMY 1.2.163 (including the
upstream drum oscillator-count repair), and contains the Gamma9001 host and
Android registration work.

Configuration revision 5 makes Gamma9001 the shipped authority. Its migration:

- replaces only the exact Tiny map published by revision 4;
- preserves existing Gamma9001 and General MIDI selections;
- rejects a customized Tiny map instead of silently overwriting user data;
- leaves all non-drum configuration untouched and retains the atomic
  `.previous` rollback copy.

The versioned Tiny and Gamma maps in `config_migrations.py` are historical
migration fixtures, not runtime defaults. Runtime synthesis continues to use
only the resolved typed configuration.

## Platform boundary

Linux, Raspberry Pi, macOS, Windows and Android are hosted targets and must all
prove Gamma9001. ESP32-P4 remains a separately declared Tiny-bank firmware
target until a Gamma9001 flash/storage layout is designed and tested. Its
constraint must not cause hosted package workflows or user configuration to
fall back to Tiny.

## Regression contract

The release pipeline must fail when any of these disagree:

1. `packaging/release_inputs.json` says `pcm_bank: gamma9001`;
2. shipped configuration says `drums.kit: gamma9001` and uses its exact map;
3. Python/native artifacts export `amy_set_gamma9001_pcm` and
   `gamma9001_pcm_data`;
4. Windows generates, links and registers `drums_bin.c` before `amy_start()`;
5. Android obtains the same registration from the pinned AMY AAR;
6. the acoustic drum smoke covers every Gamma realization used by the
   catalogue.

This release correction is intentionally split from the platform-build commit
so Git history remains a useful diagnostic boundary.

## Verification completed

The pinned AMY release passed its C tests, Android service contract, PCM-bank
build contract, offline Python render and Unix-socket integration. In the LB
branch, `tests/drum_kit_audio_smoke.py gamma9001` rendered all 62 distinct
catalogue realizations non-silent. `tests/run_tests.py --suite all` then passed
the quality gate, every unit/frontend/serial/preset suite and both native AMY
suites against exact AMY commit
`7c34aa514f10c33f02692f735166d65f4e20374a`.

The full upstream `amy.test` numerical golden suite was also attempted locally.
Its Gamma-specific PCM checks passed, but that compiler/Python environment
still reported 43 very-low-level legacy golden deviations (mostly -95 to
-99 dB). This is recorded rather than being misrepresented as a clean full
AMY golden run; the release integration gates named above are the passing
evidence used here.
