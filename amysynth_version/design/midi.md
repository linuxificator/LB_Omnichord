# MIDI Design

Status: authoritative MIDI input and routing contract
Owner: MIDI input/player subsystem
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-01

## Routing

USB MIDI input is received on the Raspberry Pi and translated into AMY wire commands.

Each MIDI row has:

- instrument
- MIDI channel
- parameters
- volume
- its own AMY bus (4 through 9)

Default channels are 1-6. Duplicate channel assignments are allowed.

MIDI input tech selection is controlled by `midi_input.tech_profile`. The
shipped value is `auto`: ordinary packages derive the closest profile from
Qt's platform abstraction and Python's runtime platform. A non-`auto` value is
a deliberate test or diagnostic override, not a platform default for a
release. This keeps one common configuration portable across Linux, macOS,
Windows and Android packages. On Linux the frontend reads every enabled raw
byte-stream MIDI technology that this build can open and combines those inputs
into one application MIDI stream. The currently implemented dependency-free
readers are:

- ALSA raw MIDI character devices, configured by `alsa_raw_globs` and retaining
  the legacy `device_glob` fallback (`/dev/snd/midiC*D*`);
- OSS-compatible raw MIDI character devices, configured by `oss_midi_globs`
  (`/dev/midi`, `/dev/midi[0-9]*`, `/dev/amidi[0-9]*`).

Each physical byte stream owns its own running-status parser state before events
are merged. This prevents one device's partial running-status message from
corrupting another device's input. The merged events parse Note On, Note Off,
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

Native readers never call the MIDI QObject or musical engine. Every reader
normalizes input to one frozen `MidiInputEvent` value. A lock-protected sequence
number gives events from simultaneous readers one total order; the application
composition root supplies a small `MidiInputPort` to the common backend, and a
single Qt signal queues that stream onto the backend's owning thread. Notes,
controls, explicitly translated buttons and activity all use this same
boundary. The receiver also drains by sequence number, so delayed delivery
cannot invert a note and control event. Ordinary native adapters intentionally
emit notes rather than buttons; button events exist for an explicit future
translation adapter, not for automatic keyboard-note classification.

The portable MIDI player imports no native API and probes no device path. The
Linux adapter owns raw-device discovery, ALSA `ctypes` calls, reader threads and
their start/status/close lifecycle. Package composition selects that adapter
once. macOS, Windows and Android currently receive adapters with the same
lifecycle/status contract that explicitly report their unbundled native
technology as unavailable. Unsupported is capability data, not a startup
exception. `close()` is idempotent, closes the event emitter before native
readers, and therefore prevents callbacks after shutdown begins.

ALSA Sequencer-only applications such as VMPK do not create a raw-MIDI device.
The frontend therefore also creates an ALSA sequencer input client named
`LB Omnichord` with a `MIDI In` port. That port is visible in graph tools such as
`qpwgraph`; connect MIDI graph outputs such as BLE MIDI, Midi-Bridge or Midi
Through to that port. Incoming ALSA sequencer events are decoded back to MIDI
bytes and enter the same merged stream as raw MIDI devices. JACK MIDI,
CoreMIDI/macOS, WinMM/Windows and Android MIDI are common platform MIDI APIs, but
this PySide-only build has no bundled native bridges for those APIs.

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

The Linux indicator set is ALSA raw, ALSA sequencer and OSS MIDI. ALSA raw and
OSS MIDI become green when readable byte-stream devices exist. ALSA sequencer
becomes green when the backend successfully creates the `LB Omnichord` sequencer
client/port.

Release acceptance loads the real shipped configuration inside every final
package and verifies that this platform profile, and no Linux technology on a
non-Linux target, is published. It then exercises the common packaged CC and
explicit controller-button route through the public simulation boundary.
Linux additionally has an end-to-end Qt test that writes real MIDI bytes to a
PTY-backed raw device. These tests do not claim physical CoreMIDI, WinMM or
Android MIDI support: those bridges are not bundled, so their tested result is
red/unavailable. A future native adapter must add platform-runner contract
tests and physical-device acceptance rather than reclassifying simulation as
hardware evidence.

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
