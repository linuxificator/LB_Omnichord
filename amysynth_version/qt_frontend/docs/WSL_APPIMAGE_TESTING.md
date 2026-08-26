# Test the Linux AppImage on Windows with WSL2 and WSLg

> **Testers wanted:** the Linux x86_64 AppImage may run on Windows through
> WSL2/WSLg, but this is not yet a validated or supported release target. If
> you try it, please report both successful and unsuccessful results. Real
> feedback about GUI behavior, audio quality, latency and MIDI is valuable.

This is a Linux application running inside WSL, not a native Windows build.
The initial test scope is an Intel/AMD (`x86_64`) Windows 11 computer running a
current WSL2 Ubuntu distribution with WSLg. Do not use WSL1. Windows-on-ARM and
the Raspberry Pi `aarch64` AppImage are outside this first test scope.

WSLg officially supports integrated Wayland/X11 windows and PulseAudio output:

- [Run Linux GUI apps with WSL](https://learn.microsoft.com/windows/wsl/tutorials/gui-apps)
- [Microsoft WSLg architecture and audio](https://github.com/microsoft/wslg)

LB Omnichord's AppImage contains the Qt frontend and the compatible AMY
service. They remain separate Linux processes and communicate through a private
Unix socket. AMY's Linux audio backend uses ALSA; under WSLg the ALSA PulseAudio
plugin must route that output to WSLg's PulseAudio server.

## 1. Prepare WSL2 and WSLg

From an Administrator PowerShell terminal, install or update WSL:

```powershell
wsl --install -d Ubuntu
wsl --update
wsl --shutdown
```

The install command is only needed when WSL is not installed yet. Open Ubuntu
again, then confirm from PowerShell that it uses WSL2:

```powershell
wsl --version
wsl --list --verbose
```

Inside Ubuntu, verify the CPU architecture and WSLg environment:

```bash
uname -m
printf 'WAYLAND_DISPLAY=%s\nPULSE_SERVER=%s\n' \
  "$WAYLAND_DISPLAY" "$PULSE_SERVER"
```

For this guide, `uname -m` must report `x86_64`. `WAYLAND_DISPLAY` and
`PULSE_SERVER` should not be empty.

## 2. Install the Linux runtime packages

On Ubuntu 24.04:

```bash
sudo apt update
sudo apt install libegl1 libfuse2t64 libasound2-plugins alsa-utils
```

On Ubuntu 22.04, install `libfuse2` instead of `libfuse2t64`:

```bash
sudo apt update
sudo apt install libegl1 libfuse2 libasound2-plugins alsa-utils
```

The AppImage runtime normally uses FUSE. If FUSE is unavailable, AppImage also
provides an extract-and-run fallback:

- [AppImage FUSE troubleshooting](https://docs.appimage.org/user-guide/troubleshooting/fuse.html)

## 3. Verify audio forwarding before starting Omnichord

Check that ALSA exposes the PulseAudio device:

```bash
aplay -L | grep -A1 -E '^(default|pulse)$'
speaker-test -D pulse -c 2 -t wav -l 1
```

You should hear the left and right test channels through the Windows default
audio output. If `pulse` is missing, recheck `libasound2-plugins` and confirm
that `PULSE_SERVER` is set.

AMY opens ALSA's default device. If `pulse` works but `default` does not route
to it, create `~/.asoundrc` with this content:

```text
pcm.!default {
    type pulse
}

ctl.!default {
    type pulse
}
```

Then confirm the default route:

```bash
speaker-test -D default -c 2 -t wav -l 1
```

## 4. Download and verify the AppImage

Download the latest `Linux-x86_64.AppImage` and matching `.sha256` file from
the [LB Omnichord Releases page](https://github.com/linuxificator/LB_Omnichord/releases).

Copy both files into the WSL Linux filesystem, for example
`~/apps/lb-omnichord`. Do not run the first test from `/mnt/c`; Linux filesystem
permissions and AppImage/FUSE behavior are more predictable under your WSL
home directory.

Use the exact downloaded filename below:

```bash
mkdir -p ~/apps/lb-omnichord
cd ~/apps/lb-omnichord
omni_appimage='LB_Omnichord.RYYYYMMDDHHMMSS.Linux-x86_64.AppImage'
sha256sum --check "${omni_appimage}.sha256"
chmod +x "$omni_appimage"
```

The checksum must report `OK` before continuing.

## 5. Run the packaged self-test

First verify the bundled Python, Qt, AMY and application assets without opening
the full interface:

```bash
./"$omni_appimage" --package-self-test
```

Expected output includes:

```text
LB Omnichord AppImage self-test passed
```

If AppImage reports a FUSE error, use its official fallback:

```bash
./"$omni_appimage" --appimage-extract-and-run --package-self-test
```

Record which launch method worked.

## 6. Start LB Omnichord and test the UI/audio path

Start windowed and keep a log:

```bash
./"$omni_appimage" --windowed 2>&1 | tee lb-omnichord-wsl.log
```

For the FUSE fallback:

```bash
./"$omni_appimage" --appimage-extract-and-run --windowed \
  2>&1 | tee lb-omnichord-wsl.log
```

Please check all of the following:

1. The Qt window opens and fits on the Windows desktop.
2. Mouse/touch interaction works on sliders, buttons and the strum surface.
3. Select a chord and play the strum surface; audio is heard on both channels.
4. Start a rhythm and verify drums, bass and chord accompaniment.
5. Switch between OMNI and MIDI without stopping active sound.
6. Preview several MIDI instruments from the MIDI screen.
7. Listen for drop-outs, crackling, distortion or unusually high latency.
8. Close the window and confirm that both the frontend and AMY service stop.

Please report subjective latency too. WSLg adds an audio-redirection layer, so
its latency is not assumed to match native Linux or the ESP32-P4 hardware.

## 7. Optional: test a physical USB MIDI controller

The frontend currently reads ALSA raw-MIDI devices matching
`/dev/snd/midiC*D*`. USB devices are not attached to WSL automatically.
Microsoft documents the `usbipd-win` route here:

- [Connect USB devices to WSL](https://learn.microsoft.com/windows/wsl/connect-usb)

Install `usbipd-win` on Windows, then use an Administrator PowerShell terminal
to share the MIDI controller:

```powershell
winget install --interactive --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
```

From a normal PowerShell terminal, attach it to WSL:

```powershell
usbipd attach --wsl --busid <BUSID>
```

Inside Ubuntu:

```bash
sudo apt install usbutils
lsusb
amidi -l
```

Restart LB Omnichord after attaching the device. Verify note input, pitch if
available, and MIDI CC learn on both screens. While attached to WSL, the USB
device is not available to native Windows applications. If `lsusb` sees the
device but `amidi -l` shows no raw-MIDI port, report that exact result.

## 8. Send feedback

[Open a new LB Omnichord GitHub issue](https://github.com/linuxificator/LB_Omnichord/issues/new)
with a title such as:

```text
WSL AppImage test: working / partial / not working - Windows version
```

Success reports are just as useful as failures. Please include this template:

```text
Release tag and exact AppImage filename:
Windows version/build:
CPU architecture:
WSL version (`wsl --version`):
Distribution (`cat /etc/os-release`):
Kernel (`uname -a`):
GPU and Windows graphics-driver version:
Direct FUSE launch or extract-and-run:
Package self-test result:
Qt window result:
Audio preflight result:
Omnichord audio result and subjective latency:
Rhythm result:
MIDI controller/model and usbipd result (if tested):
Anything that failed or required extra configuration:
```

Attach `lb-omnichord-wsl.log` and screenshots when useful. Review logs first and
remove usernames, private paths or other personal information before posting.
