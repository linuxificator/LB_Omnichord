# Codex Session Handoff

Updated 2026-08-28 for the merge of `refactoring/ui_changes` into `main`.
Inspect `git status`, the current branch and the latest GitHub Actions run
before continuing; the release build triggered by this merge may still be in
progress when the next session begins.

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

At the merge audit, `origin/main` contained no commit missing from
`refactoring/ui_changes`. The only other remote branch not merged into main was
`origin/codex_info`: it is an old, heavily diverged documentation line and was
intentionally not merged. Current design contracts plus this automatically read
handoff supersede it.

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

The 2026-08-28 merge contains the UI/performance series beginning at `6f006ee`
and the subsequent LDR audit. Treat these details as current behavior, not a
future plan.

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
  evenly. Percussion, chord and bass activity each show four equal, top-aligned
  buttons; chord activity has no user-selectable zero.

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

- A quick chord tap starts/stops manual synth 3 and selects the new active chord
  for manual play, strum, bass and automatic-chord pitches. It never closes or
  drains the automatic synth-4 lane.
- A contact held beyond the 160 ms tap window is promoted to manual takeover.
  Promotion clears only future synth-4 note-ons while retaining the sequenced
  synth-4 all-off tags, so the currently sounding accompaniment reaches its own
  rhythmic note-off instead of hanging or being cut short. Drums, bass,
  transport and timebase continue.
- `CHORD ON/OFF` owns only automatic synth 4 and keeps state independent of
  chord selection. OFF performs the same deferred-release drain; ON reinstalls
  the lane and never triggers a one-shot manual chord.
- While rhythm is running, preset switches preserve live tempo, percussion,
  chord and bass activity, bass voicing, and the octave of the active chord row.
  Inactive chord-row octaves may load from the preset. When rhythm is stopped,
  all those stored values load normally.
- Physical chord-button ownership, active row/root and chord-gate state survive
  a preset switch. A held chord converges to the destination voicing/timbre but
  remains held and releasable by its original button-up.

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

The release workflow pins the AMY fork at
`25213785696dd40e6cce59ab428e560a410d240f`.

- Linux and macOS apply `packaging/amy-tiny-bank.patch`, install with
  `AMY_PCM_BANK=tiny`, and Linux CI rejects Gamma9001 symbols.
- The Windows build does not go through AMY `setup.py`. Its CMake target
  compiles `amy.c`/`pcm.c` without defining `GAMMA9001` and does not link the
  optional generated `drums_bin.c`.
- At the pinned AMY revision, that selects `pcm_tiny.h` and the tiny version of
  MIDI drum patch 258 by construction.
- OMNI rhythm commands use direct preset/native-note pairs 0–10 from
  `config/amy_config.json`; these meanings match Linux, macOS and ESP32-P4.
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

GitHub Actions run `33021825480`, from main commit
`33455020101744ffa9c360b1a3cbf04dabd3009d`, completed successfully on
2026-08-26:

- all six frontend suite jobs passed;
- Linux x86_64 AppImage passed;
- Raspberry Pi aarch64 AppImage passed;
- macOS arm64 DMG passed;
- native Windows x86_64 zip passed;
- release publication passed.

The Windows Server 2025 job extracted only the final zip and then observed:

- `amy_service.exe --self-test`: 6,140 nonzero rendered samples;
- packaged launcher smoke: 209 real wire commands and 13,138 nonzero rendered
  samples;
- offscreen/software Qt/QML startup, packaged asset loading, initial-state
  publication, test-chord note-on/release, named-pipe delivery and clean Qt
  event-loop exit;
- no leaked `amy_service.exe` and no leftover ready file.

The resulting four-platform release is `R20260826T230234`. It contains:

- `LB_Omnichord.R20260826230234.Linux-x86_64.AppImage`;
- `LB_Omnichord.R20260826230234.RaspberryPi-aarch64.AppImage`;
- `LB_Omnichord.R20260826230234.macOS-arm64.dmg`;
- `LB_Omnichord.R20260826230234.Windows-x86_64.zip`;
- one matching SHA-256 file per package.

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
`origin/upstream/android-oboe` contains the separate Android `:amy` process,
private `amy.sock`, service-only JNI and transport-only Java client used as the
process-separation reference. That branch was not an ancestor of the active
`feature/bus-mixer` line during the audit, so Android service work and the
desktop bus-mixer fork are not assumed to be unified. Preserve the proven
service/wire boundary when those lines are eventually reconciled.

## Verification already completed

- The complete 2026-08-28 local matrix passed 147 individual tests: 106 unit,
  13 frontend, 10 serial/program, 13 preset, 3 native-control and 2
  native-rhythm tests. This includes the exhaustive 36-chord LDR audit and the
  screenshot/README contract.
- The screenshot helper completed twice consecutively with byte-identical
  1920x850 results. The final SHA-256 values at handoff were
  `ab071b66e33e8cfd5f8e5105e85616f53df9b6bfac4916a8acc80e557a60c04c`
  for OMNI and
  `e792e63f5c223526179b9768ff27a4db24433ce5063b91bc82808e81d8048df1`
  for MIDI.
- `3345502` made the preset integration test wait deterministically for live
  preset continuation instead of racing the frontend.
- GitHub Actions run `33021825480` independently passed each of the six suites
  and all release jobs as described above.
- `git diff --check` and Python compilation were run during the implementation
  work before its commits.

The standard complete local command, from
`amysynth_version/qt_frontend`, is:

```bash
ALSA_CONFIG_PATH="$PWD/tests/alsa-null.conf" \
  /home/jeroen/omnichord/omnichord-env/bin/python \
  tests/run_tests.py --suite all
```

Use `testing/windows_smoke` only for isolated Windows package iteration. Merge
or apply the final Windows changes to `main` to exercise the full gated
four-platform release.

## Remaining work / safe next steps

1. Physically test the released Windows zip on a recent Windows 10/11 x64 host:
   UI, native audio, shutdown and representative heavy patches/rhythms.
2. Implement a native Windows MIDI input adapter behind the existing MIDI
   callback boundary, without changing CC-learning/application semantics.
3. Measure and tune a WASAPI-first realtime audio profile on physical hardware.
4. Add an explicit Windows tiny-bank identity regression if AMY build inputs or
   the pinned revision change; the current smoke checks non-silence only.
5. Reconcile relevant Android service work with the active AMY bus-mixer line
   only when that fork task is explicitly in scope.

WSL2/WSLg documentation remains an optional way to experiment with the Linux
artifact. It is not the Windows implementation, release gate or realtime-audio
baseline.
