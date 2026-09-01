# Configuration contract

Status: authoritative startup configuration contract
Owner: configuration loading, migration and composition
Applies to: shipped and per-user AMY frontend configuration on all platforms
Last verified: 2026-09-01

## Authority and revision

`qt_frontend/config/amy_config.json` is the shipped configuration authority.
It declares `config_revision`; revision 1 is structurally defined by
`config/schema/amy_config_v1.schema.json`. Unknown keys inside stable objects,
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

The shipped file is copied once to the per-user configuration directory. The
user file has startup priority and is never silently deep-merged with new
defaults. The resolved object records its actual path, source kind, shipped
baseline, changed JSON paths and fields whose final value belongs to a runtime
platform adapter. `midi_input.tech_profile: auto` is platform-derived; an
explicit value is a diagnostic override.

Revision-by-revision migration runs before validation. Revision 1 remains the
current accepted revision in T09; T10 owns atomic migration, recovery and the
next revision. Unsupported revisions fail explicitly rather than being guessed.

## Dependency and package rule

Structural validation uses the assessed and exactly pinned pure-Python
`fastjsonschema` package. Schemas are local application resources; remote or
user-supplied schemas are never compiled. Every package must contain the
versioned schema and validator. Adding a schema revision requires its migration
fixture, typed conversion proof and all five package gates.
