# Synth control safety policy

The Qt frontend exposes musical controls in physical/display units, but those controls ultimately modify real-time DSP parameters in AMY. Catalogue ranges therefore are not merely UI hints: every user-editable value has a deliberately bounded application range and the same hard envelope is enforced again at the AMY serial receiver.

The shared hard limits live in `code/control_limits.py`. Catalogue entries may narrow a hard range, but may not widen it. `SynthState` clamps UI and preset input, and `AmySerialClient` clamps received sparse parameter state before it reaches AMY. Non-finite values are rejected.

The limits are intentionally wider than the normal shipped defaults. They exist to exclude values likely to be pathological for live fixed-point DSP rather than to prevent sound design. In particular, Juno `VCF base` is limited to 20–10000 Hz. It is the base term of a modulated filter-frequency CtrlCoef, not necessarily the instantaneous cutoff; high note/envelope coefficients can raise the effective filter frequency substantially above the base. `VCF LFO` is limited to 0–0.5 octaves because the shipped native catalogue peaks around 0.157 octave, while the previous 4-octave UI range was not musically or numerically sensible.

Known factory-patch extremes receive target-side compatibility corrections immediately after `K`: Harpsichord 1 and 2 use a 6000 Hz safe bright VCF base, and Sweep I uses 9000 Hz. The application catalogue uses the same corrected musical defaults. This protects both the current complete-state sender and older/name-only or incomplete senders from briefly leaving a pathological patch value active.

Current hard ranges:

| Control | Range |
| --- | --- |
| VCF base | 20–10000 Hz |
| Resonance | 0.51–12 Q |
| LFO rate | 0.1–20 Hz |
| Vibrato | 0–0.05 oct |
| VCF LFO depth | 0–0.5 oct |
| Pulse width | 0.05–0.95 |
| PWM depth | 0–0.45 |
| Portamento | 0–1000 ms |
| Attack | 0–3000 ms |
| Decay | 0–10000 ms |
| Sustain | 0–1 |
| Release | 0–10000 ms |
| DX7 algorithm | 1–32 |
| DX7 feedback | 0–0.5 |

Other user controls are independently bounded in the backend: volumes are 0–1,
reverb level is 0–3, reverb liveness/damping are 0–1, tuning reference is
415–466 Hz, rhythm tempo is 40–200 BPM, and activity selectors are restricted
to their discrete UI ranges.

## Runtime boundary guards

A first-time AMY `K...iv...` synth allocation is executed at an audio-block boundary. The host therefore inserts a configurable allocation guard (default 10 ms) before sending synth-tier commands such as bus routing, synth level, compatibility corrections or slider overrides. This prevents cold-start commands from reaching an instrument number before AMY has created it; the regression suite checks synth 4 specifically because that was observed on the ESP32-P4 as repeated `synth 4 not defined` warnings.

The ESP32-P4 also exhibited low-frequency rumble when an exact `h0` reverb command was sent. A fresh dry bus is now left untouched when the logical reverb value is zero. If an already-active reverb is turned off, the UI/preset state remains exactly 0 while the wire uses a sub-audible nonzero coefficient (`0.001`) as a target-side workaround for the exact-zero edge case. The serial regression forbids `y0h0Z` and `y1h0Z` on cold startup.

Manual chord hold is another timing-sensitive path. Suppressing automatic rhythm chords must not stop percussion or bass. Finger-down now publishes the new chord/bass state and automatic-chord gate as one accompaniment transaction, causing one sequencer rebuild rather than two consecutive stop/clear/restart cycles. The serial regression holds a chord for one second and requires rhythm transport to stay logically running with percussion events still scheduled during the hold.
