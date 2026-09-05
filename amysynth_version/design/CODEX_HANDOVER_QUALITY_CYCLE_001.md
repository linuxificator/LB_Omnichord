# Codex handover: quality cycle 001

Status: completed branch-local audit and necessary corrections
Owner: application architecture and code-quality guardrails
Applies to: `rework/quality_cycle_001`, based on `main` at `d4ae1ed`
Last verified: 2026-09-05

## Objective

Re-audit the active AMY Omnichord implementation after the sequencer,
external-control, test-separation, release-packaging and migraine-visual work.
The cycle checks whether those additions weakened the established architecture
or left a concrete correctness/maintenance defect. It is not authority for an
unbounded rewrite and does not change musical, QML interaction, AMY wire or
platform behavior.

The frozen Sonic Pi tree and the AMY fork implementation are outside this
cycle. AMY is inspected only at the already-declared dependency and wire
boundary.

## Material read and checks

The audit used the authoritative baseline contracts, prior repository-wide
audit, post-T25 queue, platform-adapter contract and production/test process
contract. It then inspected current Python/QML size, platform access, third-
party imports, queue/timer ownership, broad exception boundaries, type output,
Pyflakes output, configuration literals and release/ESP32 profile references.

Executed evidence before the final verification pass:

- the repository quality gate passed at the branch base with 35 of 42 legacy
  mypy errors still present;
- all 47 automatically discovered unit scripts passed at the branch base;
- architecture, composition, static-contract and quality-guardrail tests
  passed independently;
- a requested local coverage run could not start because the existing local
  virtual environment does not contain the declared `coverage==7.15.4` test
  dependency. The dependency is correctly declared and release CI installs
  the test requirements. Nothing was installed during this cycle because the
  user required work that needs no additional authorization.

## Architecture assessment

The principal architecture remains intact:

- the Qt frontend is still a wire-only AMY client;
- Linux/macOS, Windows, Android and ESP32-P4 retain their declared socket,
  named-pipe, app-private socket and serial boundaries;
- platform decisions remain in the composition/adapter set rather than
  musical policy or QML;
- shipped configuration is schema-validated and resolved before resource
  construction;
- rhythm/arpeggio/fill timing and sequence execution remain in AMY while LB
  owns musical selection policy;
- MIDI and OSC input events retain their queued Qt boundary and shared binding
  state;
- integration/package stimulus and assertions remain outside production code;
- command, logging and application-delay queues remain bounded;
- release inputs, package evidence, SBOM and provenance remain separately
  declared and tested.

No new import cycle, AMY import in the Qt frontend, production test driver,
platform branch in portable application code, unbounded timer-per-event path,
or duplicated runtime drum-data tree was found.

## Necessary corrections made

### Q001-1 — restore one ESP32-P4 audio authority

`AGENTS.md` still called the old 48 kHz / 64-sample / 2x32-DMA setup the proven
baseline. The firmware build inputs, firmware contract, ESP32 README, release
handover and physical decision all use 48 kHz / 128 samples / two 64-frame DMA
descriptors. The instruction is corrected to the current baseline and now says
not to *change* the geometry casually, rather than only warning against an
increase.

### Q001-2 — repair the final facade override contract

`midi_integration.InstrumentBackend._reset_synth_role_to_preset` did not accept
the keyword preservation contract exposed by both parent implementations. It
worked for current zero-keyword call sites but violated substitutability and
could fail when a parent/application collaborator passed preserved control or
volume values.

The final facade now accepts the same typed `SynthRole` and keyword arguments.
Caller-supplied preservation is retained, and actively MIDI-bound values take
precedence because the established binding contract forbids a reset from
changing them. Existing no-keyword behavior is unchanged.

### Q001-3 — remove the legacy type-error allowance

The remaining mypy inventory mixed one real override mismatch, invariant-list
annotations and PySide descriptor-stub limitations. The cycle:

- accepts a `Sequence[int | float]` at the read-only tuning boundary;
- annotates the scheduled writer with its existing `ByteSink` protocol;
- uses Python `list` types for Qt list properties. A direct meta-object check
  established that this still exposes the exact `QVariantList` Qt type;
- separates internal rhythm-tempo/density accessors from QML property
  descriptors;
- narrows PySide descriptor casts to the final MIDI integration facade;
- types the captured root as `QQuickWindow` and uses the declared `QImage.save`
  byte-format overload;
- removes an unnecessary explicit backend deletion which required a Ruff
  undefined-name suppression despite normal function-scope lifetime already
  providing the same teardown.

The production mypy result is now 0 errors. The checked-in ratchet is reduced
from 42 to 0, so the former errors cannot silently return. Twenty-eight newer
production modules continue to be checked in strict mode.

### Q001-4 — make dead-code checks and one test meaningful

The Ruff gate previously selected only a subset of Pyflakes. A broader scan
found unused production imports/locals in command planning, transport, QML
composition support, MIDI, synth state and package audit code. These were
removed without changing outputs.

The scan also found that
`test_cold_start_is_immediate_but_live_drum_edits_are_quantized` constructed
the expected live aligned-trigger collection but never asserted it. The test
now requires that collection to be non-empty. Ruff now selects all `F`
correctness rules in addition to `E9`, preventing unused, undefined and related
Pyflakes regressions across production, tests and tools.

### Q001-5 — include newer authoritative contracts in document validation

The active-document quality policy predated three authoritative contracts.
`osc_control.md`, `sequencer_sequences.md` and
`test_process_architecture.md` are now included in status/owner/verification
validation. This does not freeze their prose; it protects their declared
authority and lifecycle metadata.

## Current structural trend

The largest remaining source files are approximately:

- `code/app_core.py`: 3,918 lines;
- `code/midi_player.py`: 2,337 lines;
- `code/amy_transport.py`: 1,660 lines;
- `gui/Main.qml`: 1,559 lines.

The central classes remain substantial:

- base `InstrumentBackend`: about 2,712 lines and 185 direct methods;
- `MidiPlayerBackend`: about 1,941 lines and 118 direct methods;
- `AmySerialClient`: about 1,342 lines and 73 direct methods.

They are materially smaller/more delegated than the original audit, but still
have several reasons to change. Size is navigation evidence, not a reason to
split methods arbitrarily.

## Improvements that remain useful but are not immediately required

These have no demonstrated current user-facing failure in this cycle and must
remain separately reviewable work:

1. Expose `TransportHealth` through one application-facing supervisor/state so
   a writer failure becomes visible even when no later command is sent. Define
   restart versus reconnect policy before adding UI behavior (post-T25 T26).
2. Continue strangler extraction of complete performance, preset-side-effect,
   rhythm-state and presentation responsibilities from `InstrumentBackend`.
   Do not split by line count or change the QObject surface (T28).
3. Separate remaining MIDI performance/note/row ownership from
   `MidiPlayerBackend`, using the existing input port, binding service and
   immutable OMNI snapshot rather than another state machine (T29).
4. Separate remaining rhythm/catalogue state selection from AMY command
   submission while retaining the existing pure plans, queue semantics and
   exact wire output (T30).
5. Although ordinary mypy is now clean, older large modules still contain
   broad serialization/QML `Any` boundaries. Tighten them incrementally after
   T28-T30, then move those modules to strict checking; do not replace narrow
   justified PySide casts with global ignores (T31 continuation).
6. Reduce `Main.qml` only by extracting cohesive pages/sections. Accessibility,
   keyboard focus and non-color state feedback need an explicit product/UI
   acceptance pass while preserving native mouse/touch gesture handling (T32).
7. Continue replacing source-spelling assertions with behavior, Qt
   introspection, AST/import or structured-data assertions after implementation
   locations stabilize. Keep literal protocol assertions where the bytes/text
   are the contract (T33).
8. Complete one structured platform-capability documentation authority and
   reassess remaining tool ownership now that package self-test code has been
   removed from production (T34, partially completed by test separation).
9. Generate the Gamma9001 direct mapping deterministically from the exact AMY
   release input, but retain the reviewed snapshot until byte-for-byte and
   musical parity are proven (T35).
10. Deepen captured wheel, Android/Qt/SDK and runner input evidence without
    claiming byte-reproducibility that has not been measured (T36).
11. Perform the catalogue licence/authorship audit, compatibility-API decision,
    mutation-tool decision and production-signing decision only with their
    documented owner/governance input (D01-D04).
12. Keep physical macOS, Windows, Raspberry Pi, Android and ESP32 real-time
    evidence distinct from hosted CI. In particular, the ESP32 sequence RCU
    path still needs physical worst-case timing, memory-watermark and effects
    load measurement.

## Stop conditions for the next cycle

Do not use this handover to authorize a multi-facade rewrite, introduce a DI
framework, change AMY wire commands, merge OMNI/MIDI ownership, implement
gesture timing in Python, call parser simulation physical MIDI, or weaken the
five-platform release gate. Select one bounded continuation item and reread its
owning subsystem contract before editing.

## Final verification result

The final branch state passed:

```bash
/home/jeroen/omnichord/omnichord-env/bin/python tests/run_quality.py
/home/jeroen/omnichord/omnichord-env/bin/python tests/run_tests.py --suite all
/home/jeroen/omnichord/omnichord-env/bin/python ../esp32p4/tests/test_firmware_contract.py
git diff --check
```

The complete local suite includes quality, every discovered unit module,
portable separated input processes, Linux platform input, frontend, serial,
presets, native controls and native rhythm. No sandbox exception was needed.
Coverage remains the separately recorded local-environment limitation above;
it was not presented as passing.
