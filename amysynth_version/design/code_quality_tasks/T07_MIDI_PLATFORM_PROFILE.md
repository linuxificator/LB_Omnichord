# T07 result: portable MIDI platform-profile selection

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: MIDI input/player subsystem
Applicability: all desktop, Raspberry Pi and Android packages

## Outcome

- Changed the common shipped `midi_input.tech_profile` from `linux` to
  `auto`. The same configuration can now be packaged on every target without
  forcing Linux MIDI probes or Linux capability indicators.
- Added a small, strict-mypy-clean `midi_platform_profile` adapter module.
  Its pure resolver accepts configured override, Qt QPA name and Python
  runtime platform; the runtime wrapper is the only production location that
  reads `sys.platform`.
- Preserved a non-`auto` value as an explicit diagnostic/test override. It is
  no longer described as an ordinary release setting.
- Preserved the existing capability model and labels exactly: Linux presents
  ALSA raw, ALSA seq and OSS MIDI; macOS presents unavailable CoreMIDI;
  Windows unavailable WinMM; Android unavailable Android MIDI; unsupported
  runtimes present no irrelevant technology.
- Added real shipped-config tests for Linux, macOS, Windows, Android and an
  unsupported runtime, plus tests proving override precedence.
- Updated the authoritative MIDI contract.

## Platform-code boundary

An existing source-string test rejected every operating-system selection in
every production module. That contradicted the later clarified architecture
rule: portable application code is identical, while platform-dependent work
belongs in explicit adapter modules. The test now excludes only adapters
declared by the structured quality policy, while continuing to reject direct
OS branches in all portable Python and QML files.

The quality policy permits direct platform selection only in
`midi_platform_profile.py`. New platform access elsewhere still fails the AST
quality gate.

## Verification

- MIDI engine/profile tests: 27 passed
- T06 refactor characterization: 6 passed
- Android packaging contracts: 9 passed
- static architecture contracts: 36 passed
- complete unit suite: passed
- quality gate: passed; the new production module passes strict mypy
- `git diff --check`

## Findings and progressive insight

- Qt QPA names identify a display/backend and are sufficient for the packaged
  macOS, Windows and Android cases. `sys.platform` remains a necessary fallback
  for headless/offscreen execution and for distinguishing unsupported Unix
  systems from Linux. Keeping both inputs in one pure resolver makes that rule
  directly testable.
- XCB, Wayland, EGLFS and Linux framebuffer map to Linux only after a supported
  Python runtime did not already identify macOS, Windows or Android. This
  prevents a headless/atypical Qt backend from overriding a known package OS.
- T13 should move the concrete readers and capability descriptions behind the
  same adapter boundary. It should retain this resolver rather than introduce
  another platform-selection authority.
- CoreMIDI, WinMM and Android MIDI remain explicitly unavailable. This task
  fixes selection and presentation; it does not claim new native MIDI support.

## Follow-up task effects

No extra queue item is needed. T13 now has a proven adapter-selection seam and
must add shared adapter lifecycle/event contract tests without changing these
profile results.
