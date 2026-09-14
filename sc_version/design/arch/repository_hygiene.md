# Documentation and branch lifecycle

Status: authoritative repository-hygiene contract
Owner: repository maintenance
Applies to: `sc_version`
Last verified: 2026-09-15

Active documentation describes current behavior and is organized by owner.
Superseded task notes and duplicated edition material are removed from the
branch tip; Git history is the diagnostic trail. Machine-readable config and
tests own exact values.

Generated builds, virtual environments and temporary worktrees are not source.
Experiments use explicit diagnostic branches and are merged only after the
production contract is proven. Never place LB/Codex handovers in an upstream
AMY offer branch. A feature branch is removable after its useful commits are
reachable from `main` or a named successor.
