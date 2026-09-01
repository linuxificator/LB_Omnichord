# Post-T25 result: repair legacy pattern-capacity migration

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: versioned AMY configuration migration

## Cause and outcome

An existing revision-2 user configuration could migrate its sequencer pattern
ranges to revision 3 but still lack `amy_max_patterns`,
`amy_max_pattern_tags` and `amy_max_pattern_instances`. The first failure hid
three missing portable MIDI discovery fields and a missing drum-kit identity.
The revised v3 schema required those fields, so validation correctly rejected
the incomplete result before it could be persisted. Unit fixtures had been
derived from the current shipped file and therefore accidentally retained the
new fields.

Configuration revision 4 now represents this schema change explicitly. The
3→4 migration adds only missing historical capacities (1024 patterns, 64 tags
and 32 active instances), portable MIDI discovery defaults and a drum-kit
identity inferred from a recognized legacy sample map. This preserves the
Gamma9001 identity of the reported user configuration rather than copying the
current branch's tiny default. Existing values remain authoritative and an
unknown map fails explicitly. No consumer fallback or silent deep-merge was
added. Revision 1–4 schemas remain packaged on every platform.

## History boundary and root cause

The small task commits narrowed the regression to `9fd0cf2` (T08, last commit
without strict configuration validation) and `4f2e034` (T09, first commit with
versioned schemas). T09 described newly added capacity, MIDI-discovery and
drum-kit fields as required in revision 1 even though released user documents
could predate those fields. T10 (`4482a0e`) and T12 (`1ed0182`) advanced those
documents to revisions 2 and 3 without completing the missing historical
fields. T12 therefore did not introduce the missing values, but its 2→3
migration made the incomplete document fail against the revision-3 schema seen
in the reported traceback.

The missed test was also identifiable at this boundary: migration fixtures
were copied from the latest shipped document and had only the field under test
removed. They could not represent a real older document with several later
fields absent. Regression fixtures must start from an actual historical shape
or explicitly remove every field introduced after that revision.

## Proof

One regression fixture removes exactly the three capacity fields from a
revision-3 document, proves the changed paths and values, and resolves the
result through the typed configuration boundary. A second fixture recreates
the reported revision-2 user layout, including all later missing fields. It
proves unrelated overrides survive and that the valid migration is atomically
stored with a `.previous` copy. Kit-specific tests cover tiny, Gamma9001,
General MIDI and explicit rejection of an unknown map. Finally, the reported
user configuration itself was resolved read-only as revision 4 with Gamma9001,
1024 patterns, 64 tags, 32 instances and its custom serial baud unchanged.
