# SuperCollider migration status

Status: implementation status, not a completion claim

Last verified: 2026-09-14

Target currently exercised: Linux x86_64

## Working vertical slice

- Qt and SuperCollider are separate supervised processes connected by a
  typed, versioned loopback OSC protocol.
- The production Python import closure is checked structurally and cannot
  reach the AMY transports, local AMY service, AMY compatibility adapter or
  `c_amy`; those copied characterization modules are not a runtime fallback.
- Python compiles immutable musical plans; one SC `TempoClock` owns execution,
  quantization, note releases, gates and snapshot lifetimes.
- Session reset, panic, exact voice handles and global pitch bend are wired
  through the SC runtime.
- Prepared program parameters are keyed by musical owner as well as stable
  program identity and session-wide revision. Selecting the same instrument
  on independent MIDI, manual, bass or automatic-chord parts therefore cannot
  leak one part's controls into another.
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
- The independent SC workflow runs the complete dependency-free frontend unit
  suite and portable MIDI/OSC process contracts in addition to the SC compiler,
  coordinator, NRT audio, bank and package suites. This keeps inherited UI and
  control behavior in the same regression gate without invoking AMY-native
  audio suites as if they exercised the SC engine.
- Sequencer tests cover immutable running snapshots, overlapping finite
  executions, root/child lifetime separation, exact release ownership,
  overlapping half-open gates, same-boundary replacement coalescing,
  external-versus-nested timing boundaries, tempo-domain releases, stale
  callbacks and every 1--4 note/beat direction of a seven-note arpeggio.
- A separate GitHub workflow builds pinned headless SuperCollider 3.14.1 and a
  Linux x86_64 AppImage. Publication requires an explicit `release=true`
  manual dispatch and uses an independent `-SC` release tag. Its artifact
  carries a checksum, exact release manifest and SPDX 2.3 evidence.
- The bounded sample-source catalogue records all eleven pinned Git banks and
  the separate Iowa discovery authority. The local inventory tool rejects LFS
  placeholders and produces per-file asset locks; see
  [`SAMPLE_BANKS.md`](SAMPLE_BANKS.md).

## Not yet complete

- The migration handover's additional large instrument banks are not imported.
- VSCO import preserves its declared key/velocity/random/round-robin regions,
  gain, tuning, attack/release and named keyswitch articulations. It does not
  silently turn the six whole-file RIFF sampler loops into sustain loops: they
  are inventoried with an explicit ignored disposition. No reviewed partial
  loop exists in this bank. The importer does not yet claim the advanced
  release, sustain and microphone behavior needed by the additional planned
  banks.
- Sequential round-robin state advances only for admitted notes and is scoped
  by musical owner, program, key, articulation and velocity layer. OMNI drums
  and a MIDI row therefore cannot disturb each other's sample sequence.
- Sample-program admission publishes and accounts asynchronous buffer reads in
  one language-interpreter turn. Concurrent program changes share pending
  buffers, cannot admit the same decoded bytes twice and cannot evict a buffer
  protected by the program currently being prepared.
- Direct MIDI sample attacks arriving during asynchronous preparation are held
  at the typed client boundary and emitted only after the engine reports the
  exact program revision ready. A matching early note-off cancels the deferred
  attack, preventing both dropped first notes and late ghost notes.
- Reconfiguring a MIDI row releases its voices first and then releases its
  superseded program revision, so the sample cache can reclaim recordings
  without affecting another row's owner-scoped program state.
- Deterministic non-realtime tests render the production mono and stereo
  sample SynthDefs from synthetic fixtures, including gated release, without
  taking over the workstation's live audio session.
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
