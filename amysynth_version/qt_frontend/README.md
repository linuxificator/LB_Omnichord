# LB_Omnichord — AMY / ESP32-P4 serial version

This version keeps the Qt Quick/PySide6 Omnichord UI and musical data, but the
sound engine is AMY running on the ESP32-P4. Sonic Pi and OSC are not used by
the running application.

## Audio/control path

```text
Qt/Python on Raspberry Pi
        |
        | native AMY wire protocol, 1,000,000 baud, 8N1
        | LF added only as UART transport framing
        v
Pi GPIO14 / TXD (physical pin 8)
        |
        v
ESP32-P4 GPIO15 / LP-UART RX
        |
        v
LP core -> HP mailbox -> amy_add_message()
        |
        v
AMY -> I2S -> PCM5102A
```

A command on the wire looks for example like:

```text
n60l1i3Z\n
```

`Z` is AMY's message terminator. The final LF is consumed by the LP-UART
transport and is not part of the AMY command.

## Serial configuration

Edit `amy_config.json`:

```json
"serial": {
  "port": "/dev/serial0",
  "baud": 1000000,
  "write_timeout": 0.5
}
```

The command line can override this:

```bash
.venv/bin/python main.py --serial-port /dev/serial0 --serial-baud 1000000
```

Any pyserial device can be used, e.g. `/dev/ttyAMA0` or `/dev/ttyUSB0`.

## Raspberry Pi wiring

```text
Raspberry Pi                         ESP32-P4 Pico M
---------------------------------------------------
GPIO14 / TXD / physical pin 8   ->  GPIO15 / LP-UART RX
GND / physical pin 6            ->  GND
```

Both boards use 3.3-V UART logic. Do not connect the Pi and P4 power rails for
this link.

Disable the Pi serial login console and enable the UART hardware before using
`/dev/serial0`.

## Installation

```bash
cd LB_Omnichord_AMY_v3_2
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py --serial-port /dev/serial0
```

The existing display switches such as `--fullscreen`, `--windowed`, `--x11`,
`--wayland`, `--software-renderer`, and `--opengl-renderer` remain available.

## Five independent AMY synths

The runtime now deliberately uses five permanently allocated AMY synth
instances:

```text
AMY synth 0   drums
AMY synth 1   bass accompaniment
AMY synth 2   strum
AMY synth 3   manually held chord
AMY synth 4   rhythm-triggered chord accompaniment
```

The manual-chord and rhythm-chord synths always receive the same patch,
parameters and volume, but they have separate voice pools and separate note
lifetimes. Therefore a held chord cannot extend a bass or automatic chord
note, and clearing/rebuilding the rhythm never turns off a manually held
chord.

Default voice counts are:

```text
drums          4   (one PCM oscillator per voice)
bass           1
strum          1
manual chord   7
rhythm chord   4
```

The drum synth deliberately does **not** load legacy patch 258. That factory
kit reserves 32 oscillators to provide the full GM-note lookup table. The
Omnichord instead configures synth 0 as four one-oscillator PCM voices and
sends the preset/native-note pair needed by each rhythm hit. The pairs come
from AMY's own non-GAMMA9001 patch-258 table, so the sounds are the same baked
PCM sources without paying for the 32-oscillator GM mapping layer.

This also keeps the oscillator budget bounded. With AMY's standard 120-osc
pool and the shipped Juno/DX7 catalogue, the worst case is 108 oscillators:
4 drums + 8 bass + 8 strum + 56 manual chord + 32 rhythm chord.

Normal operation never frees/recreates these five synths with `iv0`. Patch
changes hot-swap the melodic patch while retaining the allocated voice count.
Panic is special: after silencing/resetting the sequencer it explicitly
rebuilds all five synths, so it is also a recovery operation if AMY and the
host ever got out of sync.

## Rhythm behaviour

Rhythm timing is compiled into AMY's 48-PPQ sequencer. Linux/Python is not
used as the beat clock.

On every rhythm rebuild the backend first sends explicit all-off commands to
**only**:

```text
bass synth          i1
rhythm-chord synth  i4
```

and then replaces the sequencer pattern. This is important because clearing a
sequencer also removes any future scheduled note-off events. Silencing those
two accompaniment synths first prevents an old note from becoming permanent.

Changing the active chord rebuilds the pattern when either bass or automatic
rhythm chords are active, because both lanes derive pitch from the selected
chord.

Bass notes are always sequencer-gated on synth 1. The duration of a physical
chord-button press has no connection to bass note lifetime.

On a fresh transport start the backend sends:

```text
sequencer stop
RESET_SEQUENCER
RESET_TIMEBASE
<10 ms reset guard>
new H... pattern definitions
sequencer start
```

The guard begins only after the reset commands were physically sent over the
UART. Direct performance commands remain high priority while pattern data is
being queued.

## Strum behaviour

Strum uses only synth 2. Each strum contact sends an immediate note-on and an
explicit delayed note-off. Default gate:

```json
"strum_gate_ms": 220
```

This keeps long-release factory patches from leaving strum voices held
forever while preserving immediate attack timing.

## AMY instrument catalogue

`synths.json` now contains **123 actual AMY factory instruments** rather than
Sonic-Pi synth names:

- 103 selected Juno factory patches;
- 20 selected DX7 factory patches;
- names in the UI are AMY's instrument/preset names, e.g. `Juno · A15 Moving
  Strings`, `Juno · A45 Koto`, `DX7 · E.PIANO 1`, `DX7 · BASS 2`, and
  `DX7 · SHIMMER`.

The catalogue was deliberately selected for useful variety rather than simply
showing every near-duplicate patch.

### Juno controls

The upper row maps to AMY's Juno voice structure:

```text
Cutoff | Resonance | LFO Rate | Vibrato | VCF LFO | Pulse Width | PWM Depth | Portamento
```

`LFO Rate` controls oscillator 1's modulation speed. It is intentionally paired with explicit modulation-depth controls: `Vibrato`, `VCF LFO` and `PWM Depth`. A rate change by itself can be inaudible when a patch has zero modulation depth.

### DX7 controls

```text
Algorithm | Feedback | LFO Rate | Vibrato | Portamento
```

The lower row is always `Attack | Decay | Sustain | Release`. Juno ADSR edits the patch's gather/output envelope. DX7 ADSR is an optional global output envelope layered over the native six operator envelopes. A value that has not been touched leaves the factory patch setting/routing alone.

Chord controls are mirrored to synths 3 and 4 so manual and automatic chords sound the same while remaining completely independent voice pools.

## Factory presets and old presets

The 18 supplied factory presets have been converted to AMY instruments and
use varied Juno/DX7 sounds appropriate to their musical style.

Older presets already present in `~/.omnichord` may still contain Sonic-Pi-era
synth keys. The loader contains a hidden compatibility translation from those
old keys to AMY patch keys. They are not shown in the synth catalogue. After
storing such a preset again, the saved selection uses the AMY key.

Old Sonic-Pi-specific parameter values are ignored because they have no
well-defined AMY equivalent.

## ESP32-P4 UART command task stack

The HP task that calls `amy_add_message()` must have enough stack for Juno/DX7
patch parsing. 4096 bytes was observed to overflow in the patch parser.
Use:

```c
#define AMY_COMMAND_TASK_STACK (16 * 1024)
```

See `ESP32_P4_REQUIRED_CHANGE.txt`.

## Direct transport test

Before blaming the Qt application, this should produce a tone through the
same LP-UART path:

```bash
stty -F /dev/serial0 1000000 raw -echo cs8 -cstopb -parenb -crtscts
printf 'v0w0f440Q0l0.2Z\n' > /dev/serial0
```

## Main files

```text
amy_serial.py       serial writer, AMY command backend and AMY sequencer compiler
amy_config.json     serial settings, fixed synth IDs/voice counts and patch map
synths.json         curated AMY Juno/DX7 catalogue and AMY-specific controls
main.py             Qt backend and preset/touch/rhythm state
rhythms.json        rhythm patterns
chords.csv          chord definitions
default_presets/    AMY-based factory presets
```

`sonic_pi_receiver.rb` and `README_SONIC_PI_ORIGINAL.md` are kept only as
historical reference and are not run by this version.

## v3.3

v3.3 adds asynchronous native-AMY wire logging (`~/.omnichord/amy_debug.log`),
fixes first-note strum delivery, removes the known-silent Juno A82 Resonance
Funk patch, displays instrument names before/without engine codes, adds
engine-specific + ADSR controls, and makes Panic hard-reset/reinitialize all
five AMY synth instances.  See `V3_3_FIX.md` for details and debug commands.


## v3.5 AMY patch compatibility, Panic and strum

See `V3_5_FIX.md`. v3.5 keeps Resonance Funk, Harpsichord 1 and Orchestral Pad in the catalogue and applies narrowly-scoped corrections after their normal factory patch load. It also changes Panic/startup to a clean `RESET_ALL_OSCS | RESET_SEQUENCER` followed by redefinition of synths 0..4, and host-manages the two strum voices so long sweeps never depend on AMY's stolen-note bookkeeping.
