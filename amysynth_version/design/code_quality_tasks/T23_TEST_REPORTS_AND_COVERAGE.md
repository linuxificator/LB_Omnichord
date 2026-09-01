# T23 result: semantic tests, measured coverage and run evidence

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: regression runner and test-quality feedback

## Outcome

- The existing process-isolated test runner now writes one atomic versioned
  JSON report for success and failure. It records every script's stable suite
  name, status, return code and duration plus total duration, repository commit
  and pinned AMY commit.
- Suite artifact directories are prepared once per invocation instead of once
  per script. Later unit scripts can no longer erase diagnostics from earlier
  scripts in the same suite.
- Added optional subprocess-aware branch coverage with parallel data and a
  combined JSON artifact. CI applies it to the unit suite for navigation; no
  global percentage can replace behavior/native/package acceptance.
- Adopted and documented `coverage==7.15.4` as a test-only tool after checking
  current maintenance, Python compatibility, license, subprocess support and
  exit cost. It is never packaged or imported by product code.
- Replaced concrete source-spelling assertions for backend initialization and
  legacy bass references with AST semantic checks.
- Added deterministic transition-sequence properties for the pure MIDI binding
  state machine: bounded/unique visibility, one-to-one binding indexes and
  value-range invariants are checked after every transition.

## Compatibility and proof

- Runner tests prove live child output is retained, failures become structured
  results, durations are recorded, report replacement is atomic and coverage
  wraps rather than collapses each script process.
- A real quality-suite invocation produced a valid report containing the local
  repository SHA and exact AMY release SHA. A second real invocation using
  coverage.py combined parallel/subprocess data and wrote `coverage.json`.
- MIDI binding, refactor characterization and bass catalogue suites pass after
  converting the checks. The quality gate remains green at 37/42 ratcheted
  legacy diagnostics and 24 strict new modules.
- CI uploads the report for every matrix result and the selective unit coverage
  directory even on failure. Existing native/package tests and their process
  isolation are unchanged.

## Findings and progressive insight

- The previous runner recreated a suite artifact directory before every test
  file. In the unit suite this silently discarded earlier failure evidence;
  artifact lifecycle belongs to the suite invocation, not an individual
  script.
- Source parsing is still appropriate for dependency direction and entrypoint
  structure, but AST expresses those rules without depending on whitespace or
  exact statement spelling. Workflow/package text assertions remain where the
  file format has no adopted structured parser and the literal is itself a
  delivery contract.
- Deterministic generated transition sequences provide property feedback
  without adding Hypothesis or a mutation framework. A future mutation tool
  needs its own dependency assessment and should be limited to pure modules
  only if it finds defects beyond these invariants.
- Coverage of the quality suite legitimately reports little product execution;
  this confirms why CI measures the unit suite selectively and why no aggregate
  percentage is useful as a release gate.

## Follow-up task effects

T24 can consume the versioned report metadata when assembling exact release
evidence. Release workflows should include the report and resolved dependency
inputs in their final manifest rather than scraping console text. Additional
source-string migrations should happen only when the owning module exposes a
stable behavioral, introspection, AST or structured-data boundary.
