# T03 result: tool layout hygiene

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: LB Omnichord maintainers
Applicability: repository tools, test support and packaging boundaries

## Outcome

- Removed `tools/tmp_apply_local_amy.py` and
  `tools/tmp_apply_reverb_motion.py`. Both were one-shot textual patch scripts,
  had no active references and are fully retained by Git commits `b2aff97` and
  `231fad7`.
- Moved the three slider baselines and their QML files to
  `qt_frontend/tools/diagnostics/`.
- Defined diagnostics as read-only, interactive observation tools in the local
  README and updated every invocation.
- Moved the localhost integration-test bridge from production `code/` to
  `tests/support/control_server.py`. Production entry points never imported it
  and PyInstaller includes production modules from explicit entry points, so
  the move removes an ambiguous production-looking module without changing a
  package requirement.
- Added repository checks that reject tracked `tmp_*` tools, require diagnostic
  Python/QML pairs, and keep the control bridge outside production code.

## Verification

- `test_repository_data_hygiene.py`
- `test_packaging.py`
- complete unit suite
- `git diff --check`

The diagnostic applications are GUI tools and are therefore not launched by
headless CI. Their path resolution and Python syntax are checked, while their
manual drag procedure remains documented in `tools/diagnostics/README.md`.

## Findings and follow-up

- `package_smoke.py` remains production-adjacent by design: macOS and Windows
  packaged acceptance dynamically import it. T14 must introduce the platform
  packaging hook seam before reconsidering its location.
- `update_release_screenshots.py` changes repository output intentionally and
  is a release generator, not a diagnostic. T23 should move or classify it when
  hardening release inputs, avoiding a second move now.
- The static repository checks added here should be folded into the unified
  fast quality gate in T05 and the structural policy suite in T23.
