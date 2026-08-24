# AMY Interface Design

## Wire command boundary

The Qt application produces AMY wire commands only.

The transport layer may be:

- local AMY process during development
- serial connection to ESP32-P4

Changing transport must not change behavior.

No GUI code may directly call AMY synthesis APIs.

## Testing

Wire command streams can be captured and compared between transports.
