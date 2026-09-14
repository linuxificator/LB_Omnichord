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
- enough free storage for the external VSCO 2 Community Edition repository.

All 75 VSCO source mappings are catalogued. The PCM browser groups them into
22 instrument families and 66 canonical pitched variant/articulation choices;
equivalent standalone/key-switch views are merged without dropping recorded
instruments or reserving playable MIDI notes for engine-side key-switch state.

Run:

```bash
./run_local.sh --windowed
```

`OMNICHORD_SC_CONFIG` may point to another validated SC configuration. Engine
host addresses remain loopback-only in the current trust model.

The first source or packaged launch clones
`https://github.com/linuxificator/VSCO-2-CE` to `~/VSCO-2-CE` with the bundled
Dulwich client. It records the location in
`~/.omnichord/config/supercollider.json`. A user may change that path, but the
application verifies the clone's Git origin before using it. It never assumes
that a system `git` executable is installed.

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

Reference UI captures live in `screenshots/`. A deterministic offscreen pair
can be refreshed through a separately launched protocol-faithful test engine;
neither AMY nor an audio device is involved:

```bash
python capture_screenshots.py
```

## Packages and release

The SC workflow tests Linux x86_64, Raspberry Pi aarch64, macOS arm64 and
Windows x86_64. Release packages contain the Qt application, SuperCollider
3.14.1 language/server runtime and class/plugin trees. They communicate through
the native loopback OSC protocol described above; no substitute IPC layer is
introduced.

Publishing occurs only when the manually dispatched workflow receives
`release=true`. An ordinary push or merge performs platform tests and creates
no release. Linux packages use the host's normal audio-session integration
(`pw-jack` on PipeWire); Raspberry Pi receives no scheduler, CPU-isolation or
other machine-policy changes. The external VSCO sample library is deliberately
not embedded. See [third-party notices](./THIRD_PARTY_NOTICES.md) and
[current implementation status](../design/sc/STATUS.md).
