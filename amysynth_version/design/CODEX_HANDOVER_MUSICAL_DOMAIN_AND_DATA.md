# Codex handover: musical domain and dataset quality

Status: analysis; no musical behavior or dataset changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Boundary rule

Musical intent belongs in LB; generic synthesis, pattern and wire primitives
belong in AMY. Transport adapters should transmit a validated command/plan, not
decide which instruments continue through a fill or how an Omnichord chord is
voiced. QML presents choices but should not implement music theory.

## Strong current domain work

- `BassRiffEvent`/definition and drum rhythm/fill/event models use frozen
  dataclasses.
- Catalogue loaders validate timing, references, coverage and several musical
  invariants at startup/tests.
- `performance_logic.py` already contains pure behavior separated from QML.
- The fill continuation policy is data-driven and remains outside AMY.
- One-shot AMY patterns give each fill/arpeggio note explicit lifetime and
  note-off ownership.
- Tiny, GM and Gamma9001 decisions are documented and tested against pinned AMY
  builds.
- Native tests exercise the actual generated wire stream rather than only
  checking Python model output.

These are the patterns to extend.

## Finding M1 — music theory and runtime/UI state share `app_core.py`

Tuning tables, pitch spelling, note conversion, chord state and QObject/UI
coordination are colocated. This makes pure musical behavior harder to test and
encourages MIDI code to reach into OMNI private fields.

Recommendation: extract pure modules for:

- pitch/reference/tuning conversion;
- chord identity, voicing and note set;
- performance snapshot calculation;
- preset-to-domain normalization.

Inputs and outputs should be immutable values. QObject wrappers translate to
QML properties/signals. Keep user-visible note spelling rules in the owning
design contract and tests; do not “simplify” enharmonic behavior during a move.

## Finding M2 — command compilation contains musical policy

`AmySerialClient` compiles synth parameters and rhythm plans while also owning
transport. `MidiAmyEngine` has a second parameter-command path. Approximate
complexity is high in both `_param_commands_for_synth` and `_param_commands`.

Recommendation:

- one pure AMY parameter compiler for shared synth semantics;
- explicit policy inputs for OMNI versus MIDI rather than copied code;
- one pure rhythm/pattern plan compiler that outputs scheduled wire values;
- transport only handles framing, priority/cancellation and bytes;
- parity tests compare existing and new command sequences before switching.

Do not make the compiler aware of serial sockets or QObjects. Do not move
Omnichord fill-role policy into AMY to share code.

## Finding M3 — catalogue loaders combine too many validation phases

`load_drum_pattern_catalog` has approximate decision complexity 50 and spans
about 163 lines; `load_bass_riff_catalog` is about 42/160. They mix JSON shape,
field conversion, local constraints, cross references and index construction.

Split into:

1. a versioned serialized schema;
2. typed record parsing with precise JSON-path errors;
3. domain invariant validation;
4. immutable catalogue/index construction.

Keep full validation in CI and fail fast at runtime for user/packaged file
corruption. If startup cost later matters, measure it and use a generated,
integrity-checked cache; do not skip validation by assumption.

## Finding M4 — large generated/curated datasets need provenance

Major files include approximately:

- `omnichord_bass_riffs.json`: 82,943 lines / 2.15 MB;
- `rhythms.json`: 31,607 lines / 668 KB;
- synth catalogue JSON: 19,530 lines / 483 KB.

Line count is largely pretty-printing, but manual review and merge conflict
quality are poor without provenance. Every derived catalogue should record:

- source dataset and license;
- generator/script version or documented manual process;
- schema revision;
- stable ordering/format;
- count and integrity summary;
- validation command.

Prefer checking in a compact canonical source plus deterministic generator when
one exists. Do not invent a generator for genuinely hand-curated data merely to
look architectural.

## Finding M5 — runtime drum data is duplicated under design

All nine drum JSON files under the runtime music directory are byte-for-byte
duplicated in `design/rhythm_rework/new_patterns` (verified by SHA-256). This
adds roughly 1.6 MB, creates two apparent edit locations and can make historical
design material look authoritative.

Recommendation:

- keep one canonical runtime dataset;
- let the design handover link to the canonical files and record the commit or
  schema revision it analyzed;
- if historical snapshots are essential, store a manifest/hash or release
  asset, not a second active-looking tree;
- add a repository test that rejects exact duplicate data trees unless an
  explicit allowlist documents why.

## Finding M6 — pattern/tag layout has multiple authorities

Configuration includes tag ranges while transport code also contains numeric
pattern starts and capacities such as chord start 936, drum start 1000,
`max_patterns` 1024, per-pattern event capacity 64 and active instances 32.
Docs and tests repeat selected values.

Create one typed `PatternLayout`/`AmyCapacityConfig` with invariants:

- every allocated range is inside AMY capacity;
- named ranges do not overlap;
- reserved and generated pattern counts fit;
- default upstream AMY capacity versus LB release override is explicit;
- tests retain independent boundary expectations;
- documentation links to or generates a readable allocation table.

The typed layout is LB integration configuration. The generic AMY defaults
remain small and must not acquire Omnichord-specific names.

## Finding M7 — drum mapping expressed as Python data

`drum_gamma9001.py` is a large direct mapping. It may remain Python if it needs
expressions or is easiest to validate there. If it is purely static generated
data, a versioned JSON mapping plus typed loader can improve provenance and
allow tooling to compare Tiny/GM/Gamma9001 coverage.

Before moving it, answer:

- is the file generated or hand curated?
- does Python syntax encode behavior, or only data?
- which tests currently prove every dataset instrument resolves?
- would a move improve editing/review or only change format?

Do not churn a stable mapping without a measurable benefit.

## Musical correctness invariants to preserve

- manual chord synth ownership remains distinct from automatic/arpeggio synth;
- replacing future arpeggio triggers does not shorten an already sounding
  note, and its original note-off still occurs;
- fill muting is finite, per generic tag and chosen by LB continuation policy;
- starting rhythm immediately uses the visible activity selection;
- changing presets/controls does not reset the AMY timebase or stop transport;
- one-shot/loop and `zQ` wire behavior remains compatible with the pinned AMY;
- preset/tuning/riff/rhythm references remain deterministic across platforms;
- dataset ordering does not accidentally change random/selection behavior.

## Property and metamorphic tests

In addition to examples, use generated valid values for pure domain invariants:

- tune then inverse-map remains within a defined tolerance;
- event ordering/serialization is stable;
- every note-on owner produces exactly one eventual note-off or explicit
  all-off under the documented lifecycle;
- switching arpeggio rates only changes future triggers;
- compile-then-parse wire semantics match the input plan;
- all catalogue references resolve and ranges remain disjoint;
- every fill duration bounds all contained events;
- equivalent preset normalization is idempotent.

Use deterministic seeds and retain minimal failing examples. Do not replace
the real native audio/wire tests: properties cover the pure model, native tests
cover integration.

## Acceptance criteria for extraction

- pure musical modules import neither PySide nor transport adapters;
- transport unit tests need no rhythm/fill policy knowledge;
- AMY command sequences remain characterized before/after moves;
- all current catalogue and native rhythm suites stay green;
- exact duplicated data is removed with links/manifests preserving history;
- new data has schema, provenance and validation commands;
- no generic AMY change is introduced solely to simplify LB code.
