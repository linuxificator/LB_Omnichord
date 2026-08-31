# Codex handover: configuration ownership and DRY analysis

Status: analysis; no behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Desired property

Every operational setting has one authoritative definition, one validated
runtime representation and an explicit migration policy. Tests may repeat an
expected value as an independent oracle; production code must not silently
invent a second default.

DRY means “one source of knowledge”, not “every repeated token is wrong”. A
test that independently expects port 21928 can catch a config regression. A
production reader that hardcodes 21928 while also reading a configured port
creates two authorities and is a defect.

## Current configuration path

The intended path is sound:

1. `config/amy_config.json` is the shipped default.
2. `code/config_loader.py` loads it.
3. `code/user_data.py` creates a per-user copy and applies migrations.
4. clients receive the loaded dictionary.
5. platform packages ship the same source config.

The implementation does not yet consistently obey that path.

## Finding C1 — obsolete embedded configuration remains executable

`code/amy_transport.py` still defines a large `DEFAULT_CONFIG`, `_deep_merge`
and an older loader. The embedded object has approximately 199 leaf values;
the shipped JSON has approximately 117. They disagree on behaviorally relevant
values, including:

- `amy.max_oscs`: embedded 120 versus shipped 336;
- bus names and ownership: obsolete `main`/`percussion` versus the current
  model;
- rhythm capacity naming and values;
- patch-compatibility entries;
- transport and input defaults.

`code/main.py` currently replaces imported loader/client symbols at runtime,
and `code/amy_serial.py` hides three obsolete names from its broad dynamic
re-export. That prevents the normal entry point from using the old loader, but
does not make the old code harmless: direct imports, tests, alternate entry
points and future refactors can still select it.

Severity: high maintainability risk and latent correctness risk.

Recommendation:

- add a characterization test proving all supported entry points use the same
  loader;
- remove `DEFAULT_CONFIG`, `_deep_merge` and the obsolete loader from
  `amy_transport.py`;
- replace the dynamic facade with explicit imports/exports;
- make the loader a constructor dependency rather than a monkey-patched global.

Acceptance: searching production Python finds exactly one default config path
and no dictionary that duplicates it.

## Finding C2 — validation verifies shape, not the operational contract

`config_loader.py` checks required top-level sections, voice dictionaries,
voice capacity and a few catalogue types. Targeted malformed copies were still
accepted when they had:

- no `serial.port`;
- no `buses.drums`;
- misspelled `amy_max_patterns`;
- a string instead of a list for `midi_player.synth_ids`;
- an unknown top-level property.

These failures then move into distant consumers, which often call `.get()`
with their own default. The result can be silent behavior drift instead of an
actionable startup error.

Recommendation: define a versioned JSON Schema for the persisted/shipped
document, supplemented by domain validation that JSON Schema cannot express
cleanly (non-overlapping synth/tag ranges, capacity inequalities, known role
references). JSON Schema 2020-12 explicitly separates core and validation,
making it appropriate for structural constraints while Python retains musical
invariants.

Validation policy:

- reject unknown properties within stable configuration objects;
- allow an explicitly named `extensions` object if future free-form data is
  needed;
- report a JSON path, bad value and expected rule for every error;
- validate fully before opening serial/socket/MIDI resources;
- test the exact shipped file and migrated user files;
- do not allow consumer defaults for required operational values.

Primary reference: [JSON Schema specification](https://json-schema.org/specification).

## Finding C3 — platform profile is incorrectly fixed to Linux

The shipped `config/amy_config.json` contains `"tech_profile": "linux"`.
`_MidiInputTechManager.current_tech_profile` in `code/midi_player.py` gives a
configured value priority over runtime QPA/platform detection. Because the same
config is packaged for every target, a default Windows, macOS or Android build
can advertise/select Linux MIDI technologies.

Existing tests generally pass a profile explicitly, so they do not exercise
the shipped default path. This is a demonstrated configuration/portability bug,
not merely a refactoring preference.

Recommendation:

- make the shipped value `auto` or omit an optional override;
- reserve explicit profiles for test/development overrides;
- derive the effective profile in one function from override plus observed
  platform capabilities;
- add package-level tests that load the unmodified shipped config under each
  target profile.

Acceptance: the same config selects only supported technologies on all five
release targets, while a test override remains deterministic.

## Finding C4 — user config migration is partial

`code/user_data.py` creates a user config once. The current revision migration
only changes the rhythm-chord voice from 4 to 7. It does not generally merge
new required fields from a newer shipped config. A valid old file can therefore
remain structurally old indefinitely, or consumers fill gaps from local
fallbacks.

Recommendation:

- distinguish user preferences from product/platform defaults;
- persist only actual user overrides where feasible;
- otherwise migrate revision-by-revision with an explicit transform and full
  post-migration validation;
- write migrations atomically and retain one recoverable previous version;
- never perform a best-effort deep merge that hides removed or renamed fields.

An effective model is:

```
validated shipped defaults
        + validated platform-derived facts
        + validated user overrides
        = immutable typed runtime configuration
```

The resolved object should record provenance for diagnostic output without
requiring every consumer to know how it was assembled.

## Finding C5 — consumer defaults duplicate authoritative knowledge

Examples include:

- `code/local_amy_service.py` repeating AMY bus/pattern/oscillator capacities;
- `code/amy_transport.py` using many `.get(key, default)` calls for required
  settings;
- MIDI input glob/default settings in `code/midi_player.py`;
- program/drum gain and guard defaults in command-building code.

Not every fallback must disappear. Optional logging paths and transient UI
preferences can have local defaults. Required capacities, bus IDs, synth
ownership, transport endpoints and timing guards must come from the validated
runtime object.

Recommendation: introduce frozen typed configuration sections such as
`AmyCapacityConfig`, `VoiceLayout`, `TransportConfig`, `MidiInputConfig` and
`DebugConfig`. Consumers take only the section they require. Use `Protocol`
interfaces or immutable dataclasses; do not pass the whole nested dictionary
into every subsystem.

## Finding C6 — duplicated constants mix implementation, tests and docs

Pattern ranges such as 936 and 1000 and capacities such as 1024 occur in
configuration, transport constants, tests and documentation. The right policy
is role-dependent:

- configuration/runtime: one typed source;
- derived code: compute from the typed source and validate non-overlap;
- tests: retain carefully selected literal expectations as independent
  compatibility oracles;
- documentation: describe meaning and refer to the config; generate tables if
  exact values are intended to stay synchronized.

Do not replace meaningful names with a generic “constants” module. Group values
with the domain object that owns their invariants.

## Finding C7 — persistence writes are not uniformly atomic

Atomic write patterns occur independently in `app_core.py` and
`midi_player.py`, while user-config migration uses a direct write. This is both
duplication and inconsistent failure behavior.

Recommendation: a small `JsonStore` adapter should own encoding, fsync/replace,
permissions, backup and error reporting. Domain services supply already
validated values. Tests use a temporary-directory implementation of the same
contract rather than copying write helpers.

## Implementation order

1. Add failing tests for C2, C3 and migration from one old fixture.
2. Add schema and a typed resolved configuration without changing consumers.
3. Switch the composition root and one consumer group at a time.
4. Remove required-value fallbacks after each group is typed.
5. Delete the obsolete embedded config and dynamic re-export.
6. Consolidate persistence only after behavior is characterized.

Do not mix this with musical behavior changes. Every commit should be
releasable and should keep existing public config keys through a documented
migration.
