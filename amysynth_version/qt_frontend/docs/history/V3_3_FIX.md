# AMY Omnichord v3.3 fixes

## Strum debug and touch fix

`amy_config.json` contains:

```json
"debug": {
  "log_amy_commands": true,
  "amy_command_log": "~/.omnichord/amy_debug.log",
  "log_logical_events": true
}
```

The log is append-only and is written by a separate logger thread, so file I/O
is not performed by the UART writer thread.  At startup the program prints the
resolved log path.

To watch only strum traffic on the Raspberry Pi:

```bash
tail -f ~/.omnichord/amy_debug.log | grep -E 'strum/note|i2Z'
```

A touch on the strum pad should produce a pair such as:

```text
EVENT        /strum/note '64'
TX-HIGH      n64l1i2Z
```

The touch handler now sounds its first note on press (`strumStart`) rather than
waiting for a move/release event.  Moving across strings adds subsequent notes.

## Synth catalogue

The visible selector label is now the instrument name only.  Engine/program
metadata remains in `synths.json`, for example:

```json
{
  "key": "juno_004",
  "label": "Moving Strings",
  "engine": "Juno",
  "program": "A15",
  "patch": 4
}
```

Juno patch 57 / A82 Resonance Funk has been removed from the selectable bank.
Its AMY factory definition has zero constant amplitude on all four source
oscillators, and was silent in this hardware build.  Old v3.x presets that
selected it are migrated to Juno A47 Funky I (`juno_030`).

## Controls

Every Juno and DX7 entry now exposes 8 controls in two rows:

**Upper / engine-specific row**

- Juno: Cutoff, Resonance, LFO rate, Portamento
- DX7: Feedback, Algorithm, LFO rate, Portamento

**Lower / common row**

- Attack
- Decay
- Sustain
- Release

The initial value `PATCH` means the factory patch value is left untouched.
Moving an ADSR control activates the AMY envelope override. Moving all ADSR
controls back to PATCH reloads the factory patch envelope.

Juno portamento is sent to its pitch oscillators 2, 3 and 4; it is no longer
incorrectly sent to oscillator 0.

## Panic

Panic now performs a hard AMY restart with `RESET_AMY` and then recreates the
five fixed synths after a 25 ms host-side guard:

1. drums (synth 0)
2. bass (synth 1)
3. strum (synth 2)
4. manual chords (synth 3)
5. rhythm chords (synth 4)

This makes Panic a recovery/resynchronization operation instead of just an
all-notes-off.

## Qt warnings

The QML handlers reported by Qt 6 as relying on deprecated implicit signal
parameter injection now declare their parameters explicitly.
