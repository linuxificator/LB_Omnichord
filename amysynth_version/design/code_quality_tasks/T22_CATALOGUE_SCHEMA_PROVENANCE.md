# T22 result: versioned catalogues and recorded provenance

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: musical catalogue loading and evidence

## Outcome

- Added versioned JSON Schemas for the bass-riff catalogue, activity timing,
  fill timing, fill continuation policy and drum-kit role maps. The runtime
  reuses the already approved and shipped `fastjsonschema` dependency.
- Split bass/drum loading into visible phases: schema parse, local musical
  validation, cross-reference/capacity validation and immutable index
  construction. No second in-memory mutable catalogue authority remains after
  construction.
- Added `music/catalogue_provenance.json` with a byte hash, reviewed count,
  schema and known creation process for all ten executable bass/drum JSON
  catalogues.
- Preserved every musical asset byte, item order, identifier and mapping. Only
  loaders, schemas, evidence and tests changed.
- Retained `drum_gamma9001.py` as a 121-entry Python snapshot. Repository
  history identifies the pinned AMY source but contains no deterministic
  generator, so a format-only migration would create churn rather than
  reproducibility.

## Compatibility and proof

- The provenance test verifies all ten committed SHA-256 values, counts and
  schema routes and detects both content and cardinality drift.
- An adversarial wrong-version catalogue proves failure at the named schema
  boundary with a source path and JSON location.
- Bass and drum tests prove top-level and nested indexes reject mutation after
  construction while existing coverage, timing, transposition and all three
  kit resolutions remain unchanged.
- Packaging contracts prove Linux, Raspberry Pi, macOS, Windows and Android
  copy/stage the full `music` tree, including schemas and provenance.
- Strict mypy passes for both new pure modules. The targeted catalogue and
  packaging suites pass. Socket/native audio suites were not required by this
  data-only change and were not run during the user's no-approval window.

## Findings and progressive insight

- Existing source citations describe inspiration, but neither those citations
  nor the repository currently establish a redistributable third-party data
  license. The manifest records that evidence gap; it must be resolved before
  claiming complete dataset licensing.
- A hash is review evidence, not a runtime data source. Runtime parses the
  canonical JSON directly; the manifest neither regenerates nor overrides it.
- JSON Schema is useful for version and structural errors, while musical
  relationships such as catalogue coverage, allowed timing and AMY's 64-event
  capacity remain clearer as named domain validators.
- Stable JSON order is preserved by retaining source arrays and explicitly
  sorting only indexes whose previous public contract was already sorted.

## Follow-up task effects

T23 can use the pure validators and immutable indexes for deterministic
mutation/property cases instead of source-fragment tests. A future dataset
provenance task should resolve the licensing evidence and introduce a checked
Gamma9001 generator only if AMY exposes a stable source format suitable for
byte-identical regeneration.
