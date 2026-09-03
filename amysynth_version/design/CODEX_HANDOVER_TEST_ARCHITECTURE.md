# Codex handover: test architecture and quality gates

Status: analysis; no test or product behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Current test strength

The project has a broad and valuable acceptance ladder:

- fast Python unit tests;
- headless Qt/frontend tests;
- preset tests;
- PTY serial integration;
- real/native AMY control and rhythm tests;
- package smoke tests;
- ESP32-P4 compatibility build/tests;
- Android emulator audio/wire verification;
- Linux, Windows and macOS package verification;
- screenshot refresh after successful publication.

The audited release passed all six regression groups and all five platform
jobs in run `33439634074`. Locally before merge, 185 unit, 15 frontend and 14
preset tests passed. This is a solid behavior-preservation foundation for an
incremental refactor.

## Inventory

The active test set has 36 Python files, approximately 10,600 lines and 235
test methods. The custom `tests/run_tests.py` discovers top-level unit modules
and executes each in a separate process; integration groups are explicit.

Separate processes improve isolation but complicate aggregate coverage and can
hide expensive repeated setup. Preserve isolation where global Qt/audio state
requires it, but make the reason explicit per suite.

## Finding T1 — source-text assertions are overrepresented

The tests use approximately 152 `read_text` calls and 651 source-text
assertions (`assertIn`, regex and related checks). `test_static_contracts.py`
alone is about 1,061 lines.

Static checks can cheaply guard essential architecture, such as “Qt code does
not import amy”. They become brittle when they assert exact source fragments,
ordering or formatting. Such a test can:

- fail a safe rename/extraction with no behavior change;
- pass code whose literal text remains but is unreachable;
- encourage copy/paste to satisfy a string;
- make architecture depend on implementation spelling.

Example: the architecture test verifies `amy_serial` does not publicly expose
`DEFAULT_CONFIG`, but does not detect the full obsolete config still executable
inside `amy_transport.py`.

Replacement hierarchy:

1. executable behavior assertion;
2. public QObject/API introspection;
3. structured JSON/YAML/schema validation;
4. Python AST/import-graph assertion;
5. QML parser/introspection where practical;
6. narrow text assertion only when no stable structure exists.

Keep static architecture checks, but state the semantic rule and parse the
relevant structure.

## Finding T2 — configuration happy paths dominate

Current tests do not reject several malformed configurations and generally
pass explicit MIDI platform profiles, bypassing the shipped `linux` default.

Add mutation/adversarial fixtures for:

- missing required leaf values;
- unknown or misspelled keys;
- wrong scalar/collection types;
- invalid ranges and overlapping ownership;
- older config revisions;
- interrupted/invalid user writes;
- shipped config on every package platform profile;
- loader parity across all supported entry points.

Validate before I/O construction so these tests require no hardware.

## Finding T3 — no measured coverage or mutation feedback

There is no checked-in coverage configuration and no mutation-testing gate.
Raw percentage should not become a vanity target. Use coverage to find
unexercised branches in the extracted pure domain/config/command modules and
mutation testing selectively on high-value state machines:

- MIDI binding transitions;
- note-on/note-off ownership;
- config migrations/schema-domain validation;
- slider value/intention mapping;
- rhythm/pattern plan compilation.

Because the runner starts subprocesses, configure coverage subprocess support
or emit per-process data and combine it. Do not weaken process isolation simply
to make one number easier.

## Finding T4 — static analysis is not a quality gate

There is no project Ruff/mypy configuration. A baseline mypy run found 32
errors in seven production files. Add gates by ratchet:

- `compileall` and config/schema validation immediately;
- Ruff with a selected, initially passing/error-budgeted ruleset;
- mypy strict for new pure modules and baseline/no-new-errors elsewhere;
- dependency/workflow validation;
- link/status validation for active docs.

Do not combine formatter churn with product refactors. Do not silence existing
errors globally.

## Finding T5 — concurrency and timing need deterministic seams

The project correctly retains real timing/native tests, but unit tests also
need controllable clocks and schedulers for application policies. Test:

- queued ordering of MIDI note/control events;
- shutdown while a write/event is pending;
- writer failure surfaced to UI;
- bounded debug/transport queue behavior;
- no new note-on after an onset gate/stop, while existing note-off remains;
- arpeggio-rate changes preserve original note duration;
- slider external echo during an active drag.

Use a fake monotonic clock only at the pure/application boundary. Never replace
AMY's actual sequencing or Qt pointer classification with Python timer models.

## Finding T6 — release suite observability can improve

Record machine-readable result files, duration and stable suite names. This
enables:

- identifying slow/flaky tests;
- setting explicit time budgets;
- preserving failure artifacts/logs;
- comparing platform coverage;
- distinguishing infrastructure failure from product assertion;
- confirming the exact release commit and AMY SHA in every report.

Retries should only address identified infrastructure flakiness and must still
expose the first failure. A retry is not a fix for nondeterministic product
logic.

## Proposed test pyramid by boundary

### Pure domain/config tests

Fast, no Qt, filesystem only through temporary stores, generated properties
where useful. Cover catalogues, tuning/chords, preset normalization, config
schema/migrations, binding transitions and command plans.

### Adapter contract tests

Run the same sink/store/MIDI adapter contract against fakes and platform
implementations. Verify framing, errors, cancellation, lifecycle and resource
ownership.

### Qt component/facade tests

Inspect QObject contracts and render real QML controls. Exercise multi-move
drag, touch/mouse parity, focus, indicator state and backend echo.

### Native AMY integration

Retain current real wire/audio tests. They are the proof that a pure command
plan means the same thing in the pinned AMY implementation.

### Package/release acceptance

Retain tests against built artifacts on every platform, with exact asset
manifest, hash, AMY identity, entry point, MIDI tech selection and basic audio
behavior.

## Quality scenarios and acceptance measures

- A transport adapter can be replaced while its contract suite remains
  unchanged.
- A QML visual refactor does not require changing musical unit expectations.
- A config typo fails at startup with exact JSON path before any device opens.
- A source/module extraction requires changing no literal-whole-function test.
- Every newly extracted pure module has branch coverage for error behavior,
  not only happy paths.
- A killed writer thread causes a deterministic failing test rather than a
  hang/time-based guess.
- A release report lists exactly the expected five packages and five hashes.

## Documentation tests

Active docs should be tested for:

- local link validity;
- explicit status (authoritative, analysis, historical);
- no two authoritative owners for the same contract;
- configured/file paths that exist;
- generated tables matching their source when exact values are included.

Do not assert exact prose. Historical documents may intentionally describe old
state if clearly labeled and excluded from active routing.

## Refactor safety protocol

For each extraction:

1. state the behavior/public boundary that must not change;
2. add or identify characterization tests;
3. make one dependency-direction change;
4. compare AMY wire/event sequences where relevant;
5. run local affected suites plus the normal unit set;
6. keep the commit reviewable;
7. run the complete five-platform release before merging a behavior-bearing
   architecture phase to `main`.
