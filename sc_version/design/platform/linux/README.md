# Linux platform contract

Status: authoritative platform summary

Linux runs the Qt frontend and Gamma9001 AMY service as separate processes over
a private Unix socket. ALSA raw and sequencer MIDI live in the Linux adapter;
the portable application and musical policy do not inspect Linux devices.

`../../raspberry_pi/` owns the aarch64/AppImage-specific additions. Runtime and
test commands are in `../../../qt_frontend/README.md` and
`../../../qt_frontend/INSTALL.md`.
