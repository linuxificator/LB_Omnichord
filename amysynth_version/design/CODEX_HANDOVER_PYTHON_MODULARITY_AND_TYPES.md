# Codex handover: Python modularity, readability and typing

Status: analysis; no behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Summary

The Python code is more disciplined than file size alone suggests: it parses
cleanly, nearly every function signature is annotated, domain catalogue values
use frozen dataclasses, and many behaviors have direct tests. The main problem
is that the annotations stop at the most important boundaries. Large mutable
facades accept `Any`, nested dictionaries and dynamically replaced globals, so
the type system cannot verify how the modules actually collaborate.

The goal is not “make mypy green” in isolation. The goal is to use types and
smaller modules to make ownership, valid states and dependency direction clear.

## File and class cohesion

### `app_core.py`

At about 4,970 lines it contains:

- QApplication/QML startup and argument processing;
- the primary QObject backend and QML-visible properties;
- instrument/voice state;
- performance and chord behavior;
- preset application and persistence helpers;
- music-theory/tuning tables and conversions;
- configuration use;
- transport/client selection assumptions;
- package-smoke behavior.

`InstrumentBackend` is about 3,333 lines with 175 methods. Its reasons to change
span UI, musical policy, persistence, protocol output and lifecycle. It should
remain as a compatibility facade while these responsibilities move behind
explicit collaborators.

The 500-line `main` and 390-line `_apply_preset_data` are immediate extraction
seams. First extract deterministic parsing/normalization and a declarative
preset-application plan; keep side-effect order in a short coordinator until
tests prove it can also be simplified.

### `midi_player.py`

At about 3,226 lines it includes:

- platform MIDI input discovery and readers;
- stream parsing;
- the MIDI-screen AMY engine/command generation;
- QML backend state;
- MIDI preset persistence;
- control binding/learning integration;
- QML indicator and activity reporting;
- coupling to private OMNI backend fields.

Split by stable reason to change, not by arbitrary line count:

- `midi_inputs/` adapters and discovery;
- pure MIDI message decoding/normalization;
- `MidiPerformanceEngine` for note/command ownership;
- a small QObject MIDI view model;
- explicit snapshot interfaces to permitted OMNI state.

### `amy_transport.py`

At about 2,568 lines it combines three writer implementations, queue/lane
scheduling, logging, serial/socket framing, synth parameter translation,
rhythm plan compilation and obsolete config loading.

A clean separation is:

- pure `AmyCommandCompiler` and validated command value;
- pure `RhythmPlanCompiler`;
- one reusable priority/lane scheduler;
- transport-specific writer adapters;
- observable transport lifecycle/health;
- no config loading in this module.

The serial, Unix socket and Qt-local writers already share scheduling through
inheritance, but subclassing a concrete serial writer causes fields such as
`serial` to carry incompatible meanings. Prefer a scheduler that owns a small
`write_bytes` port supplied by each adapter.

## Function complexity

The largest decision-heavy functions are catalogue loaders, startup,
parameter-command compilers and preset application. Refactor them by phases:

1. parse untrusted data into a typed intermediate value;
2. validate local field constraints;
3. validate cross-reference/domain invariants;
4. build immutable indexes/plans;
5. apply side effects in explicit order.

This preserves useful fail-fast behavior and produces more specific tests. Do
not create dozens of one-line helpers whose names merely restate syntax.

## Type baseline

Strength:

- 669/670 functions have return annotations;
- 745/746 parameters are annotated;
- immutable domain dataclasses already document several valid states.

Weakness:

- `Any` appears frequently in `midi_player.py`, `amy_transport.py`,
  `app_core.py`, `midi_control.py` and `midi_integration.py`;
- nested config/preset dictionaries do not state required keys or versions;
- `owner`/`client` parameters are implicit large interfaces;
- a serial object, Unix socket and QLocalSocket occupy related but incompatible
  attributes in the writer hierarchy;
- monkey-patched symbols make static imports disagree with runtime behavior.

The installed mypy 1.19.1, run with missing third-party imports ignored,
reported 32 errors in seven production files. Categories included:

- missing collection annotations;
- incompatible serial/socket assignments;
- object indexing and numeric conversions;
- list invariance;
- Optional path handling;
- lambda/callback types;
- an incompatible override in `midi_integration.py`;
- redefinitions/assignments caused by `main.py` monkey-patching.

This is a manageable baseline. Do not hide it with a repository-wide ignore.

Primary references:

- [PEP 484 Type Hints](https://peps.python.org/pep-0484/)
- [PEP 8 public/internal interface and wildcard-import guidance](https://peps.python.org/pep-0008/)

## Type strategy

### Prefer domain types over nested dictionaries

Use frozen dataclasses, enums, `TypedDict` only at serialization boundaries,
and small Protocols. Good candidates:

- resolved config sections;
- preset schema/version and normalized preset;
- synth/bus/tag identifiers where integers from different namespaces can be
  confused;
- MIDI note/control events;
- AMY command and scheduled command;
- transport health/failure state;
- immutable OMNI snapshot available to MIDI.

Convert JSON to types at the boundary. Do not carry `dict[str, Any]` into the
application core and repeatedly reinterpret it.

### Protocols should describe actual narrow use

Instead of `owner: Any`, define only what is intentionally shared, for example
a method returning tuning/performance context. Instead of `client: Any`, pass
an `AmyCommandSink` plus the small typed config section an engine needs.

This prevents accidental access to a new private field and turns undocumented
coupling into a reviewable interface.

### Ratchet static checking

1. Add a mypy configuration with the current supported Python versions.
2. Check new small domain/config modules strictly.
3. Record existing errors by module; forbid new errors.
4. Remove ignores as collaborators are extracted.
5. Keep PySide-specific suppressions narrow and documented.

Mypy is a design feedback tool, not a release oracle. Native behavior tests
remain authoritative.

## Naming and public API

`amy_serial.py` dynamically re-exports almost everything from
`amy_transport.py`, while `main.py` uses a wildcard import. PEP 8 notes that
wildcard imports obscure which names exist and recommends explicit `__all__`
for public APIs.

Recommendations:

- make `amy_serial.py` an explicit compatibility facade or remove it after all
  call sites migrate;
- define `__all__` where a stable module API exists;
- give the three backend classes distinct implementation names during the
  transition, even if QML continues to receive `instrumentBackend`;
- reserve leading underscores for truly private values and stop cross-module
  private-field reach;
- use names that describe domain role (`RhythmPlan`, `MidiInputEvent`) rather
  than mechanism-only dictionaries.

## Exception and failure handling

The audit found several broad exception handlers and silent/pass paths. Some
are appropriate at optional platform probes, but every suppression should say:

- which exact failure is expected;
- what degraded mode results;
- how diagnostics expose it;
- whether a retry occurs.

Catch narrow exception types in domain/load code. At a process/thread boundary,
catch broadly only to convert the failure into a recorded terminal state and
then stop safely. Never let a background exception silently remove audio/MIDI
output while the UI remains “ready”.

## Readability and tooling

There is currently no repository-level `pyproject.toml`, Ruff configuration,
mypy configuration, coverage configuration or dependency lock. Add tooling in
stages:

- Ruff for a deliberately selected ruleset: syntax/import hygiene, undefined
  names, dangerous defaults and simple maintainability errors;
- formatter only after separating behavior-changing diffs from mechanical
  formatting, because giant whole-file changes harm review/history;
- mypy as a ratchet;
- `compileall` as a fast baseline (currently passes);
- a small complexity report used for trend/navigation, not a hard universal
  threshold.

Avoid a single “lint everything” change on active product files. Establish a
baseline, fix correctness-relevant findings first, then lower thresholds.

## Test/support code placement

`code/test_control.py` is a localhost HTTP adapter used only by integration
headless testing. It belongs under test support and should be excluded from
normal packages. `code/package_smoke.py` is different: packaged acceptance
tests intentionally need it. Keep that adapter but label and feature-gate it so
normal runtime cannot accidentally start a test endpoint.

Diagnostic slider baseline apps are useful reproduction tools. Move them to an
explicit `tools/diagnostics/` namespace and document invocation rather than
mixing them with product entry points.

## Acceptance criteria for modularity work

- no runtime symbol monkey-patching;
- no constructor calls an overridable method;
- pure musical/config/command tests import no PySide module;
- MIDI code does not access OMNI private fields;
- each transport adapter implements one typed sink contract;
- current mypy baseline only improves;
- QML-visible property/signal/slot names remain compatible until a separately
  approved UI contract change;
- full behavior/native/package tests remain green after each extraction.
