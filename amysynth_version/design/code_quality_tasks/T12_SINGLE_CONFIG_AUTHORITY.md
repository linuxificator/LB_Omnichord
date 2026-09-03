# T12 result: one typed configuration authority

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: runtime configuration authority and consumer contracts
Applicability: AMY command clients, MIDI engine and all package entrypoints

## Outcome

- Deleted the approximately 199-leaf `amy_transport.DEFAULT_CONFIG`, its
  recursive deep merge and its missing-file fallback loader. The only JSON
  compatibility loader now delegates to schema/domain-validated typed
  resolution and raises on missing files.
- Replaced `amy_serial`'s `vars`/`globals` re-export loop with an explicit,
  documented facade: three program-aware clients, canonical config loaders,
  protocol reset constants and two intentionally private sequencer helpers
  used by regression tests.
- Production composition now passes `ResolvedAmyConfig` directly. It no longer
  constructs or hands a whole mutable compatibility dictionary to command
  clients. The legacy JSON view remains only as an explicit external/test API.
- AMY and MIDI consumers now read transport, debug policy, role/MIDI synth and
  bus ownership, voice/capacity limits, default synths, drum kit/gain/sample
  map, rhythm limits, MIDI input and performance timing from frozen typed
  sections. Required `.get(key, hardcoded_default)` authorities are gone.
- Synth patch maps, synth program definitions, optional instrument balance and
  patch corrections are immutable resolved data with narrow lookup methods.
  Program-aware and MIDI consumers no longer reach into a client config dict.
- Added config revision 3 and explicit 2→3 migration for sequencer pattern
  ownership. Fill patterns own 0–935, chord one-shots 936–999 and repeating
  drum bases 1000–1023. Domain validation requires contiguous ranges ending at
  `amy_max_patterns`; transport derives every pattern ID/capacity from them.
- Historical v1/v2 and current v3 schemas ship in AppImage and Android staging.

## Compatibility and behavior proof

- The compatibility facade still exposes the public program-aware client names
  and canonical loader identity; `app_core` no longer exposes an unused loader.
- Independent tests retain literal 256 tag capacity, tag ranges, 1024 pattern
  capacity, 64 chord-pattern capacity and 936/1000 boundaries. Production
  transport contains none of the old pattern-layout constant names.
- Revision fixtures prove 0→3, 1→3, 2→3 and current idempotence. Invalid gaps,
  overlaps/end mismatch and future revisions fail at exact JSON paths.
- An AST guard rejects `.get` fallbacks for required startup sections in
  transport, program, MIDI and composition consumers and rejects future
  dynamic facade loops/`vars`/`globals` use.
- Sequencer, all 700+ fill definitions, MIDI engine, program handling,
  config-user migration and package schema tests pass with identical command
  expectations.
- Quality ratchet remains 46/46 legacy errors; six new modules pass strict
  mypy.
- Complete local suite: all quality, unit, frontend, serial, preset,
  native-control, and native-rhythm suites passed.

## Deliberately retained defaults

The remaining `.get` defaults in AMY transport are not startup configuration:
they parse optional fields in live rhythm/reverb messages (`chord_events`,
arpeggio direction/rate, bass mode/events, fill order/density and tempo). Those
defaults are protocol/musical semantics characterized by native rhythm tests.
Removing them as “config cleanup” would change accepted wire/application
messages.

Optional per-instrument balance defaults to multiplier 1.0 and absent
per-patch corrections/program entries mean “no override”. These are absence
semantics, not duplicated required values. Individual synth-program object
defaults remain with the program parser until T15 owns typed musical command
plans and deeper program schema.

The numeric 2→3 values remain in `config_migrations.py` intentionally: an
historical migration must know what revision 2 meant. They are not consulted by
revision-3 runtime code and are covered by exact migration fixtures.

## Findings and progressive insight

- The application needed a typed resolved object at the command-client boundary
  before the compatibility dict could disappear; T11 made that change small.
- Pattern capacity was validated but pattern ownership was not configurable.
  Treating only total capacity as typed would have left a second hidden layout
  authority, so revision 3 was necessary rather than another constants module.
- `resolve_program` is now typed, but its extensible inner program objects still
  apply kind-specific defaults. T15 should decide/deepen that schema while
  extracting musical command plans; T12 must not redefine valid custom program
  behavior.
- Legacy callers may still construct a client from a complete dict. The client
  immediately runs that document through the same migration/schema/domain
  resolver; this is compatibility, not an alternate authority.

## Follow-up task effects

No new queue item is added. T13 receives typed MIDI input/layout/capacity data;
T14 receives immutable paths/config; T15 owns deeper synth-program and musical
command-plan typing. The compatibility JSON API can be removed only as a
separately announced public API decision, not as hidden refactoring cleanup.
