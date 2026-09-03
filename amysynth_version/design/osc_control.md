# OSC control input and binding

Status: authoritative OSC input and control-binding contract
Owner: OSC input adapter and shared external-control binding subsystem
Applies to: active `amysynth_version` implementation on all platforms
Last verified: 2026-09-03

## Purpose and boundary

OSC is a second portable control-input source beside MIDI. It controls the same
numeric and application-button targets through the same one-to-one learn,
binding, manual-takeover, persistence and preset rules. It does not create a
second musical-state path, send AMY commands directly or couple the frontend to
the AMY process. A mapped OSC value calls the same frontend setter that a mapped
MIDI value or screen gesture uses; synthesis remains wire-only on every target.

The OSC adapter owns UDP and OSC decoding. It emits immutable input events into
the existing Qt-thread boundary. The shared binding state owns visibility,
learn, ownership and application mapping. QML owns only rendering and semantic
clicks. No platform-specific branch is permitted in the portable OSC adapter,
binding state or QML.

## Network configuration

`osc_input` in `config/amy_config.json` is the only runtime authority:

```json
"osc_input": {
  "enabled": true,
  "listen_address": "0.0.0.0",
  "listen_port": 8000
}
```

The default listens on every local IPv4 interface because remote controllers
are a primary OSC use case. UDP port 8000 is a widespread controller-to-host
convention, including common TouchOSC setups; OSC itself defines no mandatory
port. Both values are editable. `127.0.0.1` restricts input to local software.
The complete `osc_input` section is optional in a revision-6 user document. If
the section, listen address or listen port is absent, OSC is explicitly
unconfigured: no socket opens and no `OSC` technology is shown. Consumers do
not silently restore the shipped endpoint. An explicitly disabled endpoint is
also absent from the technology row.

OSC UDP has no authentication, encryption or delivery guarantee. Listening on
`0.0.0.0` therefore means that any host which can reach the configured port can
attempt to control the application. Use loopback or firewall policy on an
untrusted network. Failure to bind is observable as a failed OSC capability and
must not be reported as successful listening.

The macOS application bundle declares why it receives local-network traffic so
macOS 15 and later can present the system Local Network permission. The current
Android release targets API 36, where manifest permission `INTERNET` grants
local-network UDP access. When the target moves to API 37 or later, packaging
must add and the application must request `ACCESS_LOCAL_NETWORK`; adding it to
the current target pre-emptively is explicitly not permitted by the Android
platform contract.

## Accepted OSC messages

- OSC 1.0 messages and bundles are accepted over UDP.
- Each boolean, integer or finite floating-point argument is a source.
- Source identity is the OSC address plus its zero-based argument index. Thus
  `/surface/xy` with two values exposes `/surface/xy[0]` and
  `/surface/xy[1]` independently.
- Boolean values are switch signals. Numeric values use the conventional
  normalized `0.0..1.0` controller range and are clamped at its ends.
- A numeric source bound to a button uses zero as released and any positive
  value as pressed, matching MIDI controller-button semantics.
- String, blob, MIDI-packet and non-finite numeric arguments are ignored. A
  packet with no accepted argument does not create an indicator.
- Bundle timetags do not schedule UI control changes; control messages are
  applied in received packet order when the packet reaches the application.
- OSC wildcard addresses are not interpreted on input. The exact received
  address is the source identity.

Like MIDI CC, the first continuous value establishes a baseline and only a
later different value is genuine movement. A first pressed boolean is admitted
immediately so a momentary switch can be learned without requiring an earlier
release packet. Repeated identical values do not update LRU age or location
feedback.

## Shared indicator and binding behavior

OSC activity appears in the same capacity-aware grey control bar as MIDI. MIDI
keeps its F06 family; OSC uses the compact F01 LB Radio / Utility family. OSC
rotaries and pushbuttons intentionally use flat material colors with no virtual
lighting, highlights or cast/contact shadows. Mechanical geometry, pointer or
pressed position still identifies the control type.

Every source otherwise follows the existing external-control contract:

- a single tap on grey/blue starts the unique red learn state;
- a single tap on red cancels learn;
- a single tap on green unlinks and turns the indicator blue;
- touching a supported target while a source is red binds it and consumes the
  gesture;
- one source owns at most one target and one target has at most one MIDI or OSC
  owner globally;
- genuinely moving a bound target through mouse or touch unlinks its external
  owner before applying the manual value;
- hidden bindings remain active and preset/location feedback remains intact;
- LRU, eviction, blue timeout and button takeover semantics are identical.

The label is the exact OSC address for argument zero and appends `[N]` for
later arguments. It may elide visually but the persisted identity is never
shortened.

## Input-technology and mode-button feedback

One `OSC` item shares the MIDI input-technology row when a complete, enabled
listen endpoint is configured. Its LED is invisible while the socket is merely
listening, flashes green for 450 ms after accepted OSC control data, and is red
when the socket cannot bind or the configured network is unavailable. The
network state is polled through Qt's portable network-interface API; a
loopback-only endpoint remains available without an external interface, while
the wildcard endpoint requires one running non-loopback IPv4 interface.

On the OMNI screen the rainbow mode button says `OSC` above `MIDI`, using the
same typeface at a smaller size. The button deliberately does not gain separate
protocol LEDs: its blinking red learn LED represents the one shared MIDI/OSC
learn state, and its blinking green location LED reports bindings from either
protocol. OSC movement therefore restarts the same cross-screen location
feedback as MIDI movement.

## Persistence and compatibility

OSC bindings use the existing screen-owned optional
`midi_control_bindings` preset field for backward compatibility. The field is
historically named but now stores external-control bindings. Existing MIDI
entries keep their exact JSON shape. An OSC entry adds:

```json
{
  "source_type": "osc",
  "address": "/surface/filter",
  "argument": 0,
  "value_type": "continuous",
  "target": {"screen": "omni", "kind": "reverb_damping"}
}
```

`value_type` is `continuous` or `button`. Runtime values, socket peers,
indicator order, red learn state and blue timers are not persisted. Invalid OSC
addresses or argument indexes are ignored while loading a preset; they never
invalidate unrelated legacy MIDI bindings.

## Lifecycle and failure behavior

The portable input port has constructed, starting, ready, failed, closing and
closed states. One worker owns the UDP socket. Closing is idempotent, unblocks
the worker and prevents callbacks after close. Malformed datagrams are rejected
without terminating the port. The Qt object thread alone mutates presentation,
binding and musical/application state.

## Verification

Tests must prove:

- exact config migration/default/validation and no consumer fallback;
- omission/disablement, idle-hidden/activity-green/network-red technology
  presentation and live network recovery;
- real loopback UDP reception, message/bundle decoding, ordering, malformed
  packet survival, configured bind address/port and idempotent shutdown;
- continuous and switch baselines, multi-argument identity and normalized
  mapping;
- global one-to-one ownership across MIDI and OSC, persistence round trips,
  preset handoff, manual takeover and legacy MIDI JSON compatibility;
- the shared QML bar renders MIDI as F06 and OSC as flat F01, with identical
  click transitions and no shadow/effect nodes for F01;
- the OMNI rainbow button renders `OSC` above `MIDI` and reuses the shared red
  learn and green binding-location LEDs;
- import/install and exercised parser behavior in every release package,
  including Android; and
- unchanged MIDI tests, AMY wire convergence and all code-quality gates.
