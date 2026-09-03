# Post-T25 result: first slimmed main release and release-boundary fixes

Status: complete
Recorded: 2026-09-02
Branch: `rework/code_quality`
Owner: merge-to-main validation, transport timing proof and release staging

## Outcome

The complete T01-T25 and package-slimming work was merged to `main` in
`71883ea` (`Merge code quality and package slimming rework`). The first two
main runs correctly stopped on defects that a non-publishing branch run could
not fully expose. Both defects were fixed without weakening a product gate:

- `b975e05` (`Make allocation guard timing test deterministic`) moved the
  synth-allocation timing proof to the boundaries that actually own it;
- `3740191` (`Separate release packages from build evidence`) separated exact
  publishable files from diagnostic CI evidence.

Final workflow run `33560667071` passed all seven regression suites, all five
release packages, both Android architectures, the packaged Android
QML/socket/AMY/Oboe emulator gate, exact release-manifest validation, SPDX SBOM
generation, provenance/SBOM signing and independent attestation verification.

Release `R20260901T212205` targets immutable source commit `3740191` and AMY
release branch `releases/amy_omnichord_R20260901T201533` at commit
`7c34aa514f10c33f02692f735166d65f4e20374a`, using the Gamma9001 PCM bank.
Screenshot follow-up `6ccebe9` contains only `README.md` and the release-tagged
OMNI/MIDI PNG pair. Its `skip-rebuild` plus `skip-checks:true` trailers
prevented a release loop as intended.

## Incident 1: PTY receive time is not physical write time

Initial main run `33557814378` failed only `tests / serial`. The cold-start
test observed the first synth-4 post-allocation command about 27 microseconds
after the allocation command even though the product scheduler had enqueued
and executed the configured 10 ms guard.

The test timestamped decoded lines in a separate PTY reader thread. Linux may
deschedule that reader while the writer performs two writes with a sleep
between them, then return both buffered writes in one later read. Assigning
timestamps while decoding that batch therefore measures observer scheduling,
not physical sink-write separation.

The corrected proof has two complementary layers:

1. the real serial integration test checks that the startup transport log
   orders synth-4 allocation, `GUARD sleep 10.0 ms`, then the next synth-4
   command;
2. the scheduler characterization test timestamps calls at the injected byte
   sink and proves that a queued guard separates the two physical writes.

The obsolete PTY line-timestamp helper was removed. No product transport,
guard duration, musical behavior or AMY command changed. The targeted
integration test passed ten consecutive local runs, the full local unit and
serial suites passed, quality passed, and the hosted serial suite passed in
both later main runs.

The separate ESP32-P4 workflow for merge commit `71883ea`, run `33557814140`,
also passed. Later documentation/workflow-only fixes did not touch its path and
therefore correctly did not rebuild firmware.

## Incident 2: exact release staging must exclude diagnostic evidence

Second main run `33558530899` passed every regression, package and Android
emulator gate, then stopped in `publish-release`. The publisher downloaded
`package-*` Actions artifacts that contained the expected five packages and
five checksums but also package-audit, QML-import and Android-wheel-pruning
JSON. The exact-set validator correctly rejected those ten extra files.

The validator was deliberately not given ignore rules. Instead, every
platform job now uploads:

- `package-*`: only the package and its canonical checksum, retained for two
  days as release staging;
- `evidence-*`: package audit plus QML-import or Android pruning evidence,
  retained for 14 days as run diagnostics.

The x86 Android emulator package remains a non-publishing package artifact and
has its own evidence artifact. The publisher downloads only `package-*`, so
the exact five-package contract is structural rather than filename-filtered.
A workflow contract test proves that package upload steps contain no evidence
patterns and that the publisher never downloads `evidence-*`.

Final run `33560667071` retained these separate evidence artifacts:

- `evidence-Linux-x86_64`;
- `evidence-RaspberryPi-aarch64`;
- `evidence-macOS-arm64`;
- `evidence-Windows-x86_64`;
- `evidence-package-Android-arm64`;
- `evidence-android-emulator-x86_64`.

## Published package evidence

| Platform | Published bytes |
| --- | ---: |
| Android arm64 APK | 65,622,671 |
| Linux x86_64 AppImage | 98,896,376 |
| Raspberry Pi aarch64 AppImage | 92,441,096 |
| macOS arm64 DMG | 54,529,408 |
| Windows x86_64 zip | 57,751,423 |

The GitHub Release contains exactly 14 assets: five packages, five checksum
files, `release-manifest.json`, the SPDX document and two retained Sigstore
bundles. Package-audit evidence remains attached to the workflow run rather
than silently broadening the public release asset contract.

## Lessons learned and future rules

- A non-publishing manual all-platform run is strong package validation, but
  it cannot prove a `main`-only publish or screenshot job. Describe it as
  package validation, never as a complete release rehearsal.
- Observe timing at the boundary that owns the timing. Consumer/read timestamps
  are valid for receipt behavior, not for proving producer/write separation
  across kernel buffering and thread scheduling.
- Keep strict validators strict. When diagnostic evidence and release files
  have different ownership and retention, separate their staging namespaces
  instead of teaching the release validator to ignore extras.
- An Actions artifact name is an API boundary. `package-*` means publishable
  package material only; `evidence-*` means non-publishing diagnostic proof.
- If a fix changes workflow structure or artifact contents, rerunning the old
  failed workflow is insufficient: it checks out the old workflow and reuses
  the old artifact contract. A new commit/run is required.
- After a successful release, verify more than the top-level green result:
  inspect the release target SHA, exact asset names, AMY branch/SHA in release
  notes, evidence-artifact presence and the screenshot-only follow-up commit.
- Keep product corrections separate from test-observability corrections. The
  PTY incident required a better test, not a larger delay or transport change.
- Production signing remains a separate distribution/key-ownership decision.
  This release intentionally preserves the documented ad-hoc macOS and debug
  Android signing boundaries.

## Branch state after handoff

After release validation, `main`, `origin/main`, `rework/code_quality` and
`origin/rework/code_quality` were aligned at `6ccebe9`. This handover is the
first documentation-only continuation commit on the retained rework branch;
it is not part of release `R20260901T212205` and must not be merged to `main`
merely to update historical release notes.
