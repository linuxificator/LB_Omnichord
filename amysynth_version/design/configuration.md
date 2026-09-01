# Configuration contract

Status: authoritative startup configuration contract
Owner: configuration loading, migration and composition
Applies to: shipped and per-user AMY frontend configuration on all platforms
Last verified: 2026-09-01

## Authority and revision

`qt_frontend/config/amy_config.json` is the shipped configuration authority.
It declares `config_revision`; current revision 4 is structurally defined by
`config/schema/amy_config_v4.schema.json`. Historical revisions 1–3 remain
packaged so their contracts are inspectable; the three pattern capacities are
optional there, as are the later MIDI discovery fields and drum-kit identity;
all are required from revision 4 onward. Unknown keys inside stable objects,
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
- contiguous fill/chord/drum-base sequencer-pattern ownership;
- synth defaults, drum kit/gain/sample map, rhythm/performance timing;
- synth programs/patches, optional balance levels and patch corrections;
- debug settings;
- source/default/override/platform provenance.

Production consumers receive only the typed object/sections. `load_amy_config`
remains an explicit external compatibility API and returns a fresh mutable JSON
view; it is not used to construct the application graph. The view preserves the
derived 256-entry Juno/DX7 patch map but cannot mutate typed state or another
view.

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
Revision 2 to 3 adds the previously hardcoded contiguous pattern layout:
fills 0–935, chord one-shots 936–999 and drum bases 1000–1023. Validation
requires these ranges to be contiguous and to end exactly at
`amy_max_patterns`.
Revision 3 to 4 repairs the pattern-capacity contract added after the earlier
revision-3 release: it adds missing `amy_max_patterns`,
`amy_max_pattern_tags` and `amy_max_pattern_instances` values while preserving
any values already present. The same revision completes the portable MIDI
discovery lists and infers the missing drum-kit identity from a recognized
legacy tiny, Gamma9001 or General MIDI sample map; an unknown map fails with a
path-specific error instead of being mislabeled. These are versioned historical
migration values, not runtime fallbacks; structural and domain validation still
reject invalid custom capacities.
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
