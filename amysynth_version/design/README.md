# AMY Synth Omnichord Design Documentation

This directory is the design contract for the AMY Synth Omnichord implementation.

This is the only active implementation contract. The repository's Sonic Pi
version is frozen legacy material: it is not maintained, tested or modified as
part of AMY development.

The documents define:

- architecture boundaries
- GUI behavior
- MIDI behavior
- AMY wire protocol usage
- preset ownership
- tuning rules
- testable use cases

Core rules:

- The Qt application produces AMY wire commands only.
- AMY transport may be local development or ESP32-P4 serial without changing behavior.
- OMNI and MIDI remain separate subsystems.
- Shared state is explicit; tuning is shared only when coupling is enabled.
- `rhythm_bahavior.md` is the authoritative rhythm transport/tempo contract.
- `testing.md` defines the maintained local suites and CI responsibilities;
  it also defines five-platform release packaging and validation.
  Detailed executable scenarios live in `../qt_frontend/tests/USE_CASES.md`.
- `sound_balance.md` defines user storage/config overrides, strum modes, MIDI
  control indicators and the instrument-balance measurement contract.
- `midi_control.md` is the authoritative MIDI CC learn, binding, LRU/LED and
  preset-persistence contract.
- `CODEX_HANDOVER_EXTERNAL_CONTROLS.md` records the branch-local lessons from
  the external-control rework: smooth Qt slider drag, backend echo boundaries,
  MIDI input tech indicators and scoped hardware button takeover.
- `CODEX_HANDOVER_CODE_QUALITY_BASELINE.md` indexes the 2026-08-31
  repository-wide code-quality audit. Those files are analysis and proposed
  refactoring guidance, not authority to change product behavior.

## Code-quality audit handovers

The audit is intentionally split by responsibility so future work can select a
small, behavior-preserving phase:

- `CODEX_HANDOVER_CODE_QUALITY_BASELINE.md` — method, measurements, strengths,
  highest-priority findings and index;
- `CODEX_HANDOVER_CONFIGURATION_AND_DRY.md` — configuration authority,
  validation, migration and duplicated defaults;
- `CODEX_HANDOVER_ARCHITECTURE_BOUNDARIES.md` — dependency direction,
  composition, state ownership and incremental component boundaries;
- `CODEX_HANDOVER_PLATFORM_ADAPTER_BOUNDARY.md` — one identical
  platform-neutral Omnichord core with platform-specific behavior isolated in
  imported/injected adapter modules;
- `CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md` — reuse of established
  Python functionality, requirements ownership and strict maintenance,
  adoption, licensing, security and five-platform selection criteria;
- `CODEX_HANDOVER_PYTHON_MODULARITY_AND_TYPES.md` — Python hotspots, typing,
  public interfaces, errors and tooling;
- `CODEX_HANDOVER_QML_UI_ARCHITECTURE.md` — QML responsibilities, reusable
  interaction primitives, slider lessons and UI testing;
- `CODEX_HANDOVER_MUSICAL_DOMAIN_AND_DATA.md` — musical policy separation,
  command plans, catalogues, provenance and duplicated datasets;
- `CODEX_HANDOVER_TEST_ARCHITECTURE.md` — behavior/static test balance,
  quality gates, timing and release evidence;
- `CODEX_HANDOVER_CONCURRENCY_REALTIME_AND_IO.md` — thread ownership, bounded
  queues, failure, shutdown and local framing;
- `CODEX_HANDOVER_PORTABILITY_RELEASE_AND_SECURITY.md` — platform selection,
  pinned inputs, manifest, provenance, SBOM and signing boundaries;
- `CODEX_HANDOVER_DOCUMENTATION_AND_REPOSITORY_HYGIENE.md` — document
  authority/status, stale facts, tools, screenshots and repository policy;
- `CODEX_HANDOVER_CODE_QUALITY_ROADMAP.md` — prioritized, independently
  releasable phases and proof required for each.
- `CODEX_HANDOVER_ORDERED_CODE_QUALITY_TASKS.md` — dependency-aware ordered
  implementation queue, including prerequisites, scope and proof for the first
  25 tasks.
- `code_quality_tasks/README.md` — actual T01-T25 result handovers, verification
  evidence and newly discovered follow-up work.

## Required reading route for Codex

`AGENTS.md` requires Codex to use this route at the start of every active-AMY
session. Read selected files in full rather than relying on search excerpts.

Always read these baseline contracts:

- `../README.md` — active implementation, runtime and package overview;
- `principles.md` — product and engineering priorities;
- `architecture.md` — process, transport, synth and bus ownership;
- `behavior.md` — shared application behavior;
- `testing.md` — maintained suites, CI and verification rules.

Then add every row that matches the task:

| Task area | Additional required reading |
| --- | --- |
| Python dependencies, build tools or release inputs | `CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md`, `../qt_frontend/docs/DEPENDENCIES.md`, `../qt_frontend/packaging/AMY_RELEASE.md` |
| Qt/QML layout, interaction or screen behavior | `gui.md`, `ui_behavior_reference.md`, `../qt_frontend/docs/CONTROL_SAFETY.md` |
| MIDI input, MIDI screen or CC learn | `midi.md`, `midi_control.md`, `presets.md`, `sound_balance.md`, `../qt_frontend/tests/USE_CASES.md` |
| Presets, user state or migration | `presets.md`, `sound_balance.md`, `../qt_frontend/tests/USE_CASES.md` |
| Rhythm, tempo or sequencer behavior | `rhythm_bahavior.md`, `../qt_frontend/docs/SEQUENCER_TAGS.md`, `../qt_frontend/tests/USE_CASES.md` |
| Tuning, pitch or note conversion | `tuning.md`, `use_cases.md`, `../qt_frontend/tests/USE_CASES.md` |
| AMY commands, sockets, serial or buses | `amy_interface.md`, `../qt_frontend/docs/CONTROL_SAFETY.md` |
| Instrument catalogue, defaults or balance | `sound_balance.md`, `presets.md`, `../qt_frontend/instruments/README_defaults.md` |
| Platform packages, releases, Android or native Windows | `../qt_frontend/README.md`, `../qt_frontend/INSTALL.md`, `../qt_frontend/packaging/android/README.md`, `../qt_frontend/docs/WINDOWS_NATIVE.md`, `../../.github/workflows/desktop-release.yml` |
| Optional historical WSL experiment | `../qt_frontend/docs/WSL_APPIMAGE_TESTING.md`, plus the desktop documents above |
| ESP32-P4 firmware or packaging | `../esp32p4/README.md`, `../esp32p4/CI_FLASH.md` |
| Known unresolved behavior | `unclear.md` plus the owning subsystem documents above |
| Architecture, code quality or refactoring | `CODEX_HANDOVER_CODE_QUALITY_BASELINE.md`, the relevant dedicated audit handover, `CODEX_HANDOVER_CODE_QUALITY_ROADMAP.md`, plus every owning subsystem contract touched by the proposed change |
| Selecting or executing the next code-quality task | `CODEX_HANDOVER_ORDERED_CODE_QUALITY_TASKS.md`, its cited detailed handovers and every owning subsystem contract listed for that task |
| Platform-dependent application code or adapter extraction | `CODEX_HANDOVER_PLATFORM_ADAPTER_BOUNDARY.md`, `CODEX_HANDOVER_ARCHITECTURE_BOUNDARIES.md`, `CODEX_HANDOVER_PORTABILITY_RELEASE_AND_SECURITY.md`, plus the platform/package contracts selected above |
| Python dependency, third-party library or local-versus-external implementation choice | `CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md`, `CODEX_HANDOVER_PORTABILITY_RELEASE_AND_SECURITY.md`, `CODEX_HANDOVER_ARCHITECTURE_BOUNDARIES.md`, plus the owning subsystem contract |

When a selected document points to a more specific behavioral contract, read
that contract too. Historical files under `qt_frontend/docs/history/` and the
Sonic Pi tree are not startup reading unless the user explicitly asks for
historical comparison.

For continuation work on active branches, also read the repository-root
`CODEX_HANDOFF.md` when it exists. It records current branch/release state and
session-specific lessons learned, but it never replaces the authoritative
design contracts listed above.

When implementation and design differ, the difference must be documented before changing behavior.
