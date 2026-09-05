# Codex handover: AMY integration release 2026-09-05

Status: locally built, fully integrated and pushed; hosted platform CI remains
the next release gate
Recorded: 2026-09-05
AMY PR branch: `rework/sequencer`
AMY PR source: `3872b4be16af4f486c8f3259d44478ee7174864f`
AMY release branch: `releases/amy_omnichord_R20260905T104903`
AMY release commit: `11f0c39fe8350e7a32b9a1c7b1114f4a7806d795`
LB branch: `rework/sequencer`
LB pin commit: `1327f4c`

## Purpose and construction

The preceding immutable release stopped at AMY commit `8a896e93`. It contained
the first named start/stop/gate API but not the subsequent concurrency,
rollover, capacity, compatibility and Windows portability corrections now in
PR 1151. This release was therefore reconstructed from the current clean PR
head rather than extending or merging the preceding release history.

The release branch starts exactly at `3872b4be`. It then layers only the
maintained fork integrations:

- Android Oboe service and private Unix-socket transport;
- socket backpressure protection;
- selectable hosted PCM bank and the Gamma9001 build/registration path;
- deterministic `amy.live(audio=False, ...)` host rendering;
- configurable embedded audio geometry and ESP-IDF task signatures;
- 336 oscillators, 11 existing generic AMY buses, 1,280 sequence tags, 64
  events per sequence and 40 active or alignment-pending executions; and
- a release-facing contract which describes the current reusable-sequence
  model rather than the abandoned pattern/group APIs.

The abandoned fork bus-mixer module is absent. Eleven buses is a runtime
capacity choice for AMY's existing generic bus implementation, not another
mixer or routing API. No Codex file or Omnichord musical policy was added to
either the Shorepine-facing branch or the AMY release branch.

## Diagnostic AMY commits

- `63f5c593` — merge maintained Android and socket integration onto the PR
  head, retaining both current sequence docs and the transport guide;
- `30ca2d6e` — retain downstream Android packaging lessons;
- `c58f1511` — restore the selectable CPython PCM-bank build;
- `e082aa13` — restore deterministic offline host configuration;
- `553af87a` — build the Gamma9001 Android/service profile;
- `55f7d1e9` — register its PCM blob before AMY starts;
- `d2cdf6a8` — retain socket receiver backpressure handling;
- `6edcc75e` — retain configurable block/sample/DMA geometry while preserving
  the new sequence-specific C test recipes;
- `41f2753b` — retain correct ESP-IDF task entry signatures;
- `166a63d5` — apply the current sequence-capacity names and hosted sizes; and
- `11f0c39f` — replace stale group-era release documentation.

This trail is intentionally fine-grained. A future regression can be bisected
between the generic PR source and each downstream integration without treating
the release as an opaque merge of old experimental histories.

## Consumer and local runtime

`qt_frontend/packaging/release_inputs.json` is the single machine authority for
the new branch, SHA and `gamma9001` bank. Active Linux, Android, Windows and
dependency documentation records the same provenance for people. Historical
handover references to `8a896e93` remain historical and must not be treated as
the current build input.

The detached checkout at `/home/jeroen/omnichord/amyfork/amy` was moved to
`11f0c39f`. `qt_frontend/prepare_local_amy.sh` rebuilt and force-installed
`c_amy` into `/home/jeroen/omnichord/omnichord-env` from that exact checkout
with Gamma9001. Consequently `run_local.sh` now loads this release; it does not
silently rebuild AMY when the application starts.

No Omnichord wire-command change was needed. Existing cumulative definition,
reset and start/stop/gate commands remain compatible with the final PR code,
so no caller-side sequence, clock, timing or note state was introduced.

## Validation evidence

Completed successfully on the AMY release source:

- complete `make ctest -j2`, including reusable sequences, concurrency, OOM,
  clock rollover, bus behavior and configurable build geometry;
- `tests/test_sequence_api.py`;
- the complete 133-test AMY audio/regression suite with the CI threshold
  `AMY_TEST_THRESHOLD_DB=-70.0`;
- `make check-c-api`, covering generated C, Python, JavaScript and PCM data;
- Android service contract: Gamma9001, separate private service, 336
  oscillators, 11 buses and 1,280 sequence tags;
- PCM-bank build contract;
- the newly installed Gamma9001 extension's deterministic offline-render test.

Completed successfully on LB Omnichord against the installed and pinned AMY
SHA:

- `tests/run_tests.py --suite all`;
- all quality and architecture guardrails;
- all unit suites;
- separate-process portable input and Linux physical-input contracts;
- frontend, serial, presets, native-control and native-rhythm integrations;
- explicit release-input verification reporting AMY `11f0c39f`.

The standalone ASan/UBSan Unix-socket executable could compile but the managed
sandbox refused creation of its pathname socket. This is an execution-
environment restriction: LB's local AMY service socket tests passed, including
real service startup on temporary Unix sockets. The standalone sanitizer test
and Android/macOS/Windows/Raspberry Pi packaging remain hosted CI gates.

`appimagetool` is not installed locally, so the final AppImage wrapper was not
assembled here. PyInstaller/package construction and all five target packages
must be exercised by the normal GitHub workflow before publishing a release.

## Hosted integration findings

Non-publishing five-platform run `33956845291` compiled the newly pinned AMY
release. Its shared test jobs and Linux, Raspberry Pi and macOS package jobs
passed. The first Windows attempt found that `packaging/windows/amy_service.c`
still initialized the three retired group-capacity members of `amy_config_t`.
This was a caller integration defect, not a defect in AMY's reusable-sequence
implementation.

LB commit `e2a8bc5` changes the service to `max_sequencer_tags`,
`max_sequence_events` and `max_sequence_executions`, using the same
`1280/64/40` profile as the authoritative JSON and Android service. Its
packaging contract now derives the expected literals from that JSON and
forbids the retired member names.

The same audit found pre-group `max_pattern*` members in the separately built
ESP32-P4 application. LB commit `67e49b3` migrates those to the current fields
and extends the immutable-release static contract. This is a source/build
compatibility correction only; physical ESP32-P4 real-time validation remains
open. A focused Windows smoke build was started from that commit before the
next complete package run, preserving the project's partial-rerun workflow.

## Continuation

1. Require the focused Windows smoke build to pass, then perform one final
   complete non-publishing platform run from the repaired LB commit.
2. Require the standalone Unix-socket sanitizer job and all platform package
   jobs to pass.
3. Perform the separate physical ESP32-P4 timing, DMA and memory validation;
   hosted success does not prove that hardware deadline.
4. If any AMY release fix is needed, commit it separately on the release
   branch, update the single manifest SHA, reinstall AMY and rerun the affected
   tests followed by the full suite.
