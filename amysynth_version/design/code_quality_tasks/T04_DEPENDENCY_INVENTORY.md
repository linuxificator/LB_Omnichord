# T04 result: dependency inventory and declared groups

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: LB Omnichord maintainers
Applicability: Python dependencies and five-platform build inputs

## Outcome

- Kept the portable runtime authority unchanged: `PySide6>=6.6` and
  `pyserial>=3.5` remain in `requirements.txt`.
- Added explicit desktop-build, test/quality and Android-host requirement
  groups. Existing PyInstaller, PySide6 Android-host and Cython versions moved
  from workflow literals into those groups without an upgrade.
- Changed regression and package jobs to consume their named group and made pip
  caches depend on both the extending file and shared runtime file.
- Added an authoritative dependency contract and a machine-readable direct
  import/component-exception inventory.
- Recorded the LB AMY fork branch, immutable SHA and tiny-bank/native platform
  build ownership as an intentional external-component exception.
- Added a mandatory dated dependency-assessment template for every future
  package proposal.
- Added AST-backed tests proving that the only current third-party import roots
  are `PySide6`, `serial`, `numpy`, `amy` and `c_amy`, and that each is declared
  or covered by the exact AMY component exception.
- Found and fixed one real declaration gap: the native instrument-balance tool
  imported NumPy while relying on AMY to install it transitively. The existing
  locally resolved/current compatible version 2.5.2 is now pinned to the test
  group only and has a dated assessment.

## Verification

- `test_dependency_declarations.py`
- `test_android_packaging.py`
- `test_packaging.py`
- complete unit suite
- local Markdown-link check
- `git diff --check`

No application import or release-target dependency was changed. NumPy's
existing test use is now explicit rather than transitive.

## Findings and follow-up

- The pinned PySide6 distribution supplies its own
  `scripts/requirements-android.txt`; this is an upstream transitive build
  source that exists only after installation. T24 should capture the resolved
  Android host set in artifact provenance rather than duplicating that list by
  hand.
- `requirements-test.txt` intentionally contains no new analyzer yet. T05 must
  assess and pin Ruff/mypy before adding them.
- Workflow actions, runner images, apt packages, Android SDK components and
  AppImage tools are non-Python build inputs. They are now inventoried in the
  dependency contract; T23/T24 must enforce and emit resolved provenance.
- The direct-import scanner currently derives first-party module names from
  repository filenames. T05 should give the check fixtures and explicit
  boundary ownership so a deliberately conflicting module name cannot hide a
  new dependency.
