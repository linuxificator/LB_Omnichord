# SuperCollider Qt frontend

This is the Qt/PySide6 frontend for the independent LB Omnichord
SuperCollider edition. Production constructs one `SuperColliderClient`; it
contains no AMY runtime, wire transport, serial selector or firmware path.

## Runtime boundary

`code/main.py` composes the application. `supercollider_client.py` transports
the typed versioned OSC protocol. A supervised headless `sclang` owns musical
time and voice lifetime. Python publishes immutable plans and semantic live
actions but never follows the beat. Its `supernova` child owns the multicore
audio graph.

`config/frontend.json` owns input and frontend policy.
`config/supercollider.json` owns the SC runtime and sample configuration. The
first launch creates private editable copies under `~/.omnichord/config` and
installs the pinned, shallow VSCO 2 CE runtime subset at the configured location
when required. An ordinary copied sample directory is valid when every
reachable manifest file matches; Git metadata is not required at runtime. Its
installation receipt lists every admitted relative path and hash.

## Run and test

On Linux, install SuperCollider and the distribution's PipeWire JACK
compatibility package when PipeWire is active, then run:

```bash
./run_local.sh --windowed
```

The checkout-local `.venv` is provisioned when needed. See
[`INSTALL.md`](INSTALL.md) and list test suites with:

```bash
python tests/run_tests.py --list
```

Compiler/NRT suites exercise real SuperCollider without taking the desktop
audio device. Process tests keep MIDI/OSC senders, the frontend and fake/real
engine in distinct processes. Deterministic UI captures use the same production
QML and a separate protocol-faithful fake engine:

```bash
python capture_screenshots.py
```

## Packages

The SC workflow tests Linux x86_64, Raspberry Pi aarch64, macOS arm64 and
Windows x86_64. Packages include Qt/Python plus SC 3.14.1, but not external VSCO
recordings. Publication happens only on manual `release=true`; ordinary pushes
only test. See [`../design/sc/BUILD_AND_RELEASE.md`](../design/sc/BUILD_AND_RELEASE.md),
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and
[`../design/sc/STATUS.md`](../design/sc/STATUS.md).
