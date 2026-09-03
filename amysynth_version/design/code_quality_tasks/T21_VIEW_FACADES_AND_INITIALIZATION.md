# T21 result: incremental view facades and explicit initialization

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: root QML composition and QObject construction lifecycle

## Outcome

- Extracted the complete OMNI title/strum-mode section and strum-note guide
  from `Main.qml` into focused components. Layout inputs are explicit and the
  title component emits `strumModeToggleRequested` instead of invoking global
  backend/MIDI policy itself.
- Retained `Main.qml` as the global window, navigation and MIDI-learn policy
  owner. Existing backend properties, signals, slots and QML context names are
  unchanged.
- Split backend construction from side-effectful initialization. Constructors
  now establish invariants; the single composition root calls idempotent
  `initialize()` only after the complete concrete facade exists.
- Preset storage/loading, derived preset overrides, MIDI binding restoration,
  MIDI-player composition and native MIDI reader startup retain their order but
  no longer rely on virtual dispatch during base construction.
- Marked the actual production integration facade and standalone MIDI facade
  final. The `app_core` and performance inheritance layers were not removed:
  both still provide real, characterized overrides.

## Compatibility and proof

- The frozen QObject meta-object characterization remains unchanged.
- Composition tests prove the same injected graph creates and initializes fake
  backends; AST characterization proves extensible constructors contain no
  `self.method()` dispatch and the production concrete classes are final.
- Static QML contracts now resolve title/note-guide behavior through their
  owning components while preserving exact geometry and semantic backend route.
- Targeted composition, facade, static and native slider suites pass. The full
  local-socket/package suite is deferred until escalation is allowed again; no
  new permission will be requested during the user's 90-minute quiet window.

## Findings and progressive insight

- The old need to initialize subclass fields before `super().__init__()` was a
  symptom of preset loading from a base constructor, not a legitimate domain
  invariant. An explicit composition lifecycle removes that temporal coupling.
- Inheritance is not itself the defect here. The performance layer alters
  preset/reset/snapshot behavior and the MIDI integration layer protects bound
  values, so deleting either would merge responsibilities or duplicate policy.
- Complete visual sections are safer extraction units than scattered controls:
  their inputs and one semantic intent are reviewable, and root-global policy
  remains visible in one place.
- A backend factory protocol should eventually return a typed initialized-port
  interface instead of `Any`. This is a concrete follow-up for the remaining
  mypy debt, not a reason to broaden this QML task.

## Follow-up task effects

T23 can replace the remaining QML source-fragment assertions with component
creation/introspection now that these sections have stable boundaries. Future
facade reduction must preserve the post-construction initialization contract
and may remove an inheritance layer only after its last override is delegated.
