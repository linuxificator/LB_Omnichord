# Current work handoff

Updated: 2026-09-08

- Active branch: `rework/cleanup_and_details`, based on `main` at `476f7e3`.
- Goal: consolidate current documentation and retire obsolete branch/worktree
  labels without losing useful diagnostics.
- Rejected P4 prototypes are preserved on the non-production branch
  `diagnostics/esp32p4-rejected-prototypes`; never merge it into production.
- Released baseline: LB `R20260907T231243` (`c191e65`), AMY
  `releases/amy_omnichord_R20260908T005616` (`e9a96c2`).
- The complete release matrix passed. The Pi AppImage was physically accepted
  on a 2 GiB Pi 4 with bundled AMY and with serial ESP32-P4.

Resume through `amysynth_version/design/README.md`. It routes to the current
contracts and open work; Git history is the archive for removed handovers.
