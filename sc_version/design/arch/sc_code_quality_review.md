# SuperCollider edition code-quality review

Status: completed review and active non-regression evidence
Owner: SuperCollider edition architecture
Applies to: `sc_version`
Last verified: 2026-09-15

## Scope and outcome

This review compares `rework/sc_code_quality` with the tested SC edition on
`main`. It covers only the SuperCollider tree, its release workflow and shared
controller profile documentation. The AMY edition remains unchanged.

The review found that the SC edition had reached functional independence but
still inherited a second, unused AMY implementation in source, configuration,
firmware, tests, data and documentation. The branch now has one production
composition root, one typed SuperCollider client and one SC package graph.
There is no selectable synth backend and no AMY runtime fallback.

## Applied changes

- Replaced the copied AMY configuration and twelve migrations with a small,
  strict and typed frontend configuration. SuperCollider process/sample policy
  remains separately owned by `supercollider.json`.
- Removed AMY serial, socket, wire, scheduler, patch, drum, firmware, Android,
  Windows-service and release implementations from the SC tree.
- Removed the old AMY rhythm and bass catalogues. Runtime music now has one
  authority under `music/sc_expansion`.
- Removed copied AMY tests and release tooling. The remaining test runner names
  only SC and engine-neutral frontend contracts.
- Removed the unused Raspberry Pi AMY wire/realtime toolset. Raspberry Pi is a
  packaged SC desktop target; future tuning must be designed and tested for the
  SC process graph rather than copied from another engine.
- Kept `supercollider-legacy-map.json` as explicit data migration. A first SC
  launch may read engine-neutral values from an existing `amy_config.json`, but
  neither file creates an AMY runtime dependency.
- Corrected the MIDI percussion boundary so an incoming GM note is sent once
  to the SC GM percussion program instead of being translated through the old
  Gamma9001 mapping and interpreted a second time.
- Preserved optional OSC discovery: omitting both listen address and port is a
  valid unconfigured state and keeps OSC out of the technology row; a partial
  pair is rejected with a field-specific error.
- Replaced the copied design tree with concise, current SC ownership,
  configuration, process, test and packaging contracts. Superseded detail stays
  available in Git history.

The first diagnostic cleanup commit removed 441,900 lines while adding 1,280
lines of replacement configuration, tests and current documentation. Line
count was not the objective, but this reduction confirms that the SC product no
longer carries the old product as a hidden alternative.

## Architecture verification

- Qt/Python owns interaction and immutable plan construction; `sclang` owns
  musical timing and voice lifetime; `scsynth` owns audio resources.
- Production communicates through the typed versioned OSC protocol. UI code
  does not own engine node IDs or a musical clock.
- `code/main.py` is the only composition root and injects one client.
- Platform selection is restricted to named adapters and checked structurally.
- MIDI/OSC integration stimuli, frontend and fake or real engine run in
  separate processes.
- Runtime configuration, source identities and dependencies each have a single
  checked-in authority.
- The production import closure reaches every runtime module except
  `sfz_manifest_compiler.py`, which is deliberately a source-maintenance tool.
- The SC package contract rejects reintroduction of AMY runtime/configuration,
  firmware source or the former AMY-specific Pi tools.

No unresolved architecture violation was found in the reviewed delta.

## Executed evidence

- `python tests/run_tests.py --suite all`: passed locally, including quality,
  portable process boundaries, Linux MIDI, SC compiler, sequencer, NRT audio,
  sample banks and package contracts.
- Ruff: passed.
- Mypy ratchet: zero legacy errors; all newly introduced modules strict.
- QML lint ratchet: passed at the recorded warning baseline.
- GitHub Actions run `34903048200`: Linux x86_64, Raspberry Pi aarch64, macOS
  arm64 and Windows x86_64 jobs all passed on merged `main`.

The local SuperCollider compiler reports that realtime priority is unavailable
inside the test environment. This is expected for compiler/NRT tests and is not
reported as realtime playback evidence.

## Remaining improvements

The current non-blocking work is maintained in [`backlog.md`](backlog.md).
Highest-value items are native CoreMIDI/WinMM receive adapters, a clearer split
between MIDI performance ownership and its Qt model, and careful extraction
from the large `InstrumentBackend` only at demonstrated ownership seams.
Physical playback qualification on every packaged operating system remains
product evidence, not an architecture defect.
