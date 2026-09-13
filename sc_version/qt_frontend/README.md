# SuperCollider Qt frontend

This is the Qt/PySide6 frontend for the independent LB Omnichord
SuperCollider edition. It shares the established UI and music catalogues with
the AMY edition, but its production composition root uses only typed
SuperCollider services. Legacy AMY modules retained as characterization
oracles are excluded from the SC package and are not imported by its runtime.

## Process and timing boundary

`code/main.py` composes the frontend, `supercollider_client.py` transports the
versioned OSC protocol, and `supercollider_platform_adapter.py` owns one
headless SC process group. `sclang` owns the `TempoClock`, immutable sequence
definitions, execution state and voice handles; `scsynth` owns audio nodes,
buses and effects. Python compiles complete immutable plans but never follows
the beat or schedules note releases.

The Linux source launcher and frozen package both supervise SC separately from
Qt. On a PipeWire desktop they use the distribution's `pw-jack` compatibility
wrapper. They do not start a raw JACK server behind the user's back.

## Source run

Requirements:

- Python dependencies from `requirements.txt`;
- `sclang` and `scsynth` (3.13 is source-compatible; packages pin 3.14.1);
- the Linux distribution's PipeWire JACK compatibility tools when applicable;
- VSCO 2 Community Edition unpacked at
  `~/sample_lib/VSCO-2-CE-1.1.0`, or a different path configured in
  `config/supercollider.json`.

Run:

```bash
./run_local.sh --windowed
```

`OMNICHORD_SC_CONFIG` may point to another validated SC configuration. Engine
host addresses remain loopback-only in the current trust model.

## Test suites

The single runner is `tests/run_tests.py`:

```bash
python tests/run_tests.py --suite quality
python tests/run_tests.py --suite sc-frontend
python tests/run_tests.py --suite sc-compiler
python tests/run_tests.py --suite sc-sequencer
python tests/run_tests.py --suite sc-audio
python tests/run_tests.py --suite sc-banks
python tests/run_tests.py --suite sc-packaged
python tests/run_tests.py --suite platform-input-linux
```

SC compiler tests load every vendored SCLOrk definition. NRT tests render
audio without opening a device. Process-boundary tests launch a separate fake
SC service rather than placing test receivers in production application code.
Inherited AMY wire tests explicitly launch the frozen AMY frontend as a
behavioral oracle; they do not describe the SC production architecture.

## Linux package and release

The SC workflow builds pinned headless SuperCollider 3.14.1 and a package named
`LB_Omnichord.SC.R<timestamp>.Linux-x86_64.AppImage`. It verifies the bundled
runtime without opening an audio device and publishes only when the manually
dispatched workflow receives `release=true`. Ordinary pushes and merges run
tests and upload artifacts but do not create releases.

The current package is Linux x86_64 only and requires the host's normal audio
session integration (`pw-jack` on PipeWire). The VSCO sample library is not
embedded. See [third-party notices](./THIRD_PARTY_NOTICES.md) and
[current implementation status](../design/sc/STATUS.md).
