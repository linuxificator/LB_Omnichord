# Codex Session Handoff

Updated 2026-08-26 on branch `feature/midi_control`.

This file records the completed work and exact repository state from the
current AMY/Qt session. It supplements, but does not override, `AGENTS.md` or
the authoritative documents under `amysynth_version/design/`.

## Completed and pushed earlier in this session

- `e52dbb2 Preserve live chords across preset changes`
  - OMNI preset selection no longer silences an active chord.
  - The active row/root, chord gate and physical button ownership survive.
  - The sounding notes converge to the destination preset's chord type,
    inversion, octave, tuning and instrument.
- `f0ed4fd Fix MIDI control feedback and document WSL testing`
  - Real CC movement clears the temporary blue/unbound state immediately and
    notifies both MIDI and OMNI indicators.
  - Raw MIDI, backend reverb mapping and QML slider synchronization gained
    permanent regressions.
  - The WSL2/WSLg AppImage testing guide and release links were completed.

Both commits were pushed to `origin/feature/midi_control`. The last fetched
`origin/main` during this session was `24488cd`, the merge of the original MIDI
control feature.

## Completed implementation in this handoff

Points 2, 3 and 9 from
`amysynth_version/qt_frontend/docs/regressions.txt` are implemented:

1. APG/LDR is backend-owned OMNI preset state.
   - Presets store `strum_mode` as `APG` or `LDR`.
   - Older/factory presets without the field load as APG.
   - `Main.qml` observes `backend.strumLadderMode`; the button calls the
     backend toggle instead of owning an independent QML boolean.
2. MIDI-bound numeric values are live controller state.
   - Section RST restores selection and all unbound values, but preserves
     bound parameters and section volume.
   - Hidden instrument target values are restored directly in `SynthState`
     without briefly selecting or sending that hidden patch.
   - Runtime preset selection preserves the union of source bindings and
     bindings declared by the destination preset. Startup loading remains a
     normal full initialization.
   - The rule is implemented for both OMNI and MIDI presets/RST paths.
3. Reverb level spans 0.00 through 3.00 consistently.
   - QML, OMNI and MIDI backend clamps, CC mapping and the program-aware AMY
     receiver all accept 3.0.
   - OMNI buses 1-3 and MIDI melodic buses 4-9 are covered by exact wire tests.

Authoritative contracts were updated in `amysynth_version/design/presets.md`,
`amysynth_version/design/midi_control.md`,
`amysynth_version/design/sound_balance.md`, `amysynth_version/design/gui.md`,
`amysynth_version/design/testing.md`,
`amysynth_version/qt_frontend/docs/CONTROL_SAFETY.md` and
`amysynth_version/qt_frontend/tests/USE_CASES.md`.

## Verification

The complete regression matrix passed after these changes: 119 tests across
unit, frontend, serial, presets, native-controls and native-rhythm suites.

Command used from `amysynth_version/qt_frontend`:

```bash
ALSA_CONFIG_PATH="$PWD/tests/alsa-null.conf" \
  /home/jeroen/omnichord/omnichord-env/bin/python \
  tests/run_tests.py --suite all
```

`git diff --check` and Python compilation of the changed backend modules also
passed. No physical MIDI controller, Raspberry Pi, ESP32-P4 or packaged release
was exercised for these changes.

## Deliberately untouched local notes

`amysynth_version/qt_frontend/docs/regressions.txt` is an untracked user task
list and `.regressions.txt.swp` is an active Vim swap file. Do not delete,
rewrite, stage or commit either file without explicit user direction. Points
4, 5, 6, 7, 8 and 10 in that list remain outside the work completed here.
