# Codex handover: code-quality audit baseline

Status: analysis, not an implementation contract
Audit date: 2026-08-31
Audited branch: `rework/code_quality`
Audited base: `c46b93b607722dd429ac54cab163deb61801632a`
Release behavior represented by the base: `R20260831T210652`

## Purpose and scope

This handover is the index and measurement baseline for the code-quality audit.
It deliberately changes no product behavior. Future work should use the
separate handovers below rather than treating “clean up the code” as one large,
unbounded refactor.

The audit covers the active AMY implementation, its Qt/QML frontend, musical
datasets, tests, packaging, release automation and active design documentation.
The frozen Sonic Pi implementation is out of scope. The AMY fork itself is a
dependency and protocol boundary; this audit records how LB consumes it, but it
does not propose LB-specific changes to Shorepine AMY.

## Analysis set

| Area | Dedicated handover |
| --- | --- |
| Configuration ownership and DRY | `CODEX_HANDOVER_CONFIGURATION_AND_DRY.md` |
| Component boundaries and dependency direction | `CODEX_HANDOVER_ARCHITECTURE_BOUNDARIES.md` |
| Platform-neutral core and concrete platform adapters | `CODEX_HANDOVER_PLATFORM_ADAPTER_BOUNDARY.md` |
| External dependency selection and reuse | `CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md` |
| Python modularity, readability and typing | `CODEX_HANDOVER_PYTHON_MODULARITY_AND_TYPES.md` |
| QML/UI structure and interaction ownership | `CODEX_HANDOVER_QML_UI_ARCHITECTURE.md` |
| Musical domain and dataset quality | `CODEX_HANDOVER_MUSICAL_DOMAIN_AND_DATA.md` |
| Test architecture and quality gates | `CODEX_HANDOVER_TEST_ARCHITECTURE.md` |
| Concurrency, real-time behavior and I/O | `CODEX_HANDOVER_CONCURRENCY_REALTIME_AND_IO.md` |
| Portability, release integrity and security | `CODEX_HANDOVER_PORTABILITY_RELEASE_AND_SECURITY.md` |
| Documentation and repository hygiene | `CODEX_HANDOVER_DOCUMENTATION_AND_REPOSITORY_HYGIENE.md` |
| Prioritized, incremental execution plan | `CODEX_HANDOVER_CODE_QUALITY_ROADMAP.md` |

## Method

The audit combined:

- complete reading of the active design and platform documentation routed by
  `design/README.md`;
- AST-based Python size, method, annotation and approximate decision counts;
- QML line, handler, backend-call and similarity counts;
- dependency/import and repository-content inspection;
- targeted adversarial configuration loads;
- a mypy baseline using the installed mypy 1.19.1;
- test-suite structure and source-assertion counts;
- recent Git churn across 120 commits;
- release-workflow and package inspection;
- successful release evidence from GitHub Actions run `33439634074`;
- quality criteria from the primary sources listed below.

Counts are navigation aids, not targets by themselves. A long function is not
automatically wrong, and a short function is not automatically cohesive. The
counts identify places where complexity, change frequency and broad ownership
coincide; every recommendation is based on the actual responsibility boundary.

## Quantitative baseline

The selected active Python, QML, test, packaging and workflow sources contain
approximately 30,000 lines. The Python production set parses cleanly and has
excellent annotation coverage at the signature level: 669 of 670 functions
have a return annotation and 745 of 746 parameters are annotated.

Largest active implementation files:

| File | Approximate lines | Quality significance |
| --- | ---: | --- |
| `qt_frontend/code/app_core.py` | 4,970 | UI backend, application orchestration, music theory, presets and startup |
| `qt_frontend/code/midi_player.py` | 3,226 | MIDI UI backend, input adapters, mapping and a second AMY command engine |
| `qt_frontend/code/amy_transport.py` | 2,568 | transport workers, AMY command compilation, rhythm plan generation and obsolete config |
| `qt_frontend/qml/Main.qml` | 1,671 | root composition plus 33 backend calls and many handlers |
| `qt_frontend/tests/test_static_contracts.py` | 1,061 | large source-text contract suite |

Largest classes:

| Class | Approximate lines / methods | Observation |
| --- | ---: | --- |
| `app_core.InstrumentBackend` | 3,333 / 175 | central mutable object with many unrelated reasons to change |
| `midi_player.MidiPlayerBackend` | 2,106 / 121 | MIDI facade plus controller, persistence, platform and domain policy |
| `amy_transport.AmySerialClient` | 1,793 / 72 | I/O facade plus command/rhythm compiler and configuration consumer |
| `performance_backend.InstrumentBackend` | 662 / 46 | inheritance extension of the already large base backend |
| `midi_control.MidiControlState` | 504 / 29 | cohesive state machine compared with the larger facades, but still coupled to untyped dictionaries |

Highest approximate decision complexity included
`load_drum_pattern_catalog` (50), `app_core.main` (42),
`load_bass_riff_catalog` (42),
`AmySerialClient._param_commands_for_synth` (38),
`MidiAmyEngine._param_commands` (33), and
`InstrumentBackend._apply_preset_data` (32). `app_core.main` is also about 500
lines and `_apply_preset_data` about 390 lines.

The 36 Python test files contain approximately 10,600 lines and 235 test
methods. This is a strong test investment. It also contains 152 `read_text`
calls and roughly 651 source-text assertions, so part of the suite verifies
spelling and implementation shape instead of executable behavior.

Recent churn aligns with the structural hotspots: across the sampled 120
commits, `midi_player.py`, `app_core.py`, `amy_transport.py`,
`test_static_contracts.py`, `test_midi_engine.py`, the release workflow,
`Main.qml` and `MidiScreen.qml` were among the most frequently and heavily
changed files. Complexity plus churn is a stronger extraction signal than
either metric alone.

## Quality model used

ISO/IEC 25010:2023 defines a nine-characteristic product-quality reference
model and explicitly positions it for requirements, design objectives, test
objectives and acceptance criteria. This audit applies its concerns in concrete
LB terms:

- functional suitability: musical and control behavior remains correct;
- performance efficiency: audio/MIDI work stays bounded and UI frames do not
  wait on I/O;
- compatibility: AMY wire behavior and MIDI/platform interfaces remain stable;
- interaction capability: pointer, touch and hardware control behavior is
  predictable;
- reliability: worker and transport failures are detected and recoverable;
- security: local services, configuration and build dependencies have bounded,
  explicit trust assumptions;
- maintainability: responsibilities, types and sources of truth are clear;
- flexibility: platform and bank changes do not propagate through unrelated
  code;
- safety: control changes cannot create stuck notes or unsafe volume behavior.

The SEI quality-attribute method adds an important discipline: vague goals such
as “maintainable” are converted into scenarios with a stimulus, environment,
affected component, response and measurable response. The roadmap therefore
uses acceptance scenarios instead of aspiring to abstract cleanliness.

Examples for this repository:

- When a sixth MIDI input technology is added, only one platform adapter,
  configuration schema and targeted tests should change; musical playback and
  QML screens should not need protocol knowledge.
- When a user starts with a configuration from an older revision, startup must
  deterministically migrate or report every missing/invalid field before any
  transport thread starts.
- When an AMY writer fails during playback, the UI must receive a failure state
  within a bounded interval and shutdown must not close a resource still used
  by a live worker.
- When a release is rebuilt from the same declared inputs, dependency versions
  and provenance must be inspectable even if byte-for-byte reproducibility is
  not yet promised.

## Overall assessment

### Strong foundations to preserve

- The repository has explicit behavioral contracts and an unusually broad
  native/package test matrix across Linux, Windows, macOS, ESP32-P4 and Android.
- The release pins the exact AMY fork branch and commit across platforms.
- The Qt frontend remains a wire-only client, keeping AMY ownership outside UI
  code.
- OMNI and MIDI behavior are separated at the product-contract level.
- Musical catalogues use immutable dataclasses and validate substantial domain
  invariants.
- Slider interaction now follows Qt's native interaction signal and stable
  delegate lifetime instead of implementing gesture timing in Python.
- Local AMY transports use private Unix sockets or Windows named pipes rather
  than exposing a network service.

### Highest-priority findings

1. The shipped config fixes `tech_profile` to `linux`; runtime profile
   selection prefers it over platform detection. This is a concrete portability
   defect hidden by tests that inject profiles explicitly.
2. `amy_transport.py` still contains a large, obsolete embedded
   `DEFAULT_CONFIG` even though `config_loader.py` declares JSON the sole source
   of truth. It materially conflicts with the shipped config.
3. Configuration validation accepts missing operational fields, unknown keys,
   misspellings and incorrect types that later consumers silently default.
4. Three giant backend/client classes and runtime monkey-patching obscure
   ownership and make safe changes expensive.
5. MIDI note callbacks cross from reader threads directly into a QObject-owned
   backend while CC/button activity is queued through Qt signals.
6. Transport queues and debug logging are unbounded; background write failures
   are not consistently surfaced to the application.
7. Many static source assertions provide useful policy coverage but are brittle
   refactoring locks and not behavioral proof.
8. Runtime music data is duplicated byte-for-byte under design documentation.
9. Desktop dependencies and GitHub Actions are not immutable enough to explain
   or recreate a build precisely.
10. Active documentation has known contradictions about implemented ALSA
    sequencer support.

There was no evidence that an emergency rewrite is justified. The safest route
is characterization first, then one extraction seam at a time, with every step
remaining releasable and preserving public QML, preset, MIDI and AMY-wire
behavior.

## Primary references

- [ISO/IEC 25010:2023 product quality model](https://www.iso.org/standard/78176.html)
- [SEI: Reasoning About Software Quality Attributes](https://insights.sei.cmu.edu/library/reasoning-about-software-quality-attributes/)
- [SEI: Architecture Tradeoff Analysis Method](https://sei.cmu.edu/library/the-architecture-tradeoff-analysis-method/)
- [PEP 8: Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 484: Type Hints](https://peps.python.org/pep-0484/)
- [Qt: Best Practices for QML and Qt Quick](https://doc.qt.io/qt-6/qtquick-bestpractices.html)
- [NIST SP 800-218 Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
