# Documentation and branch lifecycle

Status: authoritative repository-hygiene contract
Owner: repository maintenance
Last verified: 2026-09-08

- Active documentation is organized by owning subsystem and describes current
  behavior only.
- Iterative handovers are consolidated when a design stabilizes. Superseded
  copies are removed from the branch tip; Git history retains them.
- Exact current values come from machine-readable config/build inputs.
- Diagnostic experiments live on `diagnostics/<category>` branches, carry a
  clear non-production notice and are never merged merely for safekeeping.
- A feature/fix/rework branch is deleted after its useful commits are in
  `main`, an active successor or a diagnostic branch.
- Open Dependabot branches are not maintenance debris and are left for their
  own review lifecycle.
- Generated build directories and temporary worktrees are not source history.
- Clean Shorepine-facing AMY branches never contain Codex/LB handovers.

The branch cleanup performed on `rework/cleanup_and_details` retains:

- `main` and `rework/cleanup_and_details`;
- open dependency-update branches;
- `diagnostics/esp32p4-rejected-prototypes`, with an explicit non-production
  warning;
- `testing/windows_smoke` and `integration/android_build`, because their exact
  names are intentional partial-CI entrypoints in `desktop-release.yml`.

Old feature/fix/rework labels are removed because their delivered commits
remain reachable from `main` and release tags. Superseded unmerged branches and
the old regression-note stash are removed only after current code, contracts
and tests were checked as their replacement. A CI-entrypoint branch may point
at an old commit while idle; create/update it from the source revision being
diagnosed rather than treating its tip as an independent product line.
