# Codex Session Handoff

Updated 2026-08-30 after the nested-sequencer drum-fill feature was implemented
and independently regression-tested. The continuation branch is
`feature/drum_fills`; original implementation commit
`32488d37a25af025eb6fd2cdbc1422341466932a` is based on current main
`f872432` plus the branch's intended preset/licence changes. Physical follow-up
`de7b4590570e288fb0fda00d5d37c83e8e521631` fixes the cold-start reset race
and bass-column alignment. The branch is pushed but not yet merged: renewed
physical UI/audio validation and explicit merge approval remain the release
boundary.

This file records operational state and completed work from the AMY/Qt UI,
performance, MIDI-control and native-Windows sessions. It supplements, but does
not override, `AGENTS.md`, the current user request or the authoritative
contracts under `amysynth_version/design/`.

## Mandatory continuation route

Before changing active AMY code, follow the complete startup route in
`AGENTS.md` and `amysynth_version/design/README.md`. For Windows work, also read
all of:

- `amysynth_version/qt_frontend/docs/WINDOWS_NATIVE.md`;
- `amysynth_version/qt_frontend/README.md`;
- `amysynth_version/qt_frontend/INSTALL.md`;
- `.github/workflows/desktop-release.yml`.

Do not use this handoff as a replacement for those contracts.

At this handoff, local and origin `main` resolve to `f872432`; local and origin
`feature/drum_fills` contain `32488d37`. The old, heavily-diverged
`origin/codex_info` documentation line remains intentionally unmerged; current
design contracts plus this automatically read handoff supersede it.

## Required branch and release workflow

- Never implement directly on `main`. Start or continue an appropriately named
  feature/fix branch and keep `main` clean while the user performs physical
  checks.
- Do not merge or start a release merely because automated tests pass. Commit,
  push and merge only when the user explicitly asks for those operations.
- Every push to `main` intentionally starts `.github/workflows/desktop-release.yml`.
  Follow that run through all six regression jobs, four package validations and
  release publication. If it fails, diagnose it and repair it on a new fix
  branch; do not make an unreviewed direct-on-main repair.
- The current `feature/drum_fills` branch is the tested workspace. Preserve it
  through physical validation; merge it only on explicit user approval, then
  follow the complete five-platform release to publication.

## Current architectural state

- The active implementation is Qt/PySide6 plus AMY. Sonic Pi is frozen
  historical material.
- Qt generates AMY wire requests only. It does not import `amy`/`c_amy`, link
  AMY or control the synth service from application code.
- Desktop packages contain two separate runtime components. A packaging
  launcher may start and supervise both processes without changing their wire
  boundary.
- Linux uses `AF_UNIX/SOCK_SEQPACKET` between Qt and the Python AMY service.
- macOS uses LF-framed `AF_UNIX/SOCK_STREAM` because Darwin has no Unix-domain
  `SOCK_SEQPACKET`.
- Native Windows uses Qt `QLocalSocket` to a private Windows named pipe owned by
  the native C `amy_service.exe`. It does not use TCP and does not use WSL.
- ESP32-P4 uses LF-delimited AMY wire requests over UART. Android's proven
  design likewise keeps the app and AMY service in separate processes.

## Current musical/UI baseline

The 2026-08-30 release contains the UI/performance series beginning at
`6f006ee`, the LDR audit, portable Qt gesture work, bass riffs and chord
arpeggios through `387776c`. Treat these details as current behavior, not a
future plan.

The branch adds five complete percussion-activity levels, five independent
fill selectors, the `/32..../1` density series, selection-order rotation and
all 270 authoritative one-shot fills. All definitions are preloaded once into
AMY; live changes replace only quantized root triggers. Fill IDs 0..999 are
reserved so the catalogue can grow beyond 700 without changing the wire
layout; base-role loop patterns start at 1000. See
`amysynth_version/qt_frontend/docs/RHYTHM_PATTERNS.md` for the complete contract.

### Shared visual layout

- OMNI and MIDI use the same utility, reverb and preset header geometry. The
  OMNI-centered title position is reused on MIDI so it never jumps on a screen
  switch.
- The pink reverb and purple preset bars share one height and a normal section
  gap. The purple bar is fitted to Store plus P1–P18/M1–M18 with equal edge and
  button spacing; the pink bar receives the freed width.
- Store is the same size as every round preset button and is visibly darker
  purple. Pointer-down never shrinks a preset. The active preset keeps the
  normal single border and width, with only the border color changed to white.
- The blue APG/LDR panel matches the reverb/preset height and bottom-aligns with
  the utility area. MIDI intentionally has no APG/LDR button.
- Tuning is at the top. Brown independent master controls sit between tuning and
  `PNC!`; `PNC!` and `FSC`/`ESC` align to the reverb panel's right edge.
- The chord-row RST/UP/DWN block ends at row two and distributes its controls
  evenly. Percussion activity keeps four buttons. Bass activity has five equal
  buttons (`1..4`, `R`). Chord activity fills the yellow bar with two rows of
  five buttons: upper `1..4` plus independent `A`, and lower `/1..4` plus
  independent `U/D`. Chord activity has no user-selectable zero.

The public images are real 1920x850 Qt renders at
`amysynth_version/qt_frontend/screenshots/omni.png` and `midi.png`. The root
README embeds them. Run `amysynth_version/qt_frontend/capture_screenshots.py`
with the frontend Python environment to refresh both deterministically. It uses
an isolated temporary home and pseudo-serial endpoint; the MIDI frame contains
three representative CC knobs in the grey bar.

### Strum modes and note guide

- APG/LDR is backend-owned OMNI preset state stored as `strum_mode`; legacy
  presets default to APG.
- The narrow gap beside the strum surface shows one blue round marker per
  available pitch class. Labels use uppercase, chord-aware spelling such as
  C/E-flat/G rather than C/D-sharp/G.
- Every one of the 36 suffixes in `music/chords.csv` has an explicit LDR mapping
  in `app_core.py`. The mapping must contain every chord tone; an unmapped new
  suffix raises an error rather than falling through a family heuristic.
- LDR uses consonant chord-scale subsets appropriate to a mechanical strum. It
  omits avoid/opposite alterations unless named by the chord. In particular,
  G minor-major 7 is `G A B-flat D E F-sharp` and never adds F natural.

### Chords, sequencer and live presets

- Chord-button input uses Qt/QML gesture semantics. `TapHandler` and Qt's
  platform long-press style hint classify tap/hold; Omnichord code contains no
  second gesture timer and no mouse/stylus/OS-specific classification. The same
  rule applies generally: use Qt Quick controls/handlers for press, release,
  tap, hold, mouse, touch and future pointer devices.
- Pointer-down starts manual synth 3 immediately and pointer-up stops it
  immediately. A quick tap also selects the new active chord for strum, bass
  and automatic-chord pitches. It never closes or drains the automatic synth-4
  lane.
- Qt long-press promotion performs manual takeover. It clears only future
  synth-4 note-ons while retaining sequenced whole-chord and note-specific
  arpeggio offs, so sounding accompaniment reaches its rhythmic release.
  Drums, bass, transport and timebase continue.
- `CHORD ON/OFF` owns only automatic synth 4 and keeps state independent of
  chord selection. OFF performs the same deferred-release drain; ON reinstalls
  the lane and never triggers a one-shot manual chord. Its label reports status:
  `CHORD ON` means scheduled chords are enabled and uses the selected activity
  color; `CHORD OFF` uses the unselected activity color.
- Retained repeating arpeggio offs become intentionally unmatched after their
  matching onsets are removed. Automatic chord synth 4 alone receives AMY
  `SYNTH_FLAGS_NO_NOTE_WARNINGS` (`if8`), atomically with every ROM or physical
  allocation. Other synths retain normal lifecycle diagnostics.
- While rhythm is running, preset switches preserve live tempo, percussion,
  chord and bass activity, chord-arpeggio mode/rate/direction, bass voicing, a
  compatible playing bass riff, and the octave of the active chord row. The
  same set survives a live rhythm-type change. Inactive chord-row octaves may
  load from the preset. When rhythm is stopped, all stored values load normally.
- Physical chord-button ownership, active row/root and chord-gate state survive
  a preset switch. A held chord converges to the destination voicing/timbre but
  remains held and releasable by its original button-up.

### Bass riffs

- Bass activity `R` switches the bass voicing slider to a discrete riff
  selector. Levels `1..4` retain the original generated bass behavior.
- The runtime catalogue is
  `amysynth_version/qt_frontend/music/omnichord_bass_riffs.json`, loaded and
  validated through `code/bass_riffs.py`. Application code has no runtime
  dependency on the design directory.
- Catalogue notes are normalized to C2 and transpose live with the active
  chord. Riff PPQ, duration and velocity remain unchanged.
- After a rhythm/chord-set change, a compatible currently playing riff is kept
  by stable ID and the selector follows its new position. Otherwise the
  destination preset selector or application default wins.
- Riff changes replace only bass sequencer tags. The complete catalogue fits
  the reserved bass range and is covered by unit and real-serial tests.

### Chord arpeggios

- `A` is independent of upper chord activity `1..4`. With `A` off, whole-chord
  scheduling is unchanged and lower `/1..4` plus `U/D` have no musical effect.
- With `A` on, every existing chord onset launches every note of the active
  2–7-note chord. `/1..4` means one through four arpeggio notes per quarter-note
  beat; `U` is low-to-high and `D` high-to-low.
- Arpeggios and note gates wrap circularly across the repeating rhythm period.
  A later onset may overlap an unfinished arpeggio. Exact repeated tick/body
  sets may be compacted onto a shorter-period AMY tag only when expansion is
  mathematically identical.
- Arpeggio edits replace only automatic chord tags 112..251 and never stop or
  reset transport. The exhaustive audit covers every rhythm, activity, rate
  and supported chord size; the worst current case uses 84 of 140 chord tags.

### MIDI feedback and output ownership

- Genuine incoming CC movement updates its bound numeric value and visible
  slider. A green binding has exclusive numeric authority until explicit
  double-tap unlink; reset/copy/nudge/preset/manual edits cannot override it.
- Incoming activity for a binding on the other screen always flashes the green
  LED left of `MIDI`/`OMNI`, whether that other-screen target is visible or
  hidden under a preset. A same-screen inactive preset instead flashes its
  small green LED above the preset label. This feedback never loads a preset or
  switches screens.
- The red MIDI-learn LED is larger and appears only while blinking, to the right
  of `MIDI` in the rainbow button. It is not rendered when off.
- Destination presets win same-controller/different-target conflicts; outgoing
  and incoming handles show the documented red/blue two-second handoff.
- OMNI master/mute owns buses 0–3; MIDI master/mute owns buses 4–10. Their live
  values are independent and survive preset changes. `MUT` applies zero without
  discarding the retained slider value; `UMT` restores it.
- Reverb level is consistently 0.00–3.00 through QML, backend clamps, CC mapping
  and owned AMY bus commands.

The authoritative details are in `amysynth_version/design/gui.md`,
`sound_balance.md`, `midi_control.md`, `presets.md`, `rhythm_bahavior.md`,
`tuning.md`, `amysynth_version/qt_frontend/docs/CONTROL_SAFETY.md`,
`SEQUENCER_TAGS.md` and `tests/USE_CASES.md`.

## Native Windows implementation

### Stable transport decision

The supported Windows path is:

```text
LB_Omnichord.exe (frozen PySide6 frontend)
    -> QLocalSocket
    -> private \\.\pipe\LB_Omnichord_AMY_<unique-guid>
    -> amy_service.exe
    -> AMY C engine/miniaudio
```

Important implementation details:

- `code/amy_transport.py` owns `_QtLocalSocketWriter`. The `QLocalSocket`
  object is created, connected, written and closed entirely on the existing
  command-writer thread to preserve QObject thread affinity and keep blocking
  writes away from the UI thread.
- `app_core.py --amy-local-name NAME` selects this transport. It is mutually
  exclusive with Unix `--amy-socket`.
- `packaging/windows/amy_service.c` uses `CreateNamedPipeA` with
  `PIPE_REJECT_REMOTE_CLIENTS`, one client, byte mode and blocking reads.
- Every logical AMY request ends in `Z` and is followed by LF. The service
  buffers partial/multiple `ReadFile()` results and splits only on LF.
- `packaging/windows/run_windows.ps1` creates a unique pipe name. It starts the
  service, waits for a short-lived `%LOCALAPPDATA%/LB_Omnichord/amy.pipe` ready
  file, verifies that its content is the expected name, deletes it, then starts
  the frontend. The ready file is discovery only, never command transport.
- The launcher owns child-process cleanup. The Qt application still does not
  own or import AMY.
- `packaging/build_windows.ps1` builds native `amy_service.exe`, freezes the Qt
  frontend independently with PyInstaller `--onedir`, and packages both plus
  the launcher in a self-contained zip.
- Frozen assets resolve from `sys._MEIPASS`; source-tree-relative lookup is
  wrong for the final PyInstaller layout.

### Why this is not AF_UNIX or TCP

Windows has native `AF_UNIX/SOCK_STREAM` since Windows 10 build 17063, and the
CI runner is Windows Server 2025 build 26100. Old Windows compatibility was not
the problem. Official CPython for Windows still does not expose
`socket.AF_UNIX`. Adding a ctypes Winsock implementation or custom Python
extension would duplicate Qt's already-supported local IPC layer.

Several commits are deliberate failed/diagnostic history and must not be read
as the current architecture:

- `6eace68` through `78376ce` diagnosed the Windows AF_UNIX startup failure;
- `df0899d` temporarily used loopback TCP to prove the rest of the package;
- `fbaa1ce` hardened that temporary service behavior;
- `906b4c5` replaced both experiments with the final native named-pipe design.

Do not restore TCP or the earlier Python AF_UNIX writer unless a new explicit
requirement changes the architectural decision.

### AMY and drum-bank compatibility

The release workflow pins AMY branch
`releases/amy_omnichord_R20260830T191146` at
`e0ef93c0c8b9c049cf5b37b25d50768cd1136e22`.

- Linux and macOS install that revision directly with `AMY_PCM_BANK=tiny`;
  Linux CI rejects Gamma9001 symbols. The old local patch is gone because the
  release branch owns and tests this integration-only build selector.
- The Windows build does not go through AMY `setup.py`. Its CMake target
  compiles `amy.c`/`pcm.c` without defining `GAMMA9001` and does not link the
  optional generated `drums_bin.c`.
- At the pinned AMY revision, that selects `pcm_tiny.h` and the tiny version of
  MIDI drum patch 258 by construction.
- OMNI rhythm commands use the dedicated timing and kit catalogues under
  `music/drums`; the shipped configuration selects direct tiny-bank
  preset/native-note pairs which match Linux, macOS, Windows and ESP32-P4.
- The optional Gamma9001 mapping resolves kit-patch/note pairs to direct PCM,
  and the optional General-MIDI mapping uses AMY patch 258. Both require a
  matching Gamma-enabled local build for complete coverage and are not the
  published-package default.
- Defining `GAMMA9001` on Windows would make identical wire requests select
  different drums and is therefore a compatibility regression.

The current Windows smoke proves non-silent PCM rendering, but it does not yet
identify each tiny-bank drum acoustically. If the AMY pin/build inputs change,
add or run an explicit bank-identity regression rather than relying only on a
nonzero-sample check.

### Windows build and release status

The native package work began at `7a7ed04`. MSVC/CMake/path/launcher corrections
continued through `a711123`. Package smoke work began at `0223166`; diagnostics
and asset-resolution fixes continued through `ddc64e7`; named pipes landed in
`906b4c5`; `7962956` selects Visual Studio 2026 when available and falls back to
Visual Studio 2022.

The dedicated `testing/windows_smoke` branch builds only the Windows package
and does not publish a release. On `main`, all six frontend suites gate Linux,
Raspberry Pi, macOS and Windows jobs, and one release is published only after
all four packages pass.

The latest GitHub Actions run is `33280227230`, from main merge commit
`387776cffad7394c1fcf6add1ced5d3e69a8d382`. It completed successfully on
2026-08-30 local time:

- all six frontend suite jobs passed;
- Linux x86_64 AppImage passed;
- Raspberry Pi aarch64 AppImage passed;
- macOS arm64 DMG passed;
- native Windows x86_64 zip passed;
- release publication passed and targeted the tested merge commit.

The resulting four-platform release is `R20260829T230734`. It contains:

- `LB_Omnichord.R20260829230734.Linux-x86_64.AppImage`;
- `LB_Omnichord.R20260829230734.RaspberryPi-aarch64.AppImage`;
- `LB_Omnichord.R20260829230734.macOS-arm64.dmg`;
- `LB_Omnichord.R20260829230734.Windows-x86_64.zip`;
- one matching SHA-256 file per package.

The release is published at
`https://github.com/linuxificator/LB_Omnichord/releases/tag/R20260829T230734`.
The run is at
`https://github.com/linuxificator/LB_Omnichord/actions/runs/33280227230`.
Its only annotations were GitHub's non-failing Node.js 20 deprecation warnings
for official checkout/setup/upload/download actions being forced onto Node 24.

### What Windows CI does not prove

- No physical Windows speaker/interface output was heard or measured.
- No physical Windows MIDI controller was tested. Native Windows MIDI input is
  not implemented; the current reader is ALSA raw-MIDI only.
- Command-to-audio latency, jitter, drop-outs and behavior under heavy
  patches/reverb were not measured.
- The current host profile still defaults to 44.1 kHz/256 samples, tries
  DirectSound before WASAPI and requests roughly 20 ms x 4 periods. It is not a
  proven realtime/low-latency profile.
- Do not copy the ESP32-P4 48 kHz/64-sample/2x32-DMA baseline blindly to
  Windows. Establish a measured native WASAPI profile.
- Raspberry Pi and macOS release packages also still need their first physical
  device/audio validation. The Linux x64 package has prior physical UI/audio
  validation.

## Android/fork audit context

The local AMY fork convention is `/home/jeroen/omnichord/amyfork/amy`.
`origin/upstream/android-oboe` remains the historical full Android reference.
The active LB dependency is now the cumulative release branch
`releases/amy_omnichord_R20260830T191146`, pinned at
`e0ef93c0c8b9c049cf5b37b25d50768cd1136e22`. It combines the proven separate
Android `:amy`/Oboe and desktop wire-service boundaries with the generic nested
sequencer. The abandoned bus-mixer experiment is absent.

## Verification already completed

- The complete 2026-08-30 local matrix now passes 192 individual tests: 143
  unit, 15 frontend, 14 serial/program, 14 preset, 3 native-control and 3
  native-rhythm tests. This includes the complete 54-rhythm/270-fill catalogue,
  exhaustive fill combinations, chord-arpeggio tag expansion, bass-riff
  validation, the 36-chord LDR audit and package contracts.
- A dedicated cold-start native test proves the visible percussion level
  renders non-silent within one second after Start. The host observes AMY's
  reset block boundary before creating tick-zero instances, preventing the
  reset from erasing freshly ingested `zQT` triggers.
- Native audio smoke renders every used drum realization non-silent: 13 tiny,
  62 Gamma9001 and 24 General-MIDI sounds. AMY itself passes C tests and all
  134 Python regressions at the release threshold.
- GitHub Actions run `33328685849` independently passed the complete LB suite
  on feature commit `32488d37` with the immutable AMY pin.
- GitHub Actions run `33329576417` independently passed all 192 tests on
  physical-regression fix `de7b4590` with the same immutable AMY pin.
- Real-serial tests prove seven-note dominant-13 arpeggios in both directions,
  lane isolation, ROM and physical synth-4 `if8` policy, live riff
  transposition and unchanged transport/timebase. Native AMY state readback
  confirms `if8` exists on synth 4 and not manual synth 3.
- The current public screenshots are 1920x850. Their SHA-256 values are
  `57a39b64db137eb54f395294cc84a24a8e004cd9668bc8ead2ff92255eb53f5b`
  for OMNI and
  `e792e63f5c223526179b9768ff27a4db24433ce5063b91bc82808e81d8048df1`
  for MIDI.
- Feature commit `b2a0934` and merge commit `387776c` contain the complete
  chord-arpeggio work and its unmatched-note-off diagnostic fix. The preceding
  release line also includes `3199032` (Qt gesture delegation), `01b7c6a`
  (rainbow label centering), `a48b4be` (status-oriented chord gate), `f22247b`
  (bass riffs) and `b519182` (live rhythm-control preservation).
- GitHub Actions run `33280227230` independently passed every suite, built and
  validated all four packages, and published `R20260829T230734`.
- `git diff --check` passed before the feature commit and merge.

The standard complete local command, from
`amysynth_version/qt_frontend`, is:

```bash
ALSA_CONFIG_PATH="$PWD/tests/alsa-null.conf" \
  /home/jeroen/omnichord/omnichord-env/bin/python \
  tests/run_tests.py --suite all
```

Use `testing/windows_smoke` only for isolated Windows package iteration. Main
exercises the full gated five-platform release.

## Remaining work / safe next steps

1. Physically validate `feature/drum_fills`: launch the Qt frontend, verify the
   five activity buttons, independent F1..F5 toggles, density labels, tiny-kit
   audio, fill rotation/continuation and live rhythm/preset continuity. After
   explicit approval, merge to `main` and follow the complete five-platform
   release. Do not offer AMY upstream until that release gate passes.
2. Physically test the released Windows zip on a recent Windows 10/11 x64 host:
   UI, native audio, shutdown and representative heavy patches/rhythms.
3. Implement a native Windows MIDI input adapter behind the existing MIDI
   callback boundary, without changing CC-learning/application semantics.
4. Measure and tune a WASAPI-first realtime audio profile on physical hardware.
5. Add an explicit Windows tiny-bank identity regression if AMY build inputs or
   the pinned revision change; the current smoke checks non-silence only.
6. Keep kit/timing policy in LB and generic nested-sequencer behavior in AMY;
   do not restore the abandoned bus-mixer experiment.

WSL2/WSLg documentation remains an optional way to experiment with the Linux
artifact. It is not the Windows implementation, release gate or realtime-audio
baseline.
