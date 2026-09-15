# Current architecture and code-quality baseline

Status: authoritative non-regression contract
Owner: application architecture
Applies to: `sc_version`
Last verified: 2026-09-15

- `code/main.py` is the only production composition root.
- One typed SC client is injected; production has no alternate engine path.
- Platform-dependent behavior is selected in named adapters.
- Musical plans are immutable and Python owns no musical clock.
- Frontend and engine configuration are strict, versioned and typed.
- Queues and ownership pools are bounded and failures are visible.
- MIDI/OSC integration stimulus runs outside production processes.
- The SC package contains no AMY runtime, transport, firmware, configuration or
  unused AMY source catalogue.
- Requirements and direct imports have one checked-in dependency authority.
- New Python modules pass strict mypy; Ruff and the QML warning ratchet gate CI.

Large modules may be split only along demonstrated ownership seams. Line count
alone is not a reason to add indirection. Refactoring preserves QML behavior,
musical timing, migration and process separation with executable contracts.
