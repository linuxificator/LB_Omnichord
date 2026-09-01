# T10 result: explicit config migrations and atomic JSON storage

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: configuration migration and durable JSON persistence
Applicability: shipped/user configuration on every package target

## Outcome

- Added explicit, isolated 0→1 and 1→2 transforms. Missing revision means the
  historically supported revision 0; every transform must advance exactly one
  revision and reports the paths it changed.
- Revision 0→1 changes only the former shipped `voices.rhythm_chord: 4`
  default to 7. Revision 1→2 changes only the former shipped
  `midi_input.tech_profile: linux` default to `auto`. All other configured
  values survive byte-for-value in the decoded document.
- The resolver now migrates in memory before applying the current revision-2
  schema and domain invariants. Old external/headless configurations therefore
  use the same validation and typed conversion as migrated user config without
  requiring a write.
- User config migration validates the complete result before persistence.
  Invalid, future or corrupt files fail clearly and are never silently replaced.
- Added `JsonStore`: JSON is strictly serialized (including rejection of NaN),
  flushed to a private same-directory temporary file, atomically replaced and
  retained as one `.previous` version. A failed final replacement restores the
  old current value; failure messages include the exact target.
- Config seeding now uses this store with mode `0600`. Preset behavior and
  ownership are deliberately unchanged; T19 can reuse the same adapter.
- Shipped config is revision 2. Historical v1 and current v2 schemas are both
  packaged in AppImage and Android staging.

## User-override decision

The current per-user file remains a complete editable config document. T09
provenance already identifies paths that differ from the shipped baseline, but
persisting only those paths now would require a new defaults-plus-overrides
composition contract. Doing that before T11/T12 would silently change the
meaning of existing user files and duplicate the next task's work. T10 thus
persists the migrated full document and makes override-only storage an explicit
later architectural choice, not an incidental migration side effect.

Revision 1 cannot distinguish the old shipped `linux` MIDI default from a user
who deliberately retyped that same value. Portability is the product default,
so 1→2 migrates every such value to `auto`; a diagnostic Linux override can be
reapplied explicitly and is then recorded by provenance.

## Recovery contract

- A successful first write creates only the current private file.
- A successful update places the prior valid document at `.json.previous`.
- An injected failure between moving current and installing the temporary file
  restores current; an abrupt process/filesystem interruption still leaves the
  moved previous document available for manual recovery.
- A corrupt current document raises a path-specific read error while an
  existing previous document remains readable.
- The file is fsynced before replacement. Directory fsync is attempted and is
  best-effort because Windows and some filesystems reject directory handles.

## Verification

- migration fixtures: revision 0→2, revision 1→2, current idempotence,
  malformed/future revisions and non-mutation of input;
- atomic-store fixtures: private mode, previous recovery, corrupt current,
  injected final-replace failure, strict serialization and exact error path;
- resolved config tests: 9 passed;
- user-data/sound-balance tests: 17 passed;
- Android packaging tests: 10 passed;
- quality gate: 58/58 legacy mypy ratchet; five new production modules pass
  strict mypy; all repository guardrails passed;
- complete local suite: all quality, unit, frontend, serial, preset,
  native-control and native-rhythm suites passed.

## Findings and progressive insight

- The former ad-hoc migration swallowed both corrupt input and write errors;
  doing so made an unchanged stale config indistinguishable from success. The
  startup path now fails visibly while retaining the user's bytes.
- Config migration and config resolution need a decoded-document seam. The new
  `resolve_amy_config_data` is that seam and prevents validation from being
  reimplemented in persistence code. T11 can use it for explicit composition.
- `app_core.py` and `midi_player.py` still contain other direct JSON writers.
  Moving those prematurely would combine preset semantics with config rollout;
  T19 remains the owner of that consolidation.
- Recovery is deliberately one version, not an unbounded history. Release/user
  backup policy remains outside the runtime JSON adapter.

## Follow-up task effects

No new queue item is required. T11 must compose typed config and CLI overrides
without mutable monkey-patching. T12 can then remove compatibility fallbacks.
T19 should reuse `JsonStore` for preset persistence only after its ownership
and validation contracts have been characterized.
