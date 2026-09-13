# Disabled shared-return regression

Status: fixed in pinned AMY commit
`5e3cd575fc744b9a0cd3e9014030acc7bf4dc5c2`

## Symptom

With reverb level at zero, enabling the DRM send made the drums sound roughly
twice as loud. This violated the aux model: dry output must remain unchanged
and a zero-level return must contribute silence. More generally, increasing
the wet level must add only the wet return; it must not turn down or replace
the direct signal.

## Cause

AMY clears each shared-return workspace at the start of a block and then sums
the configured post-fader bus sends into it. The built-in room processor had an
optimization that returned immediately when its level was zero. At that point
the workspace still held the unprocessed send input. Final mixing treated that
buffer as a wet return and added it to the unchanged dry buses, creating a
second dry path.

This fault was in the shared-return extension, not the historical per-bus
reverb DSP or the common bus summation primitive.

## Repair and proof

The zero-level branch now clears the workspace before returning. It still
avoids walking the reverb delay network, but its return is guaranteed silent.
Nonzero shared processing continues to call the wet-only reverb entry point;
the dry bus remains on the ordinary AMY master mix path.

AMY's native `tests/test_shared_reverb.c` now starts an oscillator on a bus
whose send is enabled while the room level is zero and asserts that the room
return buffer contains no samples. The test failed on the previous pinned
release and passes on the new one. The complete native shared-reverb test also
passes. The general `make test` target reached its Python installation stage
but could not install into the host's externally managed system Python; the
LB build uses an isolated environment and its pinned-AMY CI tests remain the
cross-platform authority.
