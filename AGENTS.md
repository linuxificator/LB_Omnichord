# LB Omnichord agent entry point

The active implementation is `amysynth_version`; the Sonic Pi tree is frozen
history. Preserve behavior, explicit ownership and the platform-independent
wire-command boundary unless the user explicitly changes a contract.

Before editing, read:

1. `amysynth_version/README.md`
2. `amysynth_version/design/README.md`
3. the required architecture documents listed there
4. the README and contracts for every affected design category
5. `CODEX_HANDOFF.md` for current operational state

All detailed architecture, behavior, test, platform, AMY and ESP32 rules live
under `amysynth_version/design/`; do not duplicate them here. Current code,
machine-readable configuration and executable tests outrank historical Git
notes. Work on explicit branches, preserve dirty user work, keep experiments
on clearly named diagnostic branches and never put LB/Codex material in an AMY
upstream-offer branch.
