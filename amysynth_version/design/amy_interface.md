# AMY Interface Design

## Wire command boundary

The Qt application produces AMY wire commands only.

The transport layer may be:

- local AMY process during development
- serial connection to ESP32-P4

Changing transport must not change behavior.

No GUI code may directly call AMY synthesis APIs.

## Bus master volume

The transport implements section master volume with AMY's final bus-volume
field, `y<bus>V<gain>Z`. OMNI owns buses 0–3 and MIDI owns buses 4–10. A patch
load or panic rebuild may replace bus state, so the transport reapplies the
current owning master gain after configuring a synth or rebuilding its buses.
This bus-level gain must not be folded into the individual synth `iV` values:
those values remain the independent role/row volume and balance controls.

## Testing

Wire command streams can be captured and compared between transports.
