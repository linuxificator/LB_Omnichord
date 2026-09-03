# Native Android package

The Android build preserves the same service/frontend boundary as every other
LB Omnichord package:

```text
PySide6 / Qt frontend process
        |
        | AF_UNIX + SOCK_SEQPACKET
        | <Android filesDir>/amy.sock
        | one ordinary AMY wire request per packet
        v
private :amy service process -> AMY C engine -> Oboe -> AAudio
```

The application embeds the `amy-service` AAR from fork release branch
`releases/amy_omnichord_R20260903T201525`, pinned to commit
`3462b266e4990ab6fa617bb8fa5c5ad8b43959d5`. Its native build generates,
links and registers Gamma9001 PCM data before AMY starts. The AAR's unexported lifecycle
provider starts AMY in a separate `:amy` process under the same package UID.
Qt discovers the application's real private files directory with
`QStandardPaths`; neither the data path nor an Android user number is
hard-coded. The Python frontend opens the socket and sends wire messages only.
It does not import or link AMY and it does not call the AAR's JNI
implementation.

This is the Android equivalent of the desktop wrappers. Linux and macOS use a
supervisor around a separate service and Unix socket; Windows uses
`QLocalSocket` plus a native named-pipe service because CPython on Windows does
not expose `AF_UNIX`. See `docs/WINDOWS_NATIVE.md` for that wrapper and named
pipe contract.

## Pinned build inputs

- Python 3.11 (the supported host version for `pyside6-android-deploy`)
- PySide6 and shiboken6 Android wheels 6.11.2 from Qt's official release site
- Android SDK 36 and NDK 27.2.12479018 (r27c)
- python-for-android commit `3762c88c56e3443efb8eba2a02a2604b680240fd`
  (Python 3.11.13, matching the official `cp311` Qt wheels)
- Cython 0.29.36, matching that python-for-android revision's tested environment
- Oboe 1.10.0
- the exact AMY fork commit recorded in `.github/workflows/desktop-release.yml`

Qt's deployment command uses Buildozer/python-for-android as host-side package
tools. Kivy is not an application dependency and is not included in the APK.
The build exposes the installed modern Android command-line tool through the
legacy SDK-manager path expected by Buildozer 1.5; it never executes an old
`tools/bin/sdkmanager` from the host image.
The generated Gradle repository explicitly includes python-for-Android's local
`libs` directory so the verified AMY AAR passed with `--add-aar` is resolvable.

`build_android.py` stages only the frontend Python modules and runtime assets,
lets Qt's supported Android deploy tool generate its recipes/JAR list, then
adds the AMY AAR and its Oboe dependency to the generated Gradle package. The
script rejects an AAR without both CI and production ABIs and rejects an APK
that lacks the AMY/Oboe libraries or the matching CPython 3.11/shiboken native
libraries. It also rejects an APK containing an in-process `c_amy` binding.

The official, SHA-256-pinned PySide6 Android wheel is a complete Qt for Python
SDK and is much larger than this application needs. After verification,
`prune_pyside_wheel.py` derives a valid wheel containing only the reviewed
Python bindings, the Basic-style QML module graph, the Android platform and
network-information plugins, required jars, and the complete recursive native
`DT_NEEDED` closure. It rewrites wheel `RECORD`, records both wheel hashes and
the retained native inventory, and never modifies the downloaded source
wheel. The final APK is audited again and the workflow retains both JSON
reports with the package. A manually dispatched release workflow performs the
same regression, x86_64 emulator and arm64 packaging gates on the selected
branch without publishing a release; this is the validation route for changes
to the package policy.

PySide6 6.11.2 internally collects detected Android modules through Python
sets, but python-for-Android writes the resulting list directly into Qt's JNI
startup array. The build therefore makes a second deploy initialization pass
with the explicit dependency order `Core`, `Gui`, `Network`, `OpenGL`, `Qml`,
`Quick`, `QuickControls2`. It then checks that same order in the
compiled APK resource table. In particular, `Quick` must load before
`QuickControls2`; otherwise the latter can pull in the former as an ordinary
native dependency before its Android JNI initialization is ready.

QtTest and QtWidgets are test dependencies only. Package acceptance drives the
final artifact from a separate process, so neither binding nor its native Qt
runtime is shipped in the product APK.

## Volume notation

LB Omnichord's UI volume values are logical amplitudes in the safe 0..1 range.
Role/row controls use AMY's per-synth `iV`, where `iV1` is full per-synth
level. Master controls deliberately send the same logical value to AMY's raw
bus `V` field, so LB's maximum is `V1`: AMY's normal 10%-of-final-mix bus gain.
AMY's raw bus field itself accepts 0..10 and applies `V * 0.1`; `V10` is unity
at the final mixer, but is not LB's UI maximum because several simultaneous
voices can then clip. Lowercase `l` is note velocity and lowercase `a` is
oscillator amplitude. Android adds no new volume syntax; it transports the
same messages as the other platforms.

## Validation and release status

On `integration/android_build`, CI runs all six existing frontend regression
suites but builds no desktop package. It builds x86_64 and arm64 Android APKs,
installs the x86_64 package into an emulator, exercises the existing packaged
QML tap/hold smoke path, checks the private socket and separate AMY service,
and compares the exact AMY render samples with the samples handed to Oboe.
The emulator performs an unmeasured warm-up for python-for-Android's first-run
asset extraction, force-stops the complete package, and only then arms AMY's
eight-second Oboe capture for the measured launch. If Qt exits during an
unrelated first-extraction startup fault, the warm-up alone is retried up to
three times; the deterministic library order prevents the former Qt Quick JNI
load race. The measured QML/audio launch remains single-shot. After the
warm-up, that window leaves enough margin for normal packaged frontend startup
variation and the complete UI-driven synth attack.
The readiness poll filters out verbose extraction traffic and retries a
transient `adb logcat` read instead of confusing a host transport reset with an
application failure; the filtered Python log must still contain no traceback.
Before the captured packaged-QML gesture, the platform-independent package
smoke selects LB's valid maximum chord and master controls (`1.0`) through the
normal backend. The notes still enter through real QML tap/hold events and the
usual LB wire translation; no raw AMY test tone is injected. The non-silence
gate requires at least -26 dBFS peak: the raw `V1` bus scaling accounts for
20 dB and the remaining 6 dB allows normal patch/phase headroom. The gate still
rejects clipping and requires every signed-16-bit AMY sample to equal the
sample handed to Oboe.

On `main`, the same Android gate joins Linux x64, Raspberry Pi aarch64, macOS
arm64 and Windows x64. Publication waits for all five platform jobs. The
GitHub-hosted build is debug-signed so it can be installed and tested without a
repository signing secret; the release notes label this arm64 APK experimental.
A stable production/update signing key must be supplied through protected
repository secrets before treating it as a store or update-channel build.

The emulator is strong evidence for packaging, process isolation, socket wire
delivery, QML input behavior and non-silent audio generation. It is not a
physical-device latency, touchscreen, speaker, lifecycle or audio-route test.
The Android application does not use PulseAudio: AMY opens Oboe, which selects
AAudio on the tested API level. The Linux-hosted emulator executable may print
a host PulseAudio (`pa`) initialization warning; the gate separately requires
the guest `AmyAndroid: Oboe output` route and validates the frames delivered
through that stream.
