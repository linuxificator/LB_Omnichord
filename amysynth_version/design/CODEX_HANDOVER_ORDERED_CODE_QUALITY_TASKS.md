# Codex handover: ordered code-quality implementation tasks

Status: proposed dependency-aware task sequence; no implementation authorized
Recorded: 2026-09-01
Branch: `rework/code_quality`
Source set: all code-quality handovers indexed by `design/README.md`

## Purpose

This handover converts the code-quality analyses into an executable sequence.
The order is chosen to:

- fix demonstrated correctness defects early;
- start with tasks that have few dependencies and low behavior risk;
- add proof before moving responsibilities;
- establish configuration and composition seams before platform/transport work;
- combine changes that would otherwise move the same code twice;
- defer broad UI/domain/release changes until their lower-level contracts are
  stable;
- keep every branch small, reviewable and releasable.

This is a task plan, not approval to implement it. The user selects/authorizes
each implementation task or bounded group. Before implementation, reread the
owning authoritative behavior documents as required by `design/README.md`.

## Scope and interpretation

The task source is the repository-wide code-quality set:

- configuration and DRY;
- architecture boundaries;
- platform adapter boundary;
- dependency selection and reuse;
- Python modularity/types;
- QML/UI architecture;
- musical domain/data;
- tests;
- concurrency/real-time/I/O;
- portability/release/security;
- documentation/repository hygiene;
- the original roadmap and baseline.

Feature-specific handovers such as external controls, bass riffs and rhythm
sequencing remain mandatory behavior references when a task touches them, but
they do not independently add unrelated work to this code-quality queue.

## Sequencing rules

1. A task may start only when its listed prerequisites are complete or the
   task is explicitly rescoped to avoid them.
2. Add characterization/failing tests before a correctness or extraction
   change.
3. Do not mix a mechanical move/format with a behavior change.
4. Do not introduce a temporary abstraction known to be replaced by the next
   task.
5. Keep public QML, presets, MIDI behavior and AMY wire sequences stable unless
   a separate approved requirement says otherwise.
6. Portable core work must follow the platform-adapter and dependency-selection
   handovers.
7. Every dependency added during these tasks needs a dated package assessment
   and five-platform proof.
8. Every behavior-bearing merge to `main` uses the complete release gate.
9. A task is not complete merely because unit tests pass; use the proof listed
   for that boundary.

## Dependency overview

```text
T01-T04 repository truth/inventory
       |
       v
T05 fast automated guardrails
       |
       v
T06 characterization contracts
       |----------------------|
       v                      v
T07 platform-profile fix   T08 bounded wire framing
       |                      |
       v                      |
T09 typed config/schema       |
       v                      |
T10 migration/atomic store    |
       v                      |
T11 explicit composition root|
       |----------------------|
       v
T12 remove legacy config/fallback authorities
       |
       +--> T13 MIDI/platform adapter + thread boundary
       +--> T14 runtime path/package-hook adapters
       +--> T15 pure AMY command/rhythm compilers
                    |
                    v
             T16 transport scheduler/health/bounds
                    |
                    v
             T17 bounded application timing
       |
       v
T18-T22 domain, preset/binding, QML and data extractions
       |
       v
T23-T25 test modernization and release assurance
```

T23 release-input hardening can begin after T04/T05 on a separate branch, but
it is not on the critical application-refactor path. It is listed late to keep
the main execution sequence focused and because release workflow changes have
a large validation cost.

## Wave A — low-dependency truth and hygiene

### T01 — Establish documentation authority and remove known contradictions

Priority: first; documentation-only
Prerequisites: none
Suggested branch: `docs/contract-authority`

Work:

- declare status/owner/applicability on active contracts first;
- make `design/midi.md` authoritative for MIDI input capability;
- correct stale ALSA sequencer claims in `unclear.md`, `INSTALL.md` and the
  relevant Windows wording;
- label historical documents and remove them from active routing where needed;
- update root handoff current-state text without copying subsystem contracts.

Why first: future implementation must not use contradictory support facts.
This changes no code and gives later platform/config tasks one documentation
authority.

Do not yet:

- generate all documentation from config;
- rewrite historical prose;
- change supported platform behavior.

Proof:

- every active routed contract has an explicit status/owner;
- local Markdown links pass;
- no active document says ALSA sequencer is both implemented and future work;
- `git diff --check` passes.

Sources: documentation/hygiene and platform adapter handovers.

### T02 — Canonicalize duplicated drum data without changing runtime data

Priority: early repository hygiene
Prerequisites: T01, so the design snapshot can be labeled correctly
Suggested branch: `rework/canonical-drum-data`

Work:

- retain the runtime drum JSON tree as the single canonical dataset;
- replace the nine byte-identical design copies with links, a manifest and
  recorded hashes/schema/source revision;
- add a structured duplicate-data-tree check with a narrow allowlist;
- verify all existing loaders/tests still read only the runtime location.

Why now: it removes a second edit location before later catalogue/schema work.
No loader format is changed, so T21 can improve schemas later without migrating
two copies.

Do not yet:

- rewrite catalogue formats;
- regenerate hand-curated data;
- change fill/rhythm content or ordering.

Proof: byte hashes/counts of canonical files remain unchanged; drum/native
rhythm suites pass; design links resolve.

Sources: musical domain/data and documentation/hygiene handovers.

### T03 — Classify tools and remove unsupported temporary mutation scripts

Priority: early repository hygiene
Prerequisites: T01
Suggested branch: `rework/tool-layout-hygiene`

Work:

- inspect history/references for `tmp_apply_reverb_motion.py` and
  `tmp_apply_local_amy.py`;
- remove one-off scripts if Git history is sufficient, or rename/document/test
  them under `tools/migrations` or `tools/generators`;
- move slider baseline programs to `tools/diagnostics` with read-only usage
  documentation;
- move test-only control support toward `tests/support` only when packaging
  tests prove it is not included in production;
- add a check rejecting new tracked `tmp_*` tools outside fixtures.

Why now: later architecture and packaging work should not treat accidental
scripts/test support as production dependencies.

Do not yet move `package_smoke.py`; packaged acceptance intentionally uses it
and its platform hook is handled in T14.

Proof: all tool references/packaging paths updated; unit and package-contract
tests pass; diagnostics still launch by documented command.

Sources: Python modularity and documentation/hygiene handovers.

### T04 — Inventory and declare every Python dependency group

Priority: prerequisite for new quality/schema tooling
Prerequisites: none; coordinate with T03 if tool imports move
Suggested branch: `rework/dependency-inventory`

Work:

- map every third-party import in runtime, test, tools and packaging to its
  distribution and owner;
- keep direct portable runtime dependencies authoritative in
  `requirements.txt`;
- create explicit build and test/quality requirement sources rather than
  workflow-only `pip install` literals;
- document the pinned LB AMY branch/SHA/build options as an intentional
  component exception;
- record current platform/toolchain dependency sources without changing
  versions in this task;
- add a dated assessment record for each future proposed package.

Why now: T05 and T09 may need quality/schema libraries. Their selection must
not introduce hidden or unqualified dependencies.

Do not yet:

- upgrade PySide6, pyserial, PyInstaller or AMY;
- add a schema/lint/coverage package merely because it may be useful;
- generate a full release lock before direct dependency intent is clear.

Proof: every current direct import is classified; no dependency is silently
installed by application code; five-platform requirements remain unchanged.

Source: dependency selection/reuse and release/security handovers.

## Wave B — guardrails and behavior proof

### T05 — Add fast, structured quality guardrails without formatting churn

Priority: foundation for every later refactor
Prerequisites: T01 and T04
Suggested branch: `rework/quality-guardrails`

Work:

- add `.editorconfig` and targeted `.gitattributes` for encoding/line endings;
- add `compileall` and shipped JSON parsing/validation smoke;
- add Markdown local-link/status/routing checks;
- add AST/import checks for core-to-AMY, platform and third-party dependency
  boundaries;
- add a workflow dependency-install drift check based on T04;
- establish a selected Ruff baseline and mypy no-new-errors ratchet, using
  strictly checked new modules rather than suppressing the existing 32 errors;
- record tool versions in the declared test/quality requirements group.

Why now: later file moves should be protected by semantic checks. This task
deliberately avoids reformatting existing large files so Git history remains
reviewable.

Do not yet:

- enable a broad formatter over the repository;
- require zero mypy errors;
- add coverage/mutation thresholds;
- replace existing static tests wholesale.

Proof: all existing tests pass; new checks pass on the baseline and fail on
small test fixtures demonstrating each forbidden condition.

Sources: test architecture, Python modularity, platform adapter and dependency
selection handovers.

### T06 — Add characterization contracts for the boundaries that will move

Priority: mandatory before behavior-bearing refactors
Prerequisites: T05
Suggested branch: `tests/refactor-characterization`

Work:

- introspect/freeze the intended public QObject property/signal/slot surface;
- prove every supported entry point uses the same config loader and resolved
  values;
- load the unmodified shipped config under all five platform profiles;
- characterize current MIDI tech/status presentation and event normalization;
- characterize representative OMNI/MIDI synth-parameter and rhythm/fill/
  arpeggio AMY command sequences semantically and, where part of protocol
  compatibility, byte-for-byte;
- characterize transport priority/cancellation, close and current error paths;
- preserve the slider multi-move/echo/manual-unlink regression tests;
- prefer behavior, introspection, AST and parsed data over source-string tests.

Why now: T07 onward changes actual startup/config/platform/transport paths. The
tests define what stays identical and let later tasks remove brittle literal
assertions instead of editing them to fit each move.

Do not yet change platform selection, configuration or runtime behavior.

Proof: new tests fail against deliberately altered fixtures/fakes and pass
against current production; complete local suite passes.

Sources: test, QML, configuration, architecture, musical and external-control
handovers.

## Wave C — small demonstrated correctness fixes

### T07 — Fix shipped MIDI platform-profile selection through the future seam

Priority: P0 demonstrated portability defect
Prerequisites: T06
Suggested branch: `fix/midi-tech-profile-config`

Work:

- remove Linux as the ordinary shipped runtime default;
- make an explicit profile an override for tests/diagnostics only;
- create one small effective-profile/capability resolver intended to become
  the adapter selection seam in T13;
- keep QML capability/status semantics unchanged;
- run the real shipped config in every package-profile test.

Why before the full adapter refactor: it fixes a current release defect with a
small seam that T13 will retain rather than rewrite.

Do not yet move MIDI reader classes or implement CoreMIDI/WinMM/Android MIDI.

Proof: Linux selects Linux capabilities; Windows/macOS/Android do not probe or
advertise Linux technologies by default; explicit overrides remain stable; all
MIDI/package tests pass.

Sources: configuration, platform adapter and portability handovers.

### T08 — Introduce one bounded local AMY wire-frame parser

Priority: small reliability/defense-in-depth fix
Prerequisites: T06
Suggested branch: `fix/bounded-local-wire-frames`

Work:

- define one maximum LF-framed AMY wire request length;
- create a small portable framing/parser helper with explicit ASCII,
  termination and `Z` validation;
- use it in the Unix stream fallback/service while preserving packet IPC;
- align wrapper tests with the already bounded Windows service behavior;
- fuzz or table-test empty, split, combined, non-ASCII, overlong and
  unterminated input.

Why now: it removes an unbounded buffer with a reusable helper that later
transport adapters keep. It is independent of typed config/composition.

Do not alter valid AMY wire contents, command ordering or service ownership.

Proof: valid existing streams are identical; malformed input is bounded and
rejected deterministically; socket/native tests pass.

Sources: concurrency/I/O, architecture and security handovers.

## Wave D — configuration before composition

### T09 — Add versioned schema and immutable typed resolved configuration

Priority: critical architecture prerequisite
Prerequisites: T04, T05 and T06; T07 should be merged so schema reflects `auto`
Suggested branch: `rework/versioned-config-schema`

Work:

- assess/select a mature five-platform schema-validation package rather than
  recreating a full validator, unless the dated dependency decision rejects
  every candidate;
- define versioned structural schema for shipped/user config;
- add Python domain invariants for ranges, roles, bus/synth ownership and
  capacities;
- report all errors with exact paths before opening I/O;
- convert validated data to frozen typed sections (`TransportConfig`,
  `MidiInputConfig`, capacities/layout, debug and related values);
- record provenance of shipped defaults, platform-derived facts and user
  overrides;
- keep current consumers temporarily fed from a compatibility view.

Why before composition: the future root and adapters need stable typed inputs.
Removing fallbacks first would break old user configs and force rework.

Do not yet:

- delete the embedded legacy config;
- convert every consumer in one commit;
- change musical capacities/defaults;
- silently deep-merge unknown old fields.

Proof: all adversarial config cases fail before I/O; shipped and old fixtures
resolve deterministically; exact current effective behavior remains unchanged.

Sources: configuration/DRY, dependency selection, Python typing and musical
layout handovers.

### T10 — Implement revision migrations and one atomic JSON store

Priority: prevents typed-config rollout from breaking existing users
Prerequisites: T09
Suggested branch: `rework/config-migrations-json-store`

Work:

- define explicit revision-by-revision user-config migrations;
- decide/persist only true user overrides where feasible;
- add a small atomic `JsonStore` for config/preset writes with replace,
  permissions, recoverable previous version and clear errors;
- migrate first, then validate fully through T09;
- add interrupted/corrupt/old-version fixtures;
- adopt the store for config first; leave broader preset service extraction to
  T19 while sharing the same tested adapter.

Why before composition/removal: all supported user files must survive when
required consumer fallbacks disappear.

Do not combine this with preset semantics or UI changes.

Proof: every supported old fixture reaches the exact expected typed config;
failed writes retain recoverable data; current presets/config behavior passes.

Sources: configuration/DRY, architecture and test handovers.

## Wave E — explicit construction and single authorities

### T11 — Replace runtime monkey-patching with one explicit composition root

Priority: prerequisite for clean adapters/services
Prerequisites: T09, T10 and T06
Suggested branch: `rework/explicit-composition`

Work:

- make one identical `main` composition path construct typed config, command
  client, services and QObject facade explicitly;
- replace wildcard/global assignment seams in `main.py`;
- construct the same graph with fake ports in tests;
- preserve the current public entry point, QML context properties, startup
  order and package-smoke checkpoints;
- define narrow protocols only where an actual dependency is injected.

Why now: platform, command and domain extractions need a stable place to supply
collaborators. Doing those moves first would create temporary factories/globals.

Do not yet split the giant facade or move all platform code.

Proof: public entrypoint/QObject/QML characterization stays green; mypy
monkey-patch/redefinition errors disappear; all package entrypoint tests pass.

Sources: architecture, Python modularity and platform adapter handovers.

### T12 — Remove obsolete config code and required-value fallback authorities

Priority: completes the configuration source-of-truth transition
Prerequisites: T11, T09 and T10
Suggested branch: `rework/remove-legacy-config`

Work:

- delete `amy_transport.DEFAULT_CONFIG`, its deep merge and obsolete loader;
- replace dynamic `amy_serial` re-export with an explicit compatibility API or
  remove it after call-site migration;
- move consumers from whole dictionaries/local required defaults to typed
  config sections, one coherent group per commit;
- derive pattern/tag layout through one validated typed owner;
- retain independent literal expectations in compatibility tests;
- verify every supported entry point resolves the same values.

Why after T11: deleting globals before explicit construction would merely
replace them with another temporary import hack.

Do not remove optional UI/logging defaults that are genuinely local and
documented.

Proof: production search finds one config authority; no required capacity,
bus, synth, endpoint or timing value has a second production default; all
native/package behavior stays green.

Sources: configuration/DRY, Python modularity and musical data handovers.

## Wave F — platform and I/O seams without double-moving code

### T13 — Extract MIDI platform adapters and fix the note thread boundary once

Priority: P1 correctness plus platform separation
Prerequisites: T07, T11, T12 and T06
Suggested branch: `rework/midi-platform-event-boundary`

Work:

- define immutable normalized `MidiInputEvent` values and small
  `MidiInputPort` lifecycle/capability contract;
- move ALSA raw/sequencer discovery/readers out of `midi_player.py` into Linux
  adapters;
- isolate CoreMIDI/WinMM/Android unavailable/future adapters behind the same
  capability contract;
- deliver notes, CCs, buttons and activity through one ordered queued
  QObject/application boundary;
- preserve labels/LED/activity semantics and explicit profile overrides;
- add shared adapter contract tests and platform package selection tests.

Why combined: moving readers and later changing their callback/thread model
would touch the same code twice. This task performs one extraction into its
intended final event/lifecycle contract.

Do not implement new native MIDI backends in this task.

Proof: portable core imports/probes no native MIDI API or `/dev`; no QObject is
called directly from a reader thread; event order/latency/close tests and all
MIDI package tests pass.

Sources: platform adapter, concurrency, MIDI behavior and dependency selection
handovers.

### T14 — Extract runtime paths, diagnostics and packaged test hooks

Priority: completes major platform-code removal from `app_core.py`/`main.py`
Prerequisites: T11 and T12; can run parallel with T13 on a separate branch
Suggested branch: `rework/runtime-platform-adapters`

Work:

- introduce small resolved runtime-path, diagnostics and package-test-hook
  values/ports;
- move Android private socket/marker logic out of `app_core.py`;
- move Windows windowed-console/fatal package handling to its launcher adapter;
- move Linux/XDG-specific diagnostics behind a diagnostics adapter;
- leave platform launchers/native services in packaging;
- add AST enforcement for the now-portable core module set.

Do not create a large `PlatformServices` locator or change the Qt/service
two-process boundary.

Proof: identical core imports on all platforms; Android/Windows/package smokes
unchanged; source tests reject platform branches outside the resolver/adapters.

Sources: platform adapter, architecture and release handovers.

### T15 — Extract pure AMY parameter and rhythm plan compilers

Priority: separates musical/application policy from transport before writer work
Prerequisites: T06 and T12; composition T11 supplies them explicitly
Suggested branch: `rework/pure-command-plans`

Work:

- extract deterministic parameter-command compilation shared by OMNI/MIDI where
  semantics truly match;
- extract rhythm/pattern plan compilation from `AmySerialClient`;
- use typed inputs and validated command/scheduled-command outputs;
- keep explicit OMNI/MIDI policy inputs rather than boolean-heavy universal
  behavior;
- leave byte framing, queues and cancellation in transport until T16.

Why before writer extraction: it prevents the new transport adapters from
retaining musical/rhythm responsibilities and avoids moving those methods
twice.

Proof: characterization command streams and native AMY control/rhythm suites
match; pure tests import no PySide, serial or socket modules.

Sources: musical domain, Python modularity and architecture handovers.

### T16 — Compose one scheduler with concrete sinks, bounded health and shutdown

Priority: P1 reliability and final transport adapter shape
Prerequisites: T08, T11, T14 and T15
Suggested branch: `rework/transport-health-bounds`

Work:

- replace inheritance from concrete serial writer with one priority/lane
  scheduler composed with serial, Unix and QLocalSocket byte sinks;
- define bounded lane capacities and distinct overload behavior for critical
  versus replaceable work;
- expose lifecycle, terminal failure, queue depth/high-water and drop/coalesce
  diagnostics;
- make close idempotent, ordered and unable to close a resource used by a live
  worker;
- bound/rotate the debug log and make logging loss visible without blocking
  musical output;
- preserve QLocalSocket thread ownership and all command ordering.

Why combined: scheduler extraction, capacity and failure state all determine
the sink contract. Implementing unbounded “clean” adapters first would create
another transition.

Proof: stalled/failing/blocked/repeated-close contract tests; no accepted
safety-critical command silently disappears; full serial/socket/native/package
tests pass.

Sources: concurrency/I/O, architecture, platform and Python handovers.

### T17 — Replace per-event `threading.Timer` creation with bounded scheduling

Priority: P1/P2 resource predictability
Prerequisites: T06 and T16; T15 clarifies AMY-owned musical scheduling
Suggested branch: `rework/bounded-application-scheduler`

Work:

- classify every current delayed action as AMY musical time, Qt presentation
  time or application scheduling;
- move precise musical note timing to existing AMY scheduled commands where
  behavior permits;
- keep visual timing on `QTimer` in the Qt thread;
- provide one bounded monotonic application scheduler for remaining work;
- preserve generation/cancellation and original note-off timing.

Proof: no unbounded timer-thread creation; arpeggio rate changes and preview/
strum/chord releases keep their characterized lifetime; timing/load tests pass.

Sources: concurrency, musical domain, QML and external-control handovers.

## Wave G — domain and UI extraction on stable foundations

### T18 — Extract pure tuning, chord and performance snapshots

Priority: removes private OMNI/MIDI coupling
Prerequisites: T11, T12, T13 and T15
Suggested branch: `rework/domain-state-boundaries`

Work:

- extract pure pitch/reference/tuning, chord identity/voicing and performance
  snapshot values;
- expose only intentionally shared immutable OMNI context to MIDI;
- remove MIDI reach into OMNI private fields;
- preserve enharmonic spelling, synth ownership and note lifetime.

Proof: property/example tests plus existing tuning/chord/native suites; pure
modules import no PySide/transport; mypy `Any`/private reach decreases.

Sources: musical domain, architecture, Python and tuning behavior contracts.

### T19 — Extract preset normalization and MIDI binding service

Priority: stabilizes state before QML consolidation
Prerequisites: T10, T18 and T06
Suggested branch: `rework/preset-binding-services`

Work:

- extract typed preset normalization/application plan from the 390-line method;
- use the T10 JSON store without changing preset ownership;
- make MIDI learn/bind/unlink/takeover one explicit state machine with immutable
  presentation state;
- retain separate OMNI/MIDI persistence and coupling semantics;
- remove color-driven policy from QML-facing transitions.

Proof: migration/preset/binding transition tests, hidden-control behavior and
all external-control use cases remain green.

Sources: QML, Python, architecture, configuration and external-control
handovers.

### T20 — Consolidate focused QML interaction primitives

Priority: UI DRY after backend semantics are stable
Prerequisites: T06 and T19
Suggested branch: `rework/qml-control-primitives`

Work:

- share bindable numeric interaction, indicator rendering, section framing and
  strum pointer normalization beneath separate OMNI/MIDI wrappers;
- keep stable native Qt delegates and `Slider.moved` intent;
- derive handle/fill from one invertible mapping/`visualPosition`;
- preserve pitch-bend center, manual unlink and backend echo behavior;
- add focus/accessibility names/roles where verified without visual redesign.

Do not create a boolean-heavy universal control or merge OMNI/MIDI policy.

Proof: multi-move mouse/touch, echo-during-drag, inverted/pitch-bend, learn/
unlink, screenshot and package pointer tests pass on all targets.

Sources: QML/UI and external-control handovers.

### T21 — Reduce root QML and QObject facades incrementally

Priority: larger maintainability step
Prerequisites: T18, T19 and T20
Suggested branch: `rework/view-model-facades`

Work:

- extract complete screen/section components and semantic signals from
  `Main.qml`;
- delegate coherent responsibilities from the giant QObject backends to the
  services already created;
- keep the characterized public facade during migration;
- remove an inheritance layer only when no behavioral override remains;
- never call an overridable method from a constructor.

Proof: public QML introspection and every behavior/package test stay stable;
method/private-field reach and files touched per change decrease.

Sources: architecture, Python and QML handovers.

### T22 — Version catalogue parsing and record data provenance

Priority: data maintainability after the config/schema approach is proven
Prerequisites: T02, T09 and T18; can partly run parallel after these
Suggested branch: `rework/catalogue-schema-provenance`

Work:

- split drum/bass catalogue loading into schema parse, local validation,
  cross-reference invariants and immutable index construction;
- reuse the approved schema dependency/approach from T09;
- record source/license/generator or manual process/schema/count/hash;
- decide the Gamma9001 mapping format only after determining whether it is
  generated data or behavior;
- preserve stable ordering and all musical content.

Proof: adversarial/property/catalogue/native rhythm/audio tests; generated
outputs deterministic; no second runtime dataset authority.

Sources: musical data, dependency selection and test handovers.

## Wave H — continuous test modernization and release assurance

### T23 — Replace brittle source tests and add measured coverage selectively

Priority: continuous, finalized after major seams exist
Prerequisites: T05 and T06; migrate checks alongside each earlier task
Suggested branch: `rework/test-quality-gates`

Work:

- replace source-string assertions with behavior, introspection, AST/import and
  structured-data checks as the owning code moves;
- add subprocess-aware coverage for navigation, not a vanity total;
- add deterministic property/mutation tests only for high-value pure state
  machines/config/command plans;
- emit machine-readable suite result/duration metadata;
- retain real native/package tests.

Why not first as a wholesale rewrite: many static tests describe current file
shape. Replacing all before seams are known wastes work; replace each when its
semantic boundary becomes explicit.

Proof: fewer spelling-only edits per refactor, no loss of behavioral/native
coverage, no global ignore or flaky retry masking product failures.

Sources: test architecture and all subsystem handovers.

### T24 — Make release inputs and outputs exact

Priority: supply-chain/reproducibility foundation
Prerequisites: T04 and T05; may run independently after them
Suggested branch: `automation/exact-release-inputs`

Work:

- resolve/pin/hash desktop Python build/runtime inputs through declared files;
- pin GitHub Actions to verified full commit SHAs;
- add reviewed update automation;
- centralize repeated AMY checkout/SHA identity verification without hiding
  platform-specific acceptance;
- create an exact five-package/five-checksum release manifest and fail on
  extra/missing files;
- record resolved dependencies, licenses, source and AMY SHA.

Do not claim byte-reproducible builds without bit-identical evidence.

Proof: dependency/workflow drift tests, complete five-platform release, exact
final GitHub asset verification.

Sources: dependency selection and portability/release/security handovers.

### T25 — Add provenance/SBOM, then decide retention and signing separately

Priority: final maturity step
Prerequisites: T24
Suggested branch: `automation/release-provenance`

Work:

- generate and verify build provenance attestations for release packages;
- generate SPDX/CycloneDX SBOM evidence;
- document independent hash/attestation verification;
- define screenshot retention while keeping release-identifiable names and
  semantic screenshot sanity;
- make a separate distribution/threat decision before Windows/macOS/Android
  production signing.

Signing is not automatically part of this task; it requires protected keys,
distribution intent and explicit approval.

Proof: released artifacts trace to source/workflow/dependencies and verify with
documented commands; screenshot history has a deliberate retention rule;
attestations are not described as proof of vulnerability absence.

Sources: release/security and documentation/hygiene handovers.

## The first ten tasks, compact checklist

The minimum initial queue is therefore:

1. T01 documentation authority/contradictions;
2. T02 canonical drum data;
3. T03 tool/test-support hygiene;
4. T04 dependency inventory and declared groups;
5. T05 fast structured guardrails;
6. T06 characterization contracts;
7. T07 MIDI platform-profile correctness fix;
8. T08 bounded local wire framing;
9. T09 versioned/typed configuration;
10. T10 config migration and atomic JSON storage.

Only after those ten should the explicit composition root and the larger
platform/transport/domain/UI extractions start. T01-T04 may be implemented on
separate branches with limited overlap, but they should be integrated before
T05 establishes the definitive gates.

## Global proof and release policy

For every task:

- run affected unit/integration suites;
- run the complete unit suite;
- run `git diff --check` and structured docs/import/dependency checks;
- update the owning authoritative contract and task status;
- commit only task-scoped changes;
- push to the LB fork work branch.

For behavior-bearing changes merged to `main`, run/follow the complete six-
suite, five-platform release. Documentation-only and explicitly approved
metadata-only merges follow the existing `skip-rebuild` contract; do not use
that marker to avoid validation of code, config, tests, packaging or workflows.

## How to maintain this list

- Mark tasks complete with commit/release evidence; do not rewrite history as
  if findings never existed.
- If a task reveals a new prerequisite, insert it before dependent work and
  state why.
- If implementation proves two tasks touch the same code and contract, merge
  them only when doing so reduces total transition states and remains
  reviewable.
- If a proposed task changes user behavior, split that decision from the
  quality refactor and obtain explicit approval.
- Do not automatically implement the next task merely because the previous one
  completed.

## Stop conditions

Pause and request direction if the sequence would:

- require a platform dependency that fails the dependency-selection policy;
- change AMY wire or musical behavior without a separate requirement;
- temporarily fork core code by platform;
- delete user config before migration proof;
- move code before its public behavior is characterized;
- replace native/package tests with fake-only tests;
- create a service locator/framework instead of small explicit ports;
- combine several waves into an unreviewable rewrite;
- run work that a later already-planned task will knowingly discard.
