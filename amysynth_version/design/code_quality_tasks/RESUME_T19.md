# Resume checkpoint: T19 preset and MIDI-binding services

Status: implementation checkpoint; T19 is not yet marked complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Resume after: commit `T19 checkpoint preset and binding services`

## Completed at this checkpoint

- Added pure, frozen preset values and `compile_omni_preset_plan()` in
  `qt_frontend/code/preset_plan.py`.
- Reduced `InstrumentBackend._apply_preset_data()` to preservation of live
  state, compilation of the plan, explicit application and existing synth
  role loading.
- Added `MidiBindingService`, frozen normalized entries and detached immutable
  presentation snapshots in `qt_frontend/code/midi_binding_service.py`.
- Routed MIDI binding normalization, per-screen replacement, serialization and
  QML presentation through that service without merging OMNI and MIDI preset
  ownership.
- Replaced both legacy preset-write helpers with the T10 `JsonStore`.
- Preserved integer tuning-reference state at the application facade.
- Added direct tests for default/clamped/legacy preset normalization, fill
  normalization, all three MIDI source types, per-screen binding separation
  and detached presentation snapshots.

## Verification already run

- Strict mypy for the two new service modules: green.
- Targeted preset migration, refactor characterization, MIDI engine, MIDI
  binding state/service and preset-plan tests: green.
- `run_quality.py`: green at 37/42 legacy mypy errors and 22 strict modules.
- A full `run_tests.py` invocation completed as a process. Its captured output
  was truncated after the green `test_sequencer_tags.py` start, so its final
  exit code was not retained in the session transcript. Re-run it before
  declaring T19 complete.
- `git diff --check`: green.

## Exact next actions

1. Re-run the complete behavior suite and retain the final summary/exit code.
2. Inspect the final T19 diff for accidental behavior change, especially
   preset application ordering and external-control hidden binding behavior.
3. Add the authoritative architecture paragraph describing preset-plan and
   MIDI-binding service boundaries.
4. Add `T19_PRESET_BINDING_SERVICES.md`, record measured proof and progressive
   findings, add T19 to this directory's `README.md`, then commit/push the T19
   completion-only documentation if no code correction is needed.
5. Continue with T20 from
   `../CODEX_HANDOVER_ORDERED_CODE_QUALITY_TASKS.md`; do not begin it before
   T19 has been marked complete.

No T20-T25 implementation has started.
