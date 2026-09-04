# AMY Interface Design

Status: authoritative AMY wire/transport boundary contract
Owner: AMY command and transport integration
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-04

## Wire command boundary

The Qt application produces AMY wire commands only.

The transport layer may be:

- local AMY process during development
- serial connection to ESP32-P4

Changing transport must not change behavior.

No GUI code may directly call AMY synthesis APIs.

## Local wire framing

AMY reserves 1024 bytes for a message including its terminating NUL, so every
local IPC request is limited to 1023 printable ASCII bytes including its final
`Z`. Packet-preserving Unix IPC carries exactly one validated request per
packet. Unix stream and Windows named-pipe IPC use one LF-terminated request;
CRLF is accepted and normalized. Empty stream records are ignored.

Malformed, non-ASCII, overlong, non-`Z`-terminated or connection-truncated
records are rejected before they reach AMY. Stream buffering is capped while a
record is incomplete. This local/private boundary is defense in depth and must
not change any valid command or its ordering.

## Bus master volume

The transport implements section master volume with AMY's final bus-volume
field, `y<bus>V<gain>Z`. OMNI owns buses 0–3 and MIDI owns buses 4–10. A patch
load or panic rebuild may replace bus state, so the transport reapplies the
current owning master gain after configuring a synth or rebuilding its buses.
This bus-level gain must not be folded into the individual synth `iV` values:
those values remain the independent role/row volume and balance controls.

## Reusable sequences

Reusable phrases remain wire-only. Repeated ordinary tagged `H` events
cumulate a persistent AMY definition; `HR` resets future contents and `HC`
uses the strict integer run state `0`/`1` to stop/start, with operation `2`
reserved for finite gating. Its final field selects alignment. This run state
is not note velocity; fractional values are invalid. LB owns musical data and
policy; AMY owns local phase, execution lifetime, repeats and immutable
execution snapshots. The complete boundary and regression rules are in
`sequencer_sequences.md`.

## Testing

Wire command streams can be captured and compared between transports.
