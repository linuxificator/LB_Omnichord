# Current architecture and code-quality baseline

Status: authoritative non-regression contract
Owner: application architecture
Applies to: active `amysynth_version`
Last verified: 2026-09-08

The completed quality work established these boundaries:

- `code/main.py` is the sole production composition root.
- The Qt frontend is a wire-only AMY client and never imports or links AMY.
- Platform-specific behavior lives in imported/injected adapters.
- AMY command plans and musical state transformations are pure and immutable.
- Configuration is versioned, schema-validated, migrated and resolved before
  runtime construction; config values have one authority.
- MIDI/OSC readers cross a queued Qt boundary. Integration stimulus runs in a
  separate process and is not packaged as product code.
- Command, logging and delayed-work queues are bounded and expose failure.
- Runtime catalogues are validated, immutable and covered by provenance.
- Release inputs pin an immutable AMY commit and reviewed dependency inputs.
- Ruff/Pyflakes and mypy are regression gates; production mypy debt is zero.
- Mouse, touch and keyboard policy stays in shared Qt primitives rather than
  duplicated platform branches.

Large modules remain candidates for cohesive extraction, but line count alone
is not permission to split them. Every refactor must preserve QML behavior,
wire bytes, musical timing, preset migration and process separation, with
characterization tests added before moving an uncertain boundary.

