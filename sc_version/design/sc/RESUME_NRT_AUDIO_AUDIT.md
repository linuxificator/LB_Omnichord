# Resume point: SCLOrk non-realtime audio audit

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

## Work in progress

Three uncommitted files add an `sc-audio` non-realtime render audit:

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

The second run passed that loading failure but exceeded the current 180-second
timeout. The score contains 109 sequential 0.75-second segments and includes
very expensive definitions such as the 100-oscillator `superSaw`. No live
audio device was opened.

## Exact continuation

1. Make the NRT audit shardable with environment variables for start/count, or
   have the Python test render deterministic batches in separate processes.
   Keep one report entry per all 109 catalog programs.
2. Keep `.scsyndef` file loading; do not return to `/d_recv`.
3. Run the shards headless outside the sandbox. Never boot a live SC server on
   this workstation until `pipewire-jack`/`pw-jack` is installed.
4. Investigate only programs that remain silent after correct file loading.
5. Commit and push the audit only after all 109 programs are represented and
   the suite either passes or reports an explicit, justified unsupported item.

Recommended first implementation: groups of 10-20 programs, with each NRT
score starting at time zero. This avoids one pathological definition consuming
the timeout for the whole catalog and makes failures attributable.

## Local prerequisite still missing

`pipewire-jack` is not installed. Installing it requires the user's sudo
password. Until then, headless `sclang` syntax tests and `scsynth -N` tests are
safe; live `Server.boot` tests are not.
