# Codex handover: source-checkout local runtime bootstrap

Status: implemented and covered by source contracts; fresh Pi checkout test
pending
Recorded: 2026-09-06
Branch: `fix/raspberrypi-appimage-runtime`

## Problem

`run_local.sh` previously searched for a frontend `.venv` and then an external
repository-neighbour `../omnichord-env`. A fresh Git clone therefore did not
run without undocumented machine state. It also accepted any installed
Gamma9001-looking `c_amy` because it could check symbols but not prove which
pinned source produced the binary.

## Decision

The source-only launcher now owns an idempotent developer bootstrap:

- default Python environment: `<clone>/.venv`;
- default managed AMY checkout: `<clone>/.amy/<pinned-commit>`;
- both locations are ignored by Git;
- explicit `OMNICHORD_VENV` and `OMNICHORD_AMY_ROOT` still override them.

On first run, `run_local.sh` creates the venv, installs the authoritative
`requirements.txt`, checks out the exact AMY release commit, builds it with the
declared Gamma9001 bank and starts the unchanged two-process socket runtime.

On subsequent runs it first asks pip to resolve the requirements with
`--dry-run --no-deps --no-index`. This verifies installed versions against the
real requirement files without contacting a package index. It also runs `pip
check`. Installation occurs only if that offline verification fails.

AMY installation records `<commit>:<bank>` plus the SHA-256 digest of the
compiled extension. Startup verifies the stamp, current binary digest and both
Gamma9001 symbols. A missing, changed or differently pinned extension is
rebuilt through `prepare_local_amy.sh --checkout` before either process starts.
Using a commit-named checkout avoids mutating or sharing a branch checkout when
two LB clones pin different AMY releases.

## Architecture boundary

This is not runtime package management inside the Omnichord application. It is
a source-development shell launcher, before either product process exists.
The Qt process remains wire-only and never imports AMY. The AppImage, DMG,
Windows zip and Android APK continue to embed their complete tested runtime and
never invoke these scripts or download dependencies on user startup.

First source launch necessarily requires network access plus the system Python
venv and C build prerequisites. Later launches work offline while the declared
inputs remain satisfied. Failure messages identify a missing `python3-venv`
instead of falling back to an unrelated machine-global environment.

## Regression protection

Static source contracts require:

- clone-root ignored `.venv` and `.amy` defaults;
- venv creation through the standard library;
- offline pip requirement verification and `pip check` before launch;
- invocation of the exact existing AMY preparation helper when validation
  fails;
- pinned commit/bank and extension-digest verification before the service is
  started.

The remaining acceptance step is a clean physical Pi clone with neither hidden
directory present. Its first `./run_local.sh --windowed` must provision and
start; a second launch with networking unavailable must validate and start
without installation.
