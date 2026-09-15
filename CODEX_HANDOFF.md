# Current work handoff

Updated: 2026-09-15

- Active branch: `fix/sc-runtime-lifecycle`; current implementation and
  qualification status are maintained under `sc_version/design/`.
- The AMY implementation under `amysynth_version` is intentionally unchanged.
- The preceding SC music work was merged to `main`; GitHub Actions run
  `34903048200` passed Linux x86_64, Raspberry Pi aarch64, macOS arm64 and
  Windows x86_64.
- The quality branch removes the inherited AMY runtime/config/firmware/test
  copy from `sc_version`, introduces a strict engine-neutral frontend config
  and leaves one SC production graph. The full local test suite passes. See
  `sc_version/design/arch/sc_code_quality_review.md`.
- The Linux x86_64 SuperCollider vertical slice lives under `sc_version` and
  uses separate Qt, headless `sclang` and Supernova processes. The frontend
  sends typed OSC actions and immutable plans; SC owns musical timing and note
  lifetimes.
- Pinned inputs are SuperCollider 3.14.1 and SCLOrkSynths commit
  `6730c745971aa45c95d9b4cddfb4d5ca342774b3`. VSCO 2 CE is a separate local
  CC0 bank at `~/sample_lib/VSCO-2-CE-1.1.0` by default.
- The current working tree separates the 109-definition SCLOrk source inventory
  from its 76 measured pitched-browser voices, removes AMY patch names from the
  SC catalogue, calibrates three fixed registers with float NRT renders, and
  keeps raw drums plus two unstable definitions out of that browser. The live
  engine exercised every admitted SCLOrk voice, VSCO range fallback and all
  percussion roles without `/n_free` or buffer-allocation failures. See
  `sc_version/design/sc/PLAYBACK_QUALIFICATION.md`.
- The SC instrument UI now separates 80 qualified synth programs from a compact
  PCM browser with 22 VSCO families and 66 canonical choices. SynthDef scalar
  defaults drive a reviewed parameter surface; ADSR is lower-left, PCM
  variants/articulations use two aligned button rows, and engine prefixes are
  hidden. See `sc_version/design/sc/INSTRUMENT_BROWSER.md`.
- The prior complete local matrix passed at commit `515d8bc`, including all 109
  SCLOrk non-realtime renders and the native sample-player render. GitHub run
  `34794953001` passed the independent SC test/package workflow with pinned
  SuperCollider 3.14.1 and produced the verified `package-SC-Linux-x86_64`
  artifact. Publishing is
  manual through `release=true`; AMY publication is independently explicit.
- VSCO release layers now remain correctly owned across sustain and two-phase
  program changes. Manual strum and MIDI preview gestures carry the exact
  prepared program revision. A pinned Salamander opcode audit records 69
  distinct opcodes and the 49 semantics still blocking an honest import.
- Immutable sequencer executions retain exact PCM program revisions across
  live instrument changes. Native output and PCM choke release use stable
  control buses, eliminating natural-end versus `/n_set` node races. The
  focused real-process regression is recorded in
  `sc_version/design/sc/PLAYBACK_QUALIFICATION.md`.
- The implementation is not a full migration claim. Additional banks,
  advanced SFZ behavior, comprehensive program calibration/load evidence and
  non-Linux SC targets remain open.
- `rework/sc_code_quality` was merged to `main`; GitHub run `34953089772`
  passed all four platform test jobs. The active performance branch selects
  Supernova for production audio and gives independent graph stages explicit
  parallel groups without changing the musical-time or voice-owner contracts.
- The current Supernova implementation passed the complete local matrix and a
  97.6-second separate-process broad live endurance cycle. That qualification
  exposed and fixed two server-compatibility boundaries: scalar SCLOrk controls
  are now always numeric, and non-finite third-party voice output is sanitized
  before it can poison shared buses and room effects. The live recorder follows
  Supernova's actual PipeWire ports and treats `/s_new` exceptions as fatal.
- Continuous production-QML strumming now has a reproduced engine-resource
  regression and an engine-owned fix. A queued pointer burst previously grew
  to 1,007 synths, exhausted private audio buses and corrupted subsequent
  spawns. The initial 24-voice/5-ms boundary itself caused an audible P16
  discontinuity and has been superseded. SuperCollider now admits 64 live
  voices per gesture owner and fades only the oldest saturated voice over at
  least 50 ms through a race-free control bus. The exact two-cycle,
  160-second held-pointer regression completed without SC errors, clipping or
  long silence; the preceding instrumented run also added no PipeWire errors. See
  `sc_version/design/sc/STRUM_PRESSURE.md`.
- A second, screen-edge-specific reproduction showed no extra semantic strum
  attack from out-of-bounds coordinates, but exposed incomplete Linux
  scheduling: one Supernova DSP thread was `SCHED_RR 20` and fifteen helpers
  were `SCHED_OTHER`. The source and packaged Linux launchers now perform one
  bounded, exact-owned-session RealtimeKit setup and verify the complete DSP
  pool. There is no persistent/name-based watcher and no change to Qt gesture
  or musical behavior. The focused QML top-edge and Linux realtime adapter
  regressions are in the normal test tree.
- Source and packaged starts now share the Python SuperCollider supervisor.
  It owns one private process group, fails clearly if the language UDP endpoint
  is still occupied, and tears down sclang plus Supernova on normal exit and
  termination signals. The SC bootstrap independently makes a late bind race
  fatal before registering OSC handlers. Two immediate real source launches
  completed and released both UDP ports; an occupied-port launch failed before
  opening Qt or starting another SC process.

Resume through `sc_version/design/README.md`, then
`sc_version/design/sc/STATUS.md`. The original detailed requirements remain in
`sc_version/design/sc/CODEX_HANDOVER_SUPERCOLLIDER_MIGRATION.md`; current code,
configuration and executable tests take precedence where implementation has
made a choice explicit.
