# Current work handoff

Updated: 2026-09-14

- Active branch: `version/supercollider`, based on `main` at `955cbbf`.
- The AMY implementation under `amysynth_version` is intentionally unchanged.
- The Linux x86_64 SuperCollider vertical slice lives under `sc_version` and
  uses separate Qt, headless `sclang` and `scsynth` processes. The frontend
  sends typed OSC actions and immutable plans; SC owns musical timing and note
  lifetimes.
- Pinned inputs are SuperCollider 3.14.1 and SCLOrkSynths commit
  `6730c745971aa45c95d9b4cddfb4d5ca342774b3`. VSCO 2 CE is a separate local
  CC0 bank at `~/sample_lib/VSCO-2-CE-1.1.0` by default.
- The complete local matrix passed at commit `515d8bc`, including all 109
  SCLOrk non-realtime renders and the native sample-player render. GitHub run
  `34794953001` passed the independent SC test/package workflow with pinned
  SuperCollider 3.14.1 and produced the verified `package-SC-Linux-x86_64`
  artifact. Publishing is
  manual through `release=true`; AMY publication is independently explicit.
- VSCO release layers now remain correctly owned across sustain and two-phase
  program changes. Manual strum and MIDI preview gestures carry the exact
  prepared program revision. A pinned Salamander opcode audit records 69
  distinct opcodes and the 49 semantics still blocking an honest import.
- The implementation is not a full migration claim. Additional banks,
  advanced SFZ behavior, comprehensive program calibration/load evidence and
  non-Linux SC targets remain open.

Resume through `sc_version/design/README.md`, then
`sc_version/design/sc/STATUS.md`. The original detailed requirements remain in
`sc_version/design/sc/CODEX_HANDOVER_SUPERCOLLIDER_MIGRATION.md`; current code,
configuration and executable tests take precedence where implementation has
made a choice explicit.
