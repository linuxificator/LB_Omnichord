# Install and run the SuperCollider edition

## Linux and Raspberry Pi source checkout

Install Python 3, SuperCollider (`sclang`, `scsynth` and `supernova`) and the distribution's
PipeWire JACK compatibility package when the desktop uses PipeWire. From this
directory run:

```bash
./run_local.sh --windowed
```

The launcher creates the repository `.venv` when absent, validates declared
requirements, prepares the user configuration and starts exactly one owned
headless SC process group. It refuses to start a competing raw JACK server on a
PipeWire desktop.

On first launch the application streams the pinned VSCO 2 CE runtime snapshot
from GitHub. Its default location is `~/VSCO-2-CE`; edit the active release's
`~/.omnichord/<release-name>/config/supercollider.json` to use another
checkout or ordinary copy. Only the required files are extracted and neither
Git history nor a `.git` directory is retained. All required files are
verified against the bundled content manifest.

## Packaged application

Download the package for Linux x86_64, Raspberry Pi aarch64, macOS arm64 or
Windows x86_64 and its matching SHA-256 file from one SC release. Packages are
self-contained for Qt/Python and SuperCollider; they do not download Python
packages. VSCO recordings remain a separate CC0 asset installed on first use.

The package self-check used by CI can be invoked with `--verify-package`. It
validates bundled executables, configuration migrations, frontend config,
catalogue loading and the SC bootstrap without opening an audio device.

## Configuration

- `~/.omnichord/<release-name>/config/frontend.json`: MIDI/OSC input and frontend policy.
- `~/.omnichord/<release-name>/config/supercollider.json`: SC process/server/sample policy.
- `~/.omnichord/<release-name>/omni_presets/`: OMNI presets.
- `~/.omnichord/<release-name>/midi_presets/`: MIDI presets.

Every packaged release embeds its own immutable release name and starts with
fresh defaults in a separate directory. It deliberately does not import an
older release's configuration or presets. Source checkouts use
`development-SC`, so local development also remains separate from releases.

Invalid or future configuration is rejected with a JSON path. Delete only the
specific active-release user config you intentionally want reseeded; the
application does not silently overwrite existing settings.
