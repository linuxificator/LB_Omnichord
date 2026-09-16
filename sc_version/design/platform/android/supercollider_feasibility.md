# Headless SuperCollider on Android: feasibility audit

Status: researched; implementation deliberately stopped
Branch: `research/supercollider-android`
Date: 2026-09-16
Scope: ordinary LB Omnichord APK, not a separate Termux installation

## Decision

Do not add Android to the SuperCollider edition yet. The existing typed OSC
boundary is suitable once an engine exists, but SuperCollider 3.14.1 has no
maintained Android audio backend and no ordinary-APK runtime. Producing a
working package would require substantially more than a native compile or a
thin launcher. That crosses the task's explicit stop condition: stop when
SuperCollider itself needs extensive changes.

The desktop frontend and protocol should remain unchanged. A future Android
project can reuse them after a separately tested engine runtime exists.

## What was verified locally

- Android Studio 2026.1.4.7 is installed as the classic Snap.
- `ANDROID_HOME=/home/jeroen/Android/Sdk` is exported by `.bashrc`.
- `adb` 37.0.1 and the Android emulator are installed.
- `/dev/kvm` is accessible to the current user and `emulator -accel-check`
  reports usable KVM acceleration.
- SDK platform/build tools 36/37 are present.
- The current SDK installation does not yet contain command-line tools, an
  NDK, or an emulator system image. Installing those is routine, but doing so
  would not remove the engine blockers below, so no large toolchain download
  was started.

## Upstream evidence

1. SuperCollider removed its old Android `scsynth` implementation in 2020.
   The maintainers recorded that it had not worked since approximately 3.4
   and that a modern implementation would need a different audio path:
   <https://github.com/supercollider/supercollider/pull/4975>.
2. The 3.14.1 source tree offers only `jack`, `coreaudio`, `portaudio`, and
   `bela` as `AUDIOAPI` values. It contains no AAudio, Oboe, or OpenSL ES
   server backend. Its bundled PortAudio tree also contains no Android/OpenSL
   host API.
3. A recent Android success exists in Termux, but it is a different deployment
   model. The maintained Termux recipe builds `sclang` and `scsynth` against
   Termux's JACK2 package, whose server uses OpenSL ES. It applies Android
   patches to SuperCollider and explicitly disables Supernova:
   <https://github.com/termux/termux-packages/tree/master/packages/supercollider>.
   The originating SuperCollider discussion is
   <https://github.com/supercollider/supercollider/pull/6964>.
4. Termux packages are compiled for Termux's application-specific prefix and
   package identity. They cannot be copied safely into an unrelated APK. Using
   that route would mean rebuilding and packaging JACK2 plus all native
   dependencies for LB Omnichord, then supervising an additional audio daemon.
5. Android's supported native low-latency route is AAudio or its Oboe wrapper;
   Oboe selects AAudio where available and falls back to OpenSL ES:
   <https://developer.android.com/ndk/guides/audio/aaudio/aaudio> and
   <https://developer.android.com/games/sdk/oboe>.

## Why direct OSC is necessary but insufficient

The frontend already communicates with `sclang` through versioned OSC, so no
audio or musical API needs to cross JNI. That is a useful architectural
property, but OSC does not start an Android component, establish an audio
session, or provide an audio device to `scsynth`.

An ordinary APK still needs all of the following:

1. a maintained AAudio/Oboe backend inside `scsynth`, or a packaged and
   supervised JACK/OpenSL stack;
2. cross-compiled and pinned Boost, libsndfile, yaml-cpp, readline, FFT and SC
   plugin dependencies for each Android ABI;
3. a small Android lifecycle component to start, monitor, stop, and recover
   `sclang` and the server in a private process;
4. executable/native-library packaging compatible with Android's W^X rules;
   apps targeting Android 10 or newer cannot execute code copied into their
   writable home directory;
5. audio focus, route-change, suspend/resume and device-disconnect handling;
6. emulator package tests and physical-device latency/dropout tests.

A Java/Kotlin service could keep the Android lifecycle outside the portable
frontend, and direct OSC could remain the only application protocol. It would
still be a custom Android wrapper. Embedding `libscsynth` in that service would
also require a narrow native/JNI entry layer. Launching command binaries avoids
embedding but does not avoid the lifecycle wrapper or the missing audio
backend.

## Size of the required SuperCollider work

The smallest credible native route is not a local packaging adjustment:

- add and maintain an AAudio/Oboe `scsynth` driver;
- integrate that driver with SC's callback, device, sample-rate, block-size,
  recovery and realtime-thread contracts;
- make `sclang` Android-safe (the Termux recipe currently carries several
  source patches);
- decide whether Android runs `scsynth` only or also restores Supernova's
  affinity implementation;
- upstream or maintain a pinned SuperCollider fork and Android CI.

That is a dedicated engine-port project. It should start in a SuperCollider
fork with a small standalone OSC tone test, before any LB Omnichord APK work.
Only after sustained audio and lifecycle tests pass should the existing PySide
Android packaging be adapted to include it.

## Rejected shortcuts

- Do not bundle a Termux root filesystem or require the Termux app. That would
  not be the self-contained LB Omnichord APK requested here.
- Do not run JACK, `sclang`, and `scsynth` opportunistically as unsupervised
  Python child processes. Android lifecycle and execution policy make that
  fragile, and it would recreate the process-management problems already
  avoided on desktop.
- Do not put Android branching into musical or UI code. Any future solution
  belongs in a platform service/runtime adapter; the portable frontend must
  continue to speak the same typed OSC protocol.
- Do not revive the removed pre-3.4 Android backend. Upstream explicitly
  considered it obsolete rather than a viable base.

## Future proof-of-concept gate

Resume only when one of these conditions becomes true:

- upstream SuperCollider gains a maintained AAudio/Oboe Android target; or
- a separately scoped project is approved to maintain an LB SuperCollider
  fork with that backend.

The first milestone is a headless arm64 Android engine that boots from an APK,
receives OSC, renders a sustained and polyphonic test through AAudio/Oboe,
survives pause/resume and route changes, and runs for at least thirty minutes
without underruns or leaked nodes. The Qt frontend comes afterward.
