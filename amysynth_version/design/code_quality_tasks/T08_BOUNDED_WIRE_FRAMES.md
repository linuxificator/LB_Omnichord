# T08 result: bounded local AMY wire framing

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: AMY command and transport integration
Applicability: Unix packet/stream IPC and Windows named-pipe service

## Outcome

- Added a portable, strict-mypy-clean wire-frame module with one protocol
  limit: 1023 printable ASCII request bytes including the final `Z`. This is
  AMY's `MAX_MESSAGE_LEN - 1`, retaining space for AMY's terminating NUL.
- Replaced the Unix stream service's unbounded `buffered += packet` loop with
  an incremental parser whose retained state cannot exceed one maximum frame.
- Validates packet-preserving Unix requests through the same payload contract
  without changing their packet framing.
- Accepts split and combined LF frames, CRLF and empty keepalive records;
  rejects missing `Z`, non-ASCII/non-printable bytes, overlong frames and a
  connection that closes mid-record.
- A parser becomes unusable after a malformed frame, preventing accidental
  recovery from an ambiguous byte stream.
- Tightened the already bounded Windows service's temporary line buffer from
  `MAX_MESSAGE_LEN * 2` to exactly `MAX_MESSAGE_LEN`. Its existing length and
  final-`Z` checks now enforce precisely the same maximum valid payload.
- Documented framing in the authoritative AMY interface contract and native
  Windows transport documentation.
- Preserved every valid AMY request and command order byte-for-byte.

## Verification

- frame boundary/table tests: 7 passed
- local AMY service tests: 3 passed, covering split/combined stream delivery,
  packet delivery and overlong rejection before `amy.send_wire`
- real Unix packet/stream and QLocalSocket writer tests: passed
- complete quality, unit, frontend, serial, preset, native-controls and
  native-rhythm gate: passed
- the new production module passes strict mypy
- `git diff --check`

## Findings and progressive insight

- The Unix packet path previously decoded whatever one local packet contained;
  it now rejects invalid length/ASCII/terminator just like the stream path.
  Empty packets still retain socket EOF semantics and are never presented as
  application requests.
- Printable ASCII is deliberately narrower than an ASCII codec decode: embedded
  NUL, tab and carriage return are not valid command payload. A single trailing
  CR remains accepted only as the CRLF line ending.
- The service currently fails fast when its sole private frontend sends a
  malformed record. That is deterministic and avoids silently continuing after
  protocol corruption. T16 should expose the terminal reason through transport
  health rather than weakening parser validation.
- Repeated read timeouts still keep an accepted local connection alive. The
  task required memory bounds, not an arbitrary musical-session idle timeout;
  no idle disconnect was introduced.
- T16 should compose this validator with its future Unix/QLocalSocket sinks and
  preserve packet versus LF transport details. It must not add a second frame
  limit.

## Follow-up task effects

No new queue item is required. T16 owns terminal health/reporting and must reuse
`MAX_WIRE_REQUEST_BYTES`, `validate_wire_request` and `LfWireFrameParser` at
the service/sink boundaries.
