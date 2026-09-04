# Unclear items and conflicts

Status: active open-items register; not authoritative over subsystem contracts
Owner: design index (`README.md`)
Applies to: unresolved active `amysynth_version` questions only
Last verified: 2026-09-04

Resolved decisions have been moved to their authoritative design documents.
This file contains only genuinely open work.

## ESP32-P4 physical firmware acceptance

The complete Gamma9001 firmware now builds with 336 oscillators, eleven buses,
1024 sequence groups, 64 local tags per group and 40 concurrent executions.
Both incompatible silicon profiles compile and package; v1 targets the observed
revision-1.3 board. The remaining work is physical validation of LP-UART input,
I2S output, all capacities under load and independent OMNI/MIDI buses. The exact
acceptance list is in `../esp32p4/README.md`.

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
