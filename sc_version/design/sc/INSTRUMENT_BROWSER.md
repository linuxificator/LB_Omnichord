# SuperCollider instrument browser and controls

Status: authoritative implemented contract

Last verified: 2026-09-14

## User contract

The OMNI bass, strum and chord rows each have a `SYN`/`PCM` mode button above
their existing `RST` action. Switching mode changes only the visible catalogue
partition and selects the last-used instrument in that partition. It does not
create a second audio backend: both choices are canonical SuperCollider
programs and travel through the same typed program-selection protocol.

`SYN` shows the 76 qualified SCLOrk definitions plus four owned acid voices.
Engine prefixes are not user-facing labels. `PCM` shows 22 recorded instrument
families in the roller. The space to its right shows recorded variants in the
upper row and articulations or playing styles in the lower row. A family with
one source variant but several playing styles keeps the upper variant as an
inert label; only the lower playing-style buttons are actions. A family with
one variant and one playing style has no redundant buttons. Examples are loud/quiet organ
with manual/pedal sets, open/Harmon-muted/straight-muted trumpet, and string
sustain/tremolo/pizzicato/spiccato choices.

All 75 VSCO source mappings remain accounted for. The browser exposes 66
canonical pitched choices: duplicate standalone maps whose recordings are
already exposed by an equivalent key-switch program are merged into that
program's named articulation. This is presentation curation, not removal of
recorded instruments. The dedicated VSCO percussion map remains owned by the
drum path and is never offered as a pitched keyboard program.

## Synth controls

The generated SCLOrk catalogue records the exact argument names and scalar
numeric defaults from the pinned sources. UI controls are derived from a
deliberately small reviewed vocabulary; unknown or ambiguous source arguments
are not presented as useful knobs merely because they exist.

The portable vocabulary is:

| UI parameter | Recognized native arguments | UI range |
|---|---|---|
| Attack | `att`, `attack`, `atk` | 0–3000 ms |
| Decay | `dec`, `decay` | 0–10000 ms |
| Sustain | `sus`, `sustain` | 0–1 |
| Release | `rel`, `release` | 0–15000 ms |
| Cutoff | `cutoff` | 20–20000 Hz, logarithmic |
| Filter RQ | `rq` | 0.001–1, logarithmic |
| Glide | `lagTime`, `slideTime`, `glide`, `freqLag`, `lagamount` | 0–1000 ms |
| Blend/mix/tone | same-named native argument | 0–1 |
| Width | `width`, `pw` | 0.05–0.95 |

ADSR controls, where the SynthDef implements them, are the first controls in
the lower row. Four additional sound controls fit in the upper row; any
further reviewed controls continue to the right of ADSR in the lower row.
Unchanged source defaults are omitted from transport messages. Millisecond UI
values are converted to seconds at the SC adapter, and normalized aliases are
resolved only to controls the selected SynthDef actually owns.

The owned acid voices implement ADSR, slide and accent directly. When an acid
voice is selected for bass, a small orange LED above the bass transport shows
that authored riff accent/slide events are meaningful. Other synths do not
receive acid articulation merely because they expose a glide knob.

The five pitched MIDI rows use this same browser, catalogue and parameter
model. The percussion row instead exposes the dedicated drum-kit roller. A
sample Piano row also exposes an owner-scoped `SUSTAIN ON/OFF` action. This is
the same SC sustain lifetime used by MIDI CC64; it is not a fabricated pedal
sample layer, because the two present Piano mappings contain no such layer.

## Ownership and evidence

Python owns immutable catalogue metadata, selection state, presets and UI
models. SuperCollider owns synthesis, samples, timing and note lifetimes. QML
never inspects SynthDefs or sample paths and SC never owns roller state.

`vsco_browser.py` validates complete pitched-source coverage and rejects
unknown or duplicate identities. `sclork-programs.json` is reproducibly
generated from pinned sources. Unit tests cover mode memory, family selection,
variant/articulation models, exact counts and prefix-free labels; SC compiler
tests prove normalized control aliases reach the native argument and preserve
unit conversion.
