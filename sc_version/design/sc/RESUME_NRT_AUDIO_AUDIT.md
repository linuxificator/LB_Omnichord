# SCLOrk non-realtime audio audit

Status recorded on 2026-09-14 on branch `version/supercollider`.

## Completed before this pause

- The local audio outage was diagnosed as raw JACK taking the HDMI ALSA device
  away from PipeWire when `sclang` started a live server.
- PipeWire, PipeWire Pulse and WirePlumber were restarted and HDMI audio was
  restored.
- `sc_version/qt_frontend/run_local.sh` now refuses unsafe live SuperCollider
  startup when PipeWire is active but `pw-jack` is unavailable. It also owns
  the complete `sclang`/`scsynth` process group and cleans it up on exit.
- All previously committed SuperCollider compiler, sequencer, protocol, sample
  ownership and migration tests are pushed through commit `98a62cd`.

## Implemented audit

The `sc-audio` suite contains a non-realtime render audit:

- `sc_version/supercollider/tests/sclork_nrt_render.scd`
- `sc_version/qt_frontend/tests/integration/test_supercollider_nrt.py`
- `sc_version/qt_frontend/tests/run_tests.py`

The Python analyzer deliberately uses only the standard library and is Python
3.14 compatible. It computes per-program RMS and peak values and writes
`test-artifacts/sclork-nrt-report.json`.

The first run exposed three silent programs. This was traced to the test using
`/d_recv` for SynthDefs larger than an OSC packet, not to silent synthesis.
The test now writes `.scsyndef` files and uses `/d_loadDir`, which is the normal
SuperCollider solution for large definitions.

The audit renders deterministic batches of twelve programs. This avoids making
the entire catalog share one timeout and attributes failures to a small range.
All 109 programs now produce finite, non-silent audio without opening a live
audio device.

The audit also found three upstream definitions with symbolic SynthDef-control
defaults. They compile in `sclang`, but cannot be serialized for `scsynth`.
Small owned adapters retain their behavior while representing those defaults
as numeric envelope curves:

- `sosBell`: `curve = \lin` becomes the equivalent numeric `curve = 0`.
- `kickBlocks`: `t2curve = \lin` becomes `t2curve = 0`.
- `kik3`: `sweepCurve = \exp` becomes a server-adjustable numeric exponential
  curve default of `-4`.

The generated report records RMS, peak, silence and clipping observations per
program. Silence is a blocking failure. Peak/clipping values are measurements,
not yet a claim that all programs have been perceptually loudness-normalized.

## Local prerequisite still missing

`pipewire-jack` is not installed. Installing it requires the user's sudo
password. Until then, headless `sclang` syntax tests and `scsynth -N` tests are
safe; live `Server.boot` tests are not.
