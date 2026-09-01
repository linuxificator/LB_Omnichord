# Configuration contract

Status: authoritative startup configuration contract
Owner: configuration loading, migration and composition
Applies to: shipped and per-user AMY frontend configuration on all platforms
Last verified: 2026-09-01

## Authority and revision

`qt_frontend/config/amy_config.json` is the shipped configuration authority.
It declares `config_revision`; current revision 2 is structurally defined by
`config/schema/amy_config_v2.schema.json`. Historical revision 1 remains
packaged so its contract is inspectable. Unknown keys inside stable objects,
missing required values and wrong types are startup errors. Required operational
values must not reappear as consumer fallbacks.

The schema owns structure. Python validation owns cross-field and musical
invariants: unique synth and bus ownership, seven-note chord capacity,
non-overlapping sequencer tag ranges, bus bounds, pattern capacity and known
default synth references. Every error carries a JSON path. Validation finishes
before serial, MIDI, socket or AMY resources are created.

## Resolved representation

`load_resolved_amy_config` returns frozen typed sections for:

- serial transport;
- MIDI input and whether its platform profile is derived or overridden;
- voice and AMY runtime capacities;
- synth, bus and sequencer-tag layout;
- debug settings;
- source/default/override/platform provenance.

Existing consumers temporarily receive a fresh mutable compatibility dictionary
from `load_amy_config`. The view preserves the derived 256-entry Juno/DX7 patch
map but cannot mutate the frozen resolved object or another consumer's view.
T11/T12 move consumers to narrow typed sections and then remove this transition.

## Source and provenance

The shipped file is atomically seeded once to the per-user configuration
directory with private file permissions. The user file has startup priority
and is never silently deep-merged with new defaults. For now it remains a full
editable document: provenance identifies the paths that are true overrides,
but changing storage to an override-only document is deferred until T11/T12
provide an explicit composition seam. That avoids silently redefining existing
user data during migration.

The resolved object records its actual path, source kind, shipped baseline,
changed JSON paths and fields whose final value belongs to a runtime platform
adapter. `midi_input.tech_profile: auto` is platform-derived; an explicit value
is a diagnostic override. Command-line serial port/baud overrides create a new
frozen transport section and are recorded separately as runtime override paths;
they never mutate the validated compatibility document in place.

Revision-by-revision migration runs on an isolated copy before full structural
and domain validation. Only a valid result is atomically persisted. Revision 0
to 1 raises the former shipped four-voice rhythm-chord default to seven;
revision 1 to 2 replaces the former shipped Linux MIDI profile with `auto`.
Because revision-1 full documents cannot distinguish that old default from an
intentional diagnostic selection, a user who deliberately forced `linux` must
reapply it after migration. Future and malformed revisions fail at
`$.config_revision` rather than being guessed.

`JsonStore` writes a flushed same-directory temporary file, replaces the
current document and retains one `.previous` version after successful updates.
If final replacement fails, it restores the previous current document; corrupt
input is reported with its path and is never overwritten. File replacement is
atomic where the host filesystem implements the standard rename contract.
Directory syncing is best-effort on platforms/filesystems that support it.

## Dependency and package rule

Structural validation uses the assessed and exactly pinned pure-Python
`fastjsonschema` package. Schemas are local application resources; remote or
user-supplied schemas are never compiled. Every package must contain the
versioned schema and validator. Adding a schema revision requires its migration
fixture, typed conversion proof and all five package gates.
