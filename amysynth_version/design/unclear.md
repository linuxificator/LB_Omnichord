# Unclear items and conflicts

Status: active open-items register; not authoritative over subsystem contracts
Owner: design index (`README.md`)
Applies to: unresolved active `amysynth_version` questions only
Last verified: 2026-09-01

Resolved decisions have been moved to their authoritative design documents.
This file contains only genuinely open work.

## ESP32-P4 complete resource build

The logical allocation is fixed: synths 0–4 for OMNI, synths 5–10 for MIDI
rows, synth 11 for MIDI drums, and buses 0–10 as documented in
`architecture.md`. The remaining work is validating/finalizing those resource
limits and independent OMNI/MIDI room behavior in the ESP32-P4 AMY build.

## MIDI input selection and non-Linux native bridges

Linux ALSA raw and ALSA Sequencer input are implemented as documented in
`midi.md`; VMPK can connect directly to `LB Omnichord / MIDI In`. Remaining
possible work is an explicit UI device selector and maintained native
CoreMIDI, WinMM and Android MIDI adapters. `midi.md` owns current capability
status.

## Live parameter changes

Need rules for which changes affect currently playing notes and which only affect new notes.

## External MIDI and preview concurrency

Preview strums are bounded to four tracked notes and do not cause voice
stealing by themselves. Define the desired priority when external MIDI already
occupies all four voices and preview is used simultaneously on the same row.

## ESP32-P4 instrument balance confirmation

The complete 124-instrument low/middle/high bank has been rendered with native
AMY on the development host and contains no clipped or silent captures after
the corrections in `sound_balance.md`. A physical ESP32-P4 line-output capture
is still needed to confirm that target's DAC path and 48 kHz build produce the
same measured balance. Do not introduce target-specific corrections without
that capture.
