# SuperCollider migration status

Status: implementation status, not a completion claim

Last verified: 2026-09-14

Target currently exercised: Linux x86_64

## Working vertical slice

- Qt and SuperCollider are separate supervised processes connected by a
  typed, versioned loopback OSC protocol.
- Python compiles immutable musical plans; one SC `TempoClock` owns execution,
  quantization, note releases, gates and snapshot lifetimes.
- Session reset, panic, exact voice handles and global pitch bend are wired
  through the SC runtime.
- The four native acid voices support the current conservative TB-303
  articulation contract.
- All 109 pinned SCLOrkSynths definitions compile and participate in the
  program catalogue; the automated NRT audit renders one representative note
  from each definition.
- The generated VSCO manifest contains all 75 source mappings and 3,163 sample
  regions. Their complete keyswitch articulation set is exposed as 96 stable,
  directly selectable program identities, so playable notes are never stolen
  for frontend keyswitches. Startup requires the initial GM percussion sample
  program to load before the engine announces readiness.
- MIDI and OSC integration tests keep the sender, frontend and engine receiver
  in separate processes.
- Sequencer tests cover immutable running snapshots, overlapping finite
  executions, root/child lifetime separation, exact release ownership,
  overlapping half-open gates, same-boundary replacement coalescing,
  external-versus-nested timing boundaries, tempo-domain releases, stale
  callbacks and every 1--4 note/beat direction of a seven-note arpeggio.
- A separate GitHub workflow builds pinned headless SuperCollider 3.14.1 and a
  Linux x86_64 AppImage. Publication requires an explicit `release=true`
  manual dispatch and uses an independent `-SC` release tag. Its artifact
  carries a checksum, exact release manifest and SPDX 2.3 evidence.

## Not yet complete

- The migration handover's additional large instrument banks are not imported.
- VSCO import preserves its declared key/velocity/random/round-robin regions,
  gain, tuning, attack/release and named keyswitch articulations. It does not
  yet claim sample-header sustain/loop metadata or the advanced release,
  sustain and microphone behavior needed by the additional planned banks.
- Compiling and rendering every SCLOrk definition proves loadability and basic
  signal production, not musical calibration across registers, dynamics and
  long performances. Some definitions clip under the generic audit stimulus
  and need program-specific review.
- Full soft/mid/hard and low/mid/high sample audits, measured resident-set
  admission, latency/load tests and long live performance tests remain open.
- Linux source behavior was exercised locally with SuperCollider 3.13.0. The
  pinned 3.14.1 compiler, engine, frontend and package workflow passed on
  commit `fc3b26e` in GitHub run `34790456369`.
- Raspberry Pi, macOS, Windows, Android and ESP32-P4 are not SuperCollider
  edition targets. Their existing AMY artifacts remain separate and supported
  according to the AMY documentation.

## Distribution boundary

The AppImage bundles the Qt frontend and a pinned headless SC runtime. It does
not bundle the VSCO recordings and relies on the Linux distribution's normal
JACK/PipeWire session integration. This is deliberate: sample licensing and
audio-session ownership remain visible rather than hidden in a nominally
self-contained executable.

Current code and executable tests take precedence over the original migration
handover where implementation details have evolved. The handover remains the
acceptance backlog for items explicitly listed above.
