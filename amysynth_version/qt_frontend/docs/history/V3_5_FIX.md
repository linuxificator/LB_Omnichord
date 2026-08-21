# v3.5 fixes

## Panic/startup state recovery

- Panic no longer uses `RESET_AMY` (`S32768Z`). That reset restarts the entire AMY engine from inside message parsing, which is a poor match for a live UART-forwarding task.
- Startup and Panic now use `RESET_ALL_OSCS | RESET_SEQUENCER` (`S12288Z`). In AMY this frees oscillator state and resets the synth/instrument table while leaving the running engine intact.
- The serial writer waits 20 ms (>7 blocks at 128 samples / 48 kHz) after the reset command has actually been transmitted, clears its host-side configured-synth set, then defines synths 0..4 again with their current patches, volumes and controls.
- Closing the Qt app no longer sends `RESET_AMY`; it simply stops transport, silences synths 0..4 and clears the sequencer.

## Strum voice management

- Strum synth 2 is host-voice-managed. At most two notes are left live; the oldest is explicitly released before a third starts.
- Re-entering the same rounded MIDI note releases the prior instance first.
- One inactivity timer ends the entire strum tail with synth-wide all-off instead of creating an 800 ms delayed note-off for every note crossed by a sweep.
- This avoids AMY's fixed 16-entry forgotten-note pool used to match note-offs after voice stealing.

## Retained Juno edge cases

These patches are **not removed**. Small corrections are applied immediately after their normal AMY factory patch is loaded.

- **Juno A82 Resonance Funk (patch 57):** all four factory sound-source amplitudes (pulse/saw/sub/noise) are zero. AMY treats amplitude constant zero as a hard mute/skip. v3.5 gives the noise source a small amplitude (`0.05`) so the highly resonant VCF has excitation.
- **Juno B23 Orchestral Pad (patch 74):** the factory gather/output oscillator has amplitude constant zero even though the child oscillators are active. AMY's zero-constant optimization skips that oscillator. v3.5 restores only the gather/output amplitude constant to `1`, leaving its velocity/envelope routing intact.
- **Juno B15 Harpsichord 1 (patch 68):** the factory patch requests a 71.265 kHz LPF cutoff with Q 11.2. On a 48 kHz engine AMY clamps the filter frequency near Nyquist while retaining the high Q. v3.5 keeps the patch but applies a 16 kHz cutoff and Q 4 after load to keep the fixed-point filter in a useful stable region.

The compatibility values live in `amy_config.json` under `patch_compatibility`, so they can be tuned without changing Python.

## Engine-relevant controls

### Juno upper row

- Cutoff
- Resonance
- LFO Rate
- Vibrato depth (routes Juno LFO to pitch)
- VCF LFO depth (routes Juno LFO to filter)
- Pulse Width
- PWM Depth (routes Juno LFO to pulse width)
- Portamento

Changing **LFO Rate alone need not make any audible change**. AMY's LFO is a modulation oscillator; a non-zero target modulation depth is what makes it affect the sound.

### DX7 upper row

- Algorithm
- Feedback
- LFO Rate
- Vibrato depth
- Portamento

### Common lower row

- Attack
- Decay
- Sustain
- Release

For Juno these edit the output/gather envelope used by the patch. For DX7 they are an optional global output ADSR layered over the native six-operator DX7 envelopes; until an ADSR slider is moved, the factory patch envelope is left alone.
