# AMY maintenance findings outside reusable sequences

Status: current diagnostic register
Owner: LB Omnichord AMY integration
Last verified: 2026-09-08

These findings were reproduced outside the reusable-sequence patch and should
remain separate upstream changes:

- The MIDI-mapping parser can read beyond a completed patch string.
- Repeated oscillator reset can replace bus-filter allocations without freeing
  the previous arrays.
- Repeated `amy_start()`/`amy_stop()` can leak patch-table backing storage.
- Fixed-point log lookup contains a signed-left-shift undefined operation.
- Optional ALSA MIDI shutdown state previously showed a ThreadSanitizer race.

Two independent fixes are carried by the current LB AMY release:

- `M_PI` receives a guarded portable definition so MSVC can compile the Godot
  sampler source. This predates and is causally independent of sequences.
- Synths that explicitly ignore note-offs no longer accumulate impossible
  forgotten-note bookkeeping. This fixes the pre-existing percussion overflow
  without changing public API or ordinary synth behavior.

Future fixes need focused baseline reproductions and must not be presented as
sequence regressions. Sanitizer suppressions may isolate known baseline leaks
for feature testing but may not be used to claim the whole repository clean.

