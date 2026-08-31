# Codex handover: prioritized code-quality roadmap

Status: proposed execution plan; explicit approval is required before product changes
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Goal

Improve correctness, maintainability, portability and release assurance without
changing established musical, MIDI, QML, preset or AMY-wire behavior. Every
phase is independently reviewable, testable, releasable and reversible through
ordinary Git history.

This roadmap does not authorize implementation. Future work should select one
phase/task, reread its owning contracts and obtain normal user direction.

## Priority terminology

- P0: demonstrated current correctness/portability issue.
- P1: high-probability reliability or change-safety risk at a hot boundary.
- P2: maintainability/tooling debt that compounds future work.
- P3: maturity/assurance improvement appropriate after the main seams exist.

## P0 — resolve configuration correctness first

### Q0.1 Auto-select MIDI technology profile

Evidence: shipped config fixes `tech_profile` to Linux and runtime prioritizes
it over platform detection.

Change:

- use `auto`/optional override;
- centralize effective profile selection;
- load the actual shipped config in every platform test.

Proof:

- Windows/macOS/Android never advertise Linux ALSA/OSS by default;
- Linux retains raw/sequencer/OSS capability behavior;
- explicit test override remains deterministic;
- all MIDI tech and package tests pass.

### Q0.2 Add full versioned config validation

Evidence: malformed/misspelled required settings and wrong types are accepted.

Change:

- JSON Schema plus Python domain invariants;
- complete pre-I/O error reporting;
- old-config migration fixtures.

Proof: adversarial cases in the configuration handover all fail with exact
paths; current shipped and user-migrated config passes.

### Q0.3 Remove latent embedded config

Only after loader parity tests and typed runtime config exist, delete the
obsolete `amy_transport.DEFAULT_CONFIG`, deep merge and loader. Replace dynamic
re-export/monkey-patching with explicit composition.

Proof: one default source, every supported entry point resolves identical
runtime values, package smokes unchanged.

## P1 — make failure and thread ownership deterministic

### Q1.1 Queue all MIDI input events through one boundary

Convert reader callbacks to immutable events and queued Qt/application delivery,
including notes. Preserve order and measure latency.

Proof: concurrency tests for note/control order, tuning change and shutdown;
existing performance/native MIDI tests pass.

### Q1.2 Add bounded transport/log queues and health

Specify capacity/overload by command class, coalesce stale low lanes, cap/rotate
logs and surface worker failures.

Proof: stalled adapter tests demonstrate bounded memory, accepted critical
commands have defined outcomes and UI receives terminal failure.

### Q1.3 Make shutdown ordered and owned

No worker may use a resource after close; close is idempotent and bounded.

Proof: blocked I/O and repeated-close tests; no hangs in package tests.

### Q1.4 Bound local service frames

Apply the Windows service's fixed-frame discipline to Unix stream fallback and
test malformed/non-ASCII/unterminated/overlong input.

## P1 — establish safe extraction seams

### Q1.5 Explicit composition root

Remove wildcard import/global assignment behavior in `main.py`. Construct
validated config, adapters, services and QObject facade explicitly.

Proof: alternate test composition uses the same constructors; mypy monkey-
patch errors disappear; entry-point tests remain unchanged.

### Q1.6 Freeze public QML facade contract

Add semantic QObject introspection and behavior tests for intended properties,
signals and slots. Do not freeze private class shape or literal source text.

### Q1.7 Extract pure AMY command/rhythm compilers

Characterize existing command sequences, extract deterministic compilers and
leave framing/priority in adapters.

Proof: byte/sequence parity plus native AMY controls/rhythm tests.

### Q1.8 Extract pure tuning/chord/performance values

Remove MIDI private-field reach through an immutable, intentionally shared
snapshot. Preserve manual versus automatic synth ownership and all tuning
spelling behavior.

## P2 — improve tests and maintainability guardrails

### Q2.1 Replace brittle static tests incrementally

Migrate source-string assertions to behavior, introspection, AST/import and
structured-data checks. Keep narrow architecture assertions where valuable.

Target: every refactor should require fewer spelling-only test edits than the
equivalent behavior change.

### Q2.2 Add lint/type/coverage ratchets

- compile and schema validation;
- selected Ruff rules;
- mypy strict for new pure modules, no-new-errors elsewhere;
- subprocess-aware coverage for navigation;
- selective mutation tests for high-value state machines.

Never create one giant formatting commit mixed with extraction.

### Q2.3 Split giant facade responsibilities

Use the strangler method:

1. delegate preset normalization/application to a service;
2. delegate rhythm planning;
3. delegate MIDI input adapters;
4. delegate binding state;
5. keep a thin compatible QObject facade;
6. remove inheritance layers only when no behavioral override remains.

Measure decreasing method count/private-field reach and files touched per
change, not a desired line count.

### Q2.4 Consolidate QML interaction primitives

Share bindable numeric behavior, section framing, strum pointer normalization
and indicator presentation beneath separate OMNI/MIDI wrappers.

Proof includes multiple-move drag, touch/mouse, echo-during-drag, pitch-bend
center and learn/unlink transitions.

### Q2.5 Consolidate persistence

One atomic/versioned JSON store handles config/presets with validation and
recoverable failure. Domain code owns values, not filesystem policy.

## P2 — data and documentation hygiene

### Q2.6 Remove exact duplicated drum data

Keep canonical runtime files; replace design copies with links and an integrity
manifest. Add provenance/schema/generation notes for large catalogues.

### Q2.7 Correct stale MIDI/platform docs

Make `midi.md` the capability owner, correct `unclear.md`, `INSTALL.md` and
Windows wording, and add document status metadata.

### Q2.8 Classify tools and remove obsolete `tmp_` scripts

Confirm history first. Supported generators/migrations gain contracts/tests;
one-off scripts are removed; diagnostics move to a documented namespace.

### Q2.9 Define screenshot retention

Keep release-identifiable names and semantic validation while preventing
unbounded byte-identical history.

## P3 — release and supply-chain assurance

### Q3.1 Exact release manifest

Publish only the expected five packages and five checksums; fail on extras and
verify final GitHub assets.

### Q3.2 Immutable build automation inputs

Pin GitHub Actions by full SHA; adopt reviewed update automation; resolve and
hash desktop Python release dependencies.

### Q3.3 Provenance and SBOM

Attest package digests/source/workflow and publish dependency SBOMs. Document
independent verification. Do not overclaim security or reproducibility.

### Q3.4 Signing decision

Only after distribution/trust requirements are explicit, add protected Windows,
macOS and Android release signing.

## Suggested branch sequence

Keep branches narrow. An example sequence:

1. `fix/midi-tech-profile-config`
2. `rework/versioned-config-schema`
3. `rework/explicit-composition`
4. `rework/midi-event-thread-boundary`
5. `rework/transport-health-bounds`
6. `rework/pure-command-plans`
7. `rework/domain-state-boundaries`
8. `rework/qml-control-primitives`
9. `rework/test-quality-gates`
10. `automation/release-provenance`

The user may choose a different grouping. Do not merge several phases merely
because they appear in one roadmap.

## Required proof for every phase

- state the public behavior and non-goals before editing;
- cite the exact handover and authoritative subsystem contracts;
- add characterization/failing tests before a correctness fix;
- no unapproved AMY fork protocol/core change;
- preserve OMNI/MIDI ownership and Qt wire-only boundary;
- run affected local suites and full unit tests;
- run the full five-platform release for changes merged to `main`;
- inspect release assets/AMY SHA, not just the top-level green result;
- update authoritative docs and mark superseded analysis where appropriate;
- avoid Codex traces in Shorepine-facing AMY upstream branches.

## Metrics to trend, not game

- supported change scenario: files/components touched;
- large-facade method count and private cross-object accesses;
- mypy baseline error count;
- source-text versus behavioral assertions;
- config consumer fallbacks for required fields;
- unbounded queues/background failures without observers;
- test duration/flaky retry rate;
- release inputs pinned/resolved and assets covered by provenance;
- active-doc contradictions/stale support facts.

No universal complexity or coverage number is a definition of done. A phase is
done when its stated quality scenario is measurably improved and established
behavior remains proven.

## Stop conditions

Pause and re-evaluate if a proposed cleanup:

- changes AMY wire output without a documented behavior requirement;
- combines OMNI and MIDI state ownership;
- reimplements Qt gesture timing in Python;
- requires a framework to support only one implementation;
- turns typed domain objects back into generic dictionaries/events;
- removes native/package tests in favor of mocks;
- expands a branch across several roadmap phases without independent proof;
- cannot explain its user/reliability/modifiability benefit in a concrete
  scenario.
