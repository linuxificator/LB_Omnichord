# T19 result: preset and MIDI-binding services

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: preset normalization/persistence and MIDI binding state presentation

## Outcome

- Added pure frozen preset values and `compile_omni_preset_plan()`. Chord rows,
  volume/effect bounds, legacy reverb fields, rhythm selection/settings/fills
  and tuning now normalize without Qt, I/O or application mutation.
- Reduced OMNI preset application from an embedded normalization procedure to
  a coordinator that preserves live state, compiles a plan, applies it in the
  characterized order and loads synth-role data through its existing owner.
- Added `MidiBindingService` around the existing explicit
  `MidiControlState`. It owns locking, persisted-entry normalization,
  per-screen replacement/serialization and detached immutable presentation.
- Retained separate OMNI and MIDI preset files and coupling rules. Hidden
  bindings, one red learn target, one-to-one takeover, single-click unlink and
  manual-move unlink remain state-machine behavior rather than color policy.
- Replaced both local preset-write implementations with the recoverable atomic
  T10 `JsonStore`; no third persistence authority remains in these facades.

## Compatibility and proof

- Direct pure tests cover defaults, invalid catalogue references, inversion
  wrapping, bounds, legacy effects, fill deduplication/filtering/density and
  tuning conversion.
- Binding-service tests cover CC, pitch bend and note-button persistence,
  invalid-entry rejection, OMNI/MIDI screen isolation and detached immutable
  presentation. Existing binding-transition tests retain hidden-control and
  external-control behavior.
- The complete quality gate passes at 37/42 legacy mypy errors and 22 strict
  modules. Both new modules pass strict mypy.
- The complete behavior runner passes through every unit, Qt pointer, package,
  transport and sequencer test with exit code 0.

## Findings and progressive insight

- Preset normalization and application are distinct responsibilities. Keeping
  the side-effect coordinator in the owner protects live chord/rhythm state
  while making malformed-data behavior independently testable.
- The binding machine was already explicit; duplicating it in a new service
  would have created competing transition authorities. The useful extraction
  is persistence/presentation around that machine, with frozen snapshots at
  the QML boundary.
- The full suite found one test coupled to the old source location of
  `strum_mode` normalization. It was changed to an AST boundary check while
  the pure behavior is proven in `test_preset_plan.py`. T23 should continue
  replacing source-location assertions as their owning code moves.
- Atomic durability belongs below preset ownership. Sharing `JsonStore` removes
  duplicated filesystem mechanics without combining OMNI and MIDI semantics.

## Follow-up task effects

T20 may consolidate focused QML primitives against semantic binding state and
manual-move intent, without moving learn/unlink policy back into QML. T21 can
reduce QObject facades only after preserving this coordinator ordering and the
public properties/signals. T23 should classify the remaining source-string
tests before changing implementation locations.
