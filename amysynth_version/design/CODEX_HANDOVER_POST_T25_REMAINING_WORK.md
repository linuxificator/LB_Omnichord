# Codex handover: post-T25 remaining code-quality work

Status: planned backlog; no implementation authorization
Owner: `rework/code_quality`
Recorded: 2026-09-01
Applies to: follow-up work discovered by the repository-wide audit and T01-T25

## Purpose and count

T01-T25 are complete. This document turns the remaining concrete findings into
an ordered continuation queue while keeping technical implementation separate
from evidence, product and governance decisions.

At the same approximate scope as T01-T25, the remaining queue contains:

- **11 technical implementation tasks** (`T26`-`T36`);
- **4 non-technical or decision-gated tasks** (`D01`-`D04`);
- **15 tasks in total**.

Physical Windows/macOS/Raspberry Pi/Android validation is maintained by the
platform acceptance contracts and is not counted here as code-quality
implementation. Adding missing native MIDI technologies is product feature
work, not a refactoring task, and is also outside this count.

## Rules for every technical task

- Preserve established musical, QML, preset, MIDI and AMY-wire behavior.
- Keep the Qt frontend wire-only and AMY in its separate service/target.
- Keep platform-dependent implementation in imported/injected adapters.
- Add characterization before moving a boundary that is not already covered.
- Make one reviewable commit per task, update its result handover and push the
  work branch.
- Run affected tests, the complete local suite and `git diff --check`.
- A behavior-bearing merge to `main` still requires the complete
  five-platform release gate and normal physical-approval workflow.
- Do not perform a later cleanup early when a preceding extraction will make
  that cleanup smaller or mechanically different.

## Technical implementation queue

### T26 — expose transport failure and recovery state

Surface the existing immutable `TransportHealth` through an application/view
boundary. The UI must distinguish ready, failed and shutdown-timeout states,
report the first terminal error without aborting unrelated input handling and
define whether recovery means reconnect or restart. Do not put retry policy in
byte sinks or QML.

Prerequisites: T16 and T17 (complete).

### T27 — version adapter-scoped MIDI configuration

Replace the legacy common Linux path fields with optional adapter-owned
configuration through an explicit schema revision. Preserve intentional user
path overrides, migrate the old shipped defaults deterministically and keep
portable core/config consumers independent of `/dev` and ALSA details.

Prerequisites: T09, T10, T13 and the current revision-5 migration (complete).

### T28 — continue `InstrumentBackend` service extraction

Apply the strangler pattern to the remaining responsibilities in
`app_core.InstrumentBackend`: voice/performance coordination, preset side
effects, rhythm state and QML presentation. Keep the QObject surface compatible
and extract only complete cohesive collaborators with explicit ownership.

Prerequisites: T06, T11, T15, T18, T19 and T21 (complete).

### T29 — split MIDI performance from the MIDI view model

Move remaining note/voice/row command ownership into a typed
`MidiPerformanceEngine`-style collaborator. Keep the QObject class focused on
view state, semantic intents and signals. Reuse the existing MIDI input port,
binding service, command compiler and immutable OMNI snapshots; do not create a
second state machine.

Prerequisites: T13, T15, T18 and T19 (complete).

### T30 — split AMY runtime state from command submission

Reduce `AmySerialClient`/`amy_transport.py` by separating catalogue/current-
rhythm state selection and plan submission from the already extracted command
scheduler and pure compilers. Preserve complete command records, lane/
generation semantics, quantization and all wire-byte characterization.

Prerequisites: T15-T17 (complete).

### T31 — finish typed ports, retire obsolete inheritance and clear mypy debt

After T28-T30 expose only the narrow interfaces the composition root and view
facades actually require. Replace remaining `Any` ownership boundaries, remove
an inheritance layer only after its last real override is delegated, and lower
the ratcheted legacy mypy inventory from its current nonzero count to zero.
Do not achieve this through broad ignores, casts or an invented service
locator.

Prerequisites: T28-T30.

### T32 — finish QML view-facade and accessibility boundaries

Extract further complete sections from `Main.qml`, route each screen through a
cohesive facade and keep only navigation/global policy at the root. Audit
accessible names/roles, keyboard focus order, non-color state feedback and
mouse/touch/keyboard intent parity. Preserve `BindableSlider` and framework-
native gesture classification.

Prerequisites: T20, T21, T28, T29 and the established real-pointer tests.

### T33 — finish semantic-test migration

After implementation locations stabilize, classify the remaining source-text
assertions and replace spelling/location locks with behavior, QObject/QML
introspection, AST/import rules or structured JSON/YAML checks. Retain literal
text assertions only where the literal itself is a delivery protocol. Do not
weaken native AMY or package acceptance.

Prerequisites: T28-T32.

### T34 — publish capability data and finish tool ownership

Create one structured platform-capability authority that can feed installation
and support-state documentation without generating runtime policy. Finalize
the ownership/location of `package_smoke.py` and the screenshot release
generator: package acceptance remains feature-gated and normal runtime cannot
open a test endpoint.

Prerequisites: T14, T23 and stable view/package hooks from T32-T33.

### T35 — add a deterministic Gamma9001 mapping generator

Generate `drum_gamma9001.py` or an equivalent canonical data file from the
exact pinned AMY manifest/headers. Require byte-stable output, a checked source
commit, complete entry/count comparison and zero musical/wire change. Retain
the reviewed snapshot until the generator proves exact parity.

Prerequisites: current unified Gamma9001 AMY release and T22 provenance.

### T36 — deepen reproducible build-input evidence

Extend release evidence beyond declared constraints to automatically captured
wheel/download hashes, Android/Qt/SDK inputs and relevant runner/system-package
identity where trustworthy machine-readable sources exist. Do not claim
byte-for-byte reproducibility until an actual rebuild comparison proves it;
avoid hand-maintained pseudo-precision.

Prerequisites: T24 and T25 (complete).

## Non-technical and decision-gated queue

### D01 — catalogue authorship and licence/provenance audit

Correct the stale statement in `music/catalogue_provenance.json` that says no
repository-level licence exists: root `licence.txt` does exist. For each
catalogue record whether it is LB-original, theory/style-derived or an
AMY/General-MIDI mapping, and verify that no externally copied sequence or
sample is being relicensed implicitly. Existing catalogues already describe
the bass riffs and fills as original/theory-derived, so this is an evidence
audit, not a presumption that new third-party permission is required.

This task may result only in documentation/provenance corrections. Any actual
third-party rights issue requires owner/legal direction rather than a Codex
licensing decision.

### D02 — public compatibility API lifecycle decision

Decide whether external users still rely on the mutable JSON compatibility
loader/client construction API. If removal is wanted, define deprecation,
release and migration policy first; only then create a separate technical
removal task. Do not remove it as invisible refactoring cleanup.

### D03 — mutation-testing dependency decision

Decide whether mutation testing finds useful defects beyond current
deterministic state-machine/property tests. Any trial needs the normal dated
dependency assessment and should be limited to pure modules. Reject it if
runtime, maintenance or signal-to-noise cost is not justified.

### D04 — distribution and production-signing decision

Define distribution channels, trust/threat model, key owner, secret handling,
rotation/revocation and required physical acceptance for Windows Authenticode,
macOS Developer ID/notarization and Android production signing. Only an
approved decision creates technical signing tasks; CI debug/ad-hoc signing and
Sigstore build attestations are not substitutes.

## Recommended execution order

1. T26 and T27 are bounded independent correctness/portability improvements.
2. T28-T30 establish the remaining large component seams.
3. T31 completes typing/inheritance work only after those seams exist.
4. T32 adapts the view boundary to the thinner application facades.
5. T33 removes brittle tests after source locations stabilize.
6. T34 finishes capability/document/tool ownership on stable boundaries.
7. T35 and T36 are independent data/build-assurance tasks and may follow when
   their inputs are stable.
8. D01 may be performed independently because it should not alter executable
   data. D02-D04 require explicit owner decisions before implementation.

## Not automatically queued

- new CoreMIDI, WinMM or Android MIDI input implementations;
- pixel-perfect visual redesign;
- a universal service locator or UI component;
- production signing before D04;
- mutation tooling before D03;
- byte-reproducibility claims without rebuild evidence;
- AMY or musical behavior changes disguised as code-quality refactoring.
