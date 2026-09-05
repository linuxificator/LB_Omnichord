# Configuration contract

Status: authoritative startup configuration contract
Owner: configuration loading, migration and composition
Applies to: shipped and per-user AMY frontend configuration on all platforms
Last verified: 2026-09-05

## Authority and revision

`qt_frontend/config/amy_config.json` is the shipped configuration authority.
It declares `config_revision`; current revision 10 is structurally defined by
`config/schema/amy_config_v10.schema.json`. Historical revisions 1–9 remain
packaged so their contracts are inspectable. The retired pattern capacities
are optional in revisions 1–3 and required in revisions 4–6; revisions 7 and 8
record the sequencer vocabulary transition. The later role-level and OSC
service-discovery fields follow their own versioned schemas.
Unknown keys inside stable objects, missing required values and wrong types are
startup errors. Required operational values must not reappear as consumer
fallbacks.

The schema owns structure. Python validation owns cross-field and musical
invariants: unique synth and bus ownership, seven-note chord capacity,
non-overlapping sequencer tag ranges, bus bounds, group capacity and known
default synth references. Every error carries a JSON path. Validation finishes
before serial, MIDI, socket or AMY resources are created.

## Resolved representation

`load_resolved_amy_config` returns frozen typed sections for:

- serial transport;
- MIDI input and whether its platform profile is derived or overridden;
- portable OSC UDP input;
- desktop OSC DNS-SD advertisement policy and instance name;
- voice and AMY runtime capacities;
- synth, bus and sequencer-tag layout;
- contiguous fill/chord/drum-base sequencer-group ownership;
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
Revision 4 to 5 restores the intended Gamma9001 hosted-release profile. The
exact Tiny sample map published by revision 4 is migrated atomically to the
reviewed Gamma9001 map. Existing Gamma9001 and General MIDI selections are
preserved. A customized Tiny map fails with a path-specific error because
silently translating user-authored timbres would be data loss. The ESP32-P4
firmware remains a separately declared Tiny-bank target; it does not change the
desktop/mobile configuration contract.
Revision 5 to 6 adds the portable OSC input section. Its historical migration
defaults are enabled, IPv4 wildcard address `0.0.0.0` and UDP port 8000. Those
values exist only in the shipped configuration and explicit migration; OSC
consumers receive the frozen resolved section and have no fallback constants.
A revision-6 user may omit the section or its address/port pair to make OSC an
explicitly unconfigured capability; this opens no socket and shows no OSC tech
item. Address and port must either both be present or both be absent.
Revision 6 to 7 retires the experimental pattern vocabulary. It renames
`rhythm.pattern_ranges` to `rhythm.group_ranges`, changes the zero-based
pattern IDs into non-zero sequence-group tags, and renames the three capacity
keys to `amy_max_sequence_groups`, `amy_max_sequence_group_tags` and
`amy_max_sequence_group_executions`. The migrated execution capacity is raised
from the former shipped 32 to 40, matching the exhaustive 34-execution rhythm
overlap proof while retaining headroom. These are explicit migration rules,
not consumer aliases; revision-7 runtime code knows only the group names.
Revision 7 to 8 then migrates that never-released intermediate vocabulary to
the simplified reusable-sequence API. It moves stored definitions into AMY's
single public tag namespace, renames `rhythm.group_ranges` to
`rhythm.sequence_ranges`, and replaces the three group capacity keys with
`amy_max_sequencer_tags`, `amy_max_sequence_events` and
`amy_max_sequence_executions`. The shipped 1280-tag profile covers root lanes,
the large fill reserve, chord children and base percussion without aliases.
Because revision-1 full documents cannot distinguish that old default from an
intentional diagnostic selection, a user who deliberately forced `linux` must
reapply it after migration. Future and malformed revisions fail at
`$.config_revision` rather than being guessed.

Revision 8 to 9 adds explicit perceptual role levels. The shipped bass role
gain balances one bass note against the expected energy of a three-note chord;
instrument-specific envelope and timbre remain separate policy.

Revision 9 to 10 adds `osc_input.advertise: true` and
`osc_input.service_name: "LB Omnichord"` to every existing OSC section. It does
not recreate an OSC section a user deliberately omitted. Both values remain
editable only in JSON. The service name must contain at most 63 UTF-8 bytes and
may not start or end with whitespace. These defaults live in the shipped file
and explicit migration only; the OSC listener and discovery adapter contain no
fallback copy.

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
