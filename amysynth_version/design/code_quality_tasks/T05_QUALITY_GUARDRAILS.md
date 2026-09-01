# T05 result: fast structured quality guardrails

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: LB Omnichord maintainers
Applicability: Python, shipped JSON, active documents and dependency workflows

## Outcome

- Added repository encoding/line-ending policy through `.editorconfig` and
  `.gitattributes`, including explicit binary asset treatment.
- Added a non-mutating `quality` suite to the local runner, reusable GitHub
  matrix and complete `all` gate.
- The gate compiles every maintained Python source into a temporary bytecode
  cache and parses all 54 shipped config/instrument/music JSON files while
  rejecting duplicate keys and scalar roots.
- It validates local Markdown links, the active-document metadata manifest and
  every `.md` route in `design/README.md`.
- AST checks prevent direct `amy`/`c_amy` imports outside the local AMY service,
  prevent platform imports/direct platform selection from spreading outside
  declared adapters, and compare all third-party imports with the T04 manifest.
- Workflow checks reject both pinned and unpinned package installs outside a
  declared requirements group or the exact AMY component exception.
- Ruff 0.16.5 checks correctness-critical `E9`, `F63`, `F7` and `F82` rules.
  The two existing composition-time `backend` names in `app_core.py` are the
  only narrow `F821` baseline; no source was formatted.
- Mypy 2.3.1 now has a machine-readable ratchet: 58 current diagnostics across
  file/error-code buckets may only decrease. Every future production module is
  strictly checked rather than added to the legacy baseline. The quality
  implementation itself passes strict mypy.
- Added nine negative fixtures proving syntax, JSON, link, metadata, routing,
  AMY boundary, platform boundary, third-party declaration and workflow drift
  failures.

## Dependency decisions

Ruff, mypy and types-pyserial are pinned in the test-only group and each has a
dated assessment in `design/dependency_assessments/`. None is imported or
packaged by the application. The pyserial stubs match the existing pyserial
3.5 API.

## Verification

- `python tests/run_quality.py`
- `test_quality_guardrails.py`
- complete unit suite
- workflow YAML parse
- `git diff --check`

## Findings and follow-up

- The earlier audit counted 32 mypy errors with the then-available checker.
  The reproducible mypy 2.3.1 configuration reports 58 after following the
  current module graph; this commit does not introduce those runtime issues.
  The exact categorized baseline makes the measurement stable from here.
- `app_core.py`'s two Ruff `F821` findings are consequences of its implicit
  composition/extensions. T11 should remove the root cause and then delete the
  per-file exception.
- JSON validation here is repository-wide structural parsing, not domain
  schema validation. T09 owns configuration schemas and T22 owns catalogue/data
  schemas; both should call the same quality gate after extending it.
- Direct platform APIs are currently limited, but OS policy still lives inside
  `midi_player.py`. The allowlist prevents further spread until T13 extracts
  the adapter.
- T23 should move the active-document policy from a test-local JSON file only
  if a broader repository policy manifest becomes authoritative; do not create
  a second list in parallel.
