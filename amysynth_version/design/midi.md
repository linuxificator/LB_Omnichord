# MIDI Design

## Routing

MIDI input from local devices, platform APIs and ipMIDI multicast is merged and
translated into the same AMY wire-command path.

Each MIDI row has:

- instrument
- MIDI channel
- parameters
- volume
- its own AMY bus (4 through 9)

Default channels are 1-6. Duplicate channel assignments are allowed.

MIDI input tech selection may be overridden by `midi_input.tech_profile`. The
shipped config leaves it unset so the backend derives the closest profile from
Qt's platform abstraction; Linux and Raspberry Pi still resolve to `linux`. On Linux
the frontend reads every enabled raw byte-stream MIDI technology that this build
can open and combines those inputs into one application MIDI stream. The
currently implemented dependency-free readers are:

- ALSA raw MIDI character devices, configured by `alsa_raw_globs` and retaining
  the legacy `device_glob` fallback (`/dev/snd/midiC*D*`);
- OSS-compatible raw MIDI character devices, configured by `oss_midi_globs`
  (`/dev/midi`, `/dev/midi[0-9]*`, `/dev/amidi[0-9]*`);
- ipMIDI-compatible UDP/IPv4 multicast on every platform profile. Each UDP
  datagram is parsed as raw MIDI bytes, matching QmidiCtl and ipMIDI rather than
  RTP-MIDI. The shipped listener is `225.0.0.37:21928`.

Each physical byte stream owns its own running-status parser state before events
are merged. ipMIDI additionally isolates state by listener and UDP sender. This
prevents one device's or network sender's partial running-status message from
corrupting another input. The merged events parse Note On, Note Off,
velocity-zero Note Off, Control Change, Pitch Bend and running status. System
real-time bytes are ignored; SysEx and Program Change are not application
inputs. A channel-status byte by itself creates no indicator. The first value
seen for each channel/controller pair establishes a baseline; only a later,
different value counts as control movement. Pitch Bend is the exception to the
zero-baseline rule: its baseline is the MIDI center value, so moving a spring
loaded wheel or encoder away from center creates an indicator immediately.
This prevents controller-state snapshots sent during a VMPK channel switch from
creating indicators. Actual CC, Pitch Bend and MIDI-button changes drive the
left-to-right, capacity-aware indicators.
Changed MIDI control sources also enter the explicit MIDI-learn system defined
in `midi_control.md`. Unbound controls remain display-only. Bound continuous
sources map to one numeric target and still apply through the target's normal
backend/AMY wire path. Bound CC-style controller buttons map to explicit
application button targets and use the same backend actions as screen taps.
Ordinary Note On/Off events remain musical input and do not create button-learn
indicators; a controller that sends pads as notes needs an explicit whitelist or
translation layer before those notes may be treated as buttons.
Channel 0 in a row means omni/all incoming channels.

ALSA Sequencer-only applications such as VMPK do not create a raw-MIDI device.
The frontend therefore also creates an ALSA sequencer input client named
`LB Omnichord` with a `MIDI In` port. That port is visible in graph tools such as
`qpwgraph`; connect MIDI graph outputs such as BLE MIDI, Midi-Bridge or Midi
Through to that port. Incoming ALSA sequencer events are decoded back to MIDI
bytes and enter the same merged stream as raw MIDI devices. JACK MIDI,
CoreMIDI/macOS, WinMM/Windows and Android MIDI are common platform MIDI APIs, but
this PySide-only build has no bundled native bridges for those APIs.

## ipMIDI / QmidiCtl

The [QmidiCtl reference implementation](https://github.com/rncbc/qmidictl)
sends complete raw MIDI messages as UDP multicast payloads without an
additional protocol header. LB Omnichord follows that simple receive contract.
Its factory/user `amy_config.json` contains:

```json
"midi_input": {
  "ipmidi": {
    "enabled": true,
    "listeners": [
      {
        "address": "225.0.0.37",
        "port": 21928,
        "interface": "0.0.0.0"
      }
    ]
  }
}
```

`address` is an IPv4 multicast group, `port` is the virtual ipMIDI cable and
`interface` is the local IPv4 interface address used to join the group.
`0.0.0.0` selects the system's default multicast interface. Multiple listener
objects may be configured when more groups, interfaces or ipMIDI cable ports
are required. Invalid entries are recorded in the tech diagnostic reason and
ignored; valid entries keep listening. The tech is red when no valid listener
can bind and join a group.

The default is directly compatible with QmidiCtl's default `--udp-addr` and
`--udp-port`, so starting QmidiCtl without network overrides is sufficient.
ipMIDI multicast has no authentication or encryption; use it only on a trusted
local network and allow inbound UDP in the host firewall where required.

## MIDI input tech indicators

The MIDI screen shows platform-relevant MIDI input tech LEDs in the narrow gap
below MIDI synth row 6 and above the grey MIDI CC indicator bar.

- Red means the technology is relevant to the current platform but is not
  available to this build at runtime: no matching device, unreadable device,
  disabled MIDI input, or no bundled native bridge.
- Green means the technology has at least one readable input and the app is
  listening to it.
- Blinking green means bytes arrived through that technology recently.
- Technologies that are not relevant to the current platform are not shown.

The Linux indicator set is ALSA raw, ALSA sequencer, OSS MIDI and ipMIDI. Other
platform profiles show their native API indicator plus ipMIDI; an otherwise
unknown platform still shows ipMIDI because the socket implementation is
platform-independent. ALSA raw and OSS MIDI become green when readable
byte-stream devices exist. ALSA sequencer becomes green when the backend
successfully creates the `LB Omnichord` sequencer client/port. ipMIDI becomes
green after at least one configured multicast listener has bound and joined its
group. Its on-screen label is exactly `ipMIDI`.

## Pitch handling

Incoming MIDI notes are converted using the active tuning configuration before generating AMY commands.

The active chord supplies the intonation root; without an active chord the
fallback root is C. EQ at A=440 maps an incoming note to the same AMY note.
HARM/JV apply the selected table's frequency factor and normally produce a
fractional AMY note for non-root intervals. A root such as C4/60 over C remains
exactly 60 by design. Note-off uses the tuned pitch remembered at note-on.

## Separation

MIDI audio routing is separate from Omnichord routing. MIDI must not reuse Omnichord synth instances or effect buses.

MIDI drums use bus 10. The pink MIDI reverb section programs all six MIDI row
buses with one shared user setting and includes bus 10 only when DRM is enabled.
The similarly shaped OMNI reverb control is independent.

MIDI master volume is likewise independent: it writes the same final bus gain
to MIDI buses 4 through 10. OMNI master volume writes only buses 0 through 3.
Mute applies zero to the owned buses without discarding the selected master
value; unmute restores that value. Neither master may alter the other screen's
state or buses.

Each pitched MIDI synth has four voices. Both external MIDI and preview notes
are tracked by source note. The preview strum explicitly releases its oldest
live preview note before exceeding four notes; it must not rely on AMY voice
stealing or AMY's finite forgotten-note pool.

## Patch parameters

The numeric UI state is not automatically an AMY override. MIDI uses the same
`SynthState.transport_payload()` contract as OMNI: controls equal to a patch's
native value are omitted, while application corrections and actual edits are
sent explicitly. This prevents a visible default slider value from overwriting
internal Juno/DX7 patch state merely because a preset was loaded.
