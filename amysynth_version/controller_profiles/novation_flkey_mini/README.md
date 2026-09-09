# Novation FLkey Mini General MIDI drums

This directory contains a device-side Custom Mode for the original Novation
FLkey Mini (`USB 1235:013b`). It makes all 16 pads send distinct General MIDI
percussion notes on MIDI channel 10.

LB Omnichord needs no FLkey-specific translation. Leave the final MIDI row on
its factory `Drum Kit 0` and channel `10`: the existing standard GM percussion
path resolves these identities to the active AMY/Gamma9001 drum bank. Other
MIDI controllers that already emit these notes behave identically.

The profile changes only the FLkey's pad **Custom Mode**. Its other pad modes
are unaffected. Enter the configured mode by holding **Shift** and pressing
the pad labelled **Custom**.

## Factory control bindings

Every shipped OMNI preset also contains the same MIDI binding declarations for
the FLkey Mini's factory controls. They are dormant until their first genuine
input, so an absent controller does not lock or preserve any screen value just
by loading a preset. They are not device-detection rules: any controller
emitting the same standard messages gets the same result.

| FLkey source | MIDI message | OMNI target |
| --- | --- | --- |
| Pitch strip | channel 1 Pitch Bend | shared tuning reference |
| Modulation strip | channel 1 CC1 | OMNI strum position |
| Knobs 1--4 | channel 1 CC21--24 | drum, bass, strum and chord volume |
| Knobs 5--8 | channel 1 CC25--28 | chord-type rows 1--4 |
| Play | channel 16 CC115 | rhythm start/stop |
| Stop | channel 16 CC117 | automatic CHORD ON/OFF |

The first genuine event activates its declared binding and applies the value
immediately. Moving a bound screen slider or chord-type wheel temporarily hands
that target to mouse/touch. Moving the preset-declared hardware control takes
it back and applies the incoming value immediately. The two transport buttons
and strum remain usable from both hardware and screen and can be unlinked only
from the grey controller bar. Pitch Bend follows the existing coupled-tuning
setting, so it controls both OMNI and MIDI tuning while coupling is enabled.
CC1 changes strum position only; the preset's strum volume remains in force.

The reviewed authoring copy of this shared mapping is
[`default_omni_midi_control_bindings.json`](../../qt_frontend/instruments/default_omni_midi_control_bindings.json).
Each factory OMNI preset embeds its own copy so storing or editing one preset
can change its bindings independently.

## Layout

Pad numbers follow the physical device and `ncc`: 1--8 are the upper row from
left to right; 9--16 are the lower row from left to right.

| Upper | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM note | 49 | 42 | 44 | 46 | 50 | 48 | 51 | 57 |
| Sound | Crash 1 | Closed hat | Pedal hat | Open hat | High tom | Hi-mid tom | Ride | Crash 2 |

| Lower | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM note | 37 | 39 | 38 | 36 | 35 | 45 | 43 | 41 |
| Sound | Side stick | Hand clap | Snare | Bass drum 1 | Acoustic bass drum | Low tom | High floor tom | Low floor tom |

The high row follows a conventional kit from left crash through hi-hats and
rack toms to ride/right crash. The low row puts auxiliary/snare voices to the
left, kicks in the center and floor toms to the right. Colors identify sound
families; every pressed pad turns white.

## Install the supplied SysEx on GNU/Linux

1. Stop LB Omnichord and other applications using the FLkey MIDI ports.
2. Connect the FLkey Mini and select its pad Custom Mode with **Shift** plus
   **Custom**.
3. Install `alsa-utils` if `amidi` is unavailable.
4. Find the bidirectional hardware port:

   ```sh
   amidi --list-devices
   ```

   On the development machine it appeared as:

   ```text
   IO  hw:2,0,0  FLkey Mini MIDI Out
   IO  hw:2,0,1  FLkey Mini DAW Out
   ```

   ALSA card numbers are not stable. Use the current `FLkey Mini MIDI Out`
   entry; do not copy `hw:2,0,0` blindly.

5. The recommended sender is the companion tool from `ncc`:

   ```sh
   cargo install ncc --version 0.1.4 --locked
   ncc-alsa-send hw:CARD,0,0 lb_omnichord_gm_drums.syx
   ```

   It sends the message and reads the device response required to activate the
   change. The equivalent low-level sequence documented by `ncc` is:

   ```sh
   amidi --port hw:CARD,0,0 --send lb_omnichord_gm_drums.syx
   amidi --port hw:CARD,0,0 --dump --timeout=1
   ```

6. Keep Custom Mode selected and start LB Omnichord. With `Drum Kit 0` on
   channel 10, every pad should now play the corresponding sound above.

If transfer fails, close every process holding either FLkey port, reconnect the
device, select Custom Mode again and retry. The official Novation Components
application can also restore or replace the Custom Mode.

## Rebuild and verify the artifact

The editable source is [`lb_omnichord_gm_drums.toml`](lb_omnichord_gm_drums.toml).
The committed SysEx was generated with `ncc 0.1.4`:

```sh
ncc -o lb_omnichord_gm_drums.syx lb_omnichord_gm_drums.toml
sha256sum --check SHA256SUMS
```

`ncc` is used only to build or transmit this optional profile. It is not an LB
Omnichord runtime or release dependency. Review the TOML diff, regenerate the
SysEx and update `SHA256SUMS` together whenever the layout changes.

## Provenance

- Novation documents that FLkey Mini has one editable pad Custom Mode whose
  note, channel, color and momentary/toggle behavior can be configured:
  https://support.novationmusic.com/hc/en-gb/articles/6741279709714-FLkey-Components-Guide
- `ncc` 0.1.4 documents full FLkey Mini support and compiles TOML profiles to
  device SysEx:
  https://github.com/taylordotfish/ncc
- The configuration syntax was derived from the CC0 FLkey Mini examples in
  `ncc`; this profile's note selection and documentation are maintained here.
