# AMY aux returns and ESP32-P4 reverb limit

Status: implemented on AMY release branch
`releases/amy_omnichord_R20260908T212305`. The immutable AMY commit must be
read from `packaging/release_inputs.json` once that release is adopted by the
Omnichord build.

## Architecture decision

AMY's existing bus render buffers and summation kernel remain authoritative.
The shared routing code adds weighted, post-fader aux sends from arbitrary bus
subsets and adds each processed return once to the normal master bus. It does
not introduce a separate Omnichord mixer or copy rendered buses into a second
mix graph.

The runtime return count is deliberately not fixed at two. The historical
configuration name `max_reverb_rooms` and the `hR`/`hS` wire family remain for
compatibility, but the underlying routing is an aux-send/return abstraction:

- a default return uses AMY's built-in stereo reverb;
- a host may mark a return as external and process its accumulated block in
  place with a realtime callback;
- that callback may implement a lighter reverb or a different end effect;
- the external callback owns its parameters and return gain;
- the existing `hS` command still selects the return and send weight per bus;
- the existing `hR` command configures only AMY's built-in reverb.

This keeps the generally useful mechanism in AMY while keeping the choice of
room simulation or other end effect with the AMY host.

## Resource limits

`AMY_MAX_REVERBS` is a compile-time maximum for the expensive built-in stereo
reverb networks. It counts both shared built-in returns and legacy per-bus
reverbs. External return processors do not count. The default is effectively
unlimited, so desktop and mobile hosts retain runtime freedom.

The ESP32-P4 Omnichord build explicitly sets `AMY_MAX_REVERBS=2`. It also
provides two separately reserved 128 KiB internal-SRAM arenas. This makes the
P4's actual memory and realtime envelope explicit and prevents a later legacy
per-bus reverb command from silently allocating a third built-in network in
PSRAM. The arenas hold the reverb state, delay data, and one render block; they
do not introduce an extra copy in the audio path.

The first two returns run concurrently on AMY's two existing ESP render tasks.
Additional returns remain supported generically and run serially. On other
platforms the same routing and DSP are used, without P4 memory placement.

## Verification contract

- Legacy `h` per-bus reverb behavior stays the default when
  `max_reverb_rooms == 0`.
- Tests cover two shared reverbs, a host-processed external return, a third
  runtime-configured return, weighted sends, fixed arenas, deferred timing
  diagnostics, and the compile-time built-in-reverb ceiling.
- The P4 firmware contract checks both the two reserved banks and
  `AMY_MAX_REVERBS=2` in its generated AMY component.
- No silent-signal shortcut is counted as capacity. Reverb tails continue to
  be processed while the return is enabled, even when the current input block
  is silent.

## Remaining platform work

After the AMY release SHA is final, update `packaging/release_inputs.json` and
its generated release documentation, then run the generic AMY regression
matrix plus a clean ESP32-P4 v1/v3 build. Raspberry Pi CPU affinity remains a
separate host-level performance experiment; it is not part of generic AMY.
