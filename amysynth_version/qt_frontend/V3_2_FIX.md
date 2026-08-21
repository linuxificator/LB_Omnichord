# v3.2 hardware fixes

This revision follows the first v3.1 tests on the ESP32-P4.

## Root causes addressed

1. The previous fixed synth pools could exceed AMY's standard 120-oscillator pool.
   In a normal Juno/DX7 combination v3.1 could eventually demand 136 oscillators.
   Failed allocations explain the intermittent `synth N not defined` state and are
   the most likely reason the dedicated strum synth could be silent.

2. The legacy GM drum patch 258 reserves 32 oscillators for its complete GM-note
   mapping. The Omnichord does not need that mapping layer. v3.2 instead uses four
   one-oscillator PCM voices and sends the preset/native-note pair for each hit.

3. Panic previously stopped notes but trusted the backend's cached set of configured
   synth IDs. v3.2 treats Panic as recovery: it invalidates pending sequencer traffic
   and delayed releases, stops all five synths, and unconditionally rebuilds all five.

## Fixed synth layout

- synth 0: drums, 4 voices x 1 PCM oscillator
- synth 1: bass, 1 voice
- synth 2: strum, 1 voice
- synth 3: manual chord, 7 voices
- synth 4: rhythm chord, 4 voices

For the shipped Juno (6 oscs/voice) and DX7 (8 oscs/voice) catalogue, the absolute
worst case is 108 oscillators, leaving 12 of AMY's standard 120 free.
