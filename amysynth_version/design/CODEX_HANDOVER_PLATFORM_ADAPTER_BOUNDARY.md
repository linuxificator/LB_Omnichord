# Codex handover: platform-neutral core and platform adapter boundary

Status: clarified architectural direction; no code or behavior changed
Recorded: 2026-09-01
Branch: `rework/code_quality`
Builds on: `CODEX_HANDOVER_ARCHITECTURE_BOUNDARIES.md`

## Clarified requirement

The earlier rule “no platform-dependent code in the Omnichord itself” was too
absolute. The intended rule is:

> The Omnichord core source and behavior are identical on every platform.
> Platform-dependent implementation lives in separate adapter modules. The
> common startup/composition code imports or receives those adapters through a
> small platform-neutral contract.

Platform-specific code is therefore allowed and necessary. It must not be
spread through musical logic, application state, QML behavior or AMY command
generation. Adding a platform must primarily add or extend adapters, packaging
and their contract tests; it must not fork the Omnichord application.

This handover is an analysis/implementation constraint for future refactoring.
It does not authorize that refactoring and does not change any current product
contract.

## What “the same Omnichord code” means

The following modules and behavior must be shared byte-for-byte or from the
same source tree in all packages:

- musical domain rules, chord/tuning/rhythm/fill/bass-riff behavior;
- preset and MIDI-binding semantics;
- AMY wire-command and scheduling-plan generation;
- QObject view-model behavior and public QML contract;
- QML screens and interaction semantics;
- configuration schema and normalized application configuration;
- application use cases and error-state semantics.

Platform packages may contain different adapter modules, launchers, native
services, build scripts, manifests and signing metadata. A package may omit an
adapter it cannot use, provided the composition boundary reports that
capability consistently.

The core may import a stable platform-neutral facade such as
`platform_adapters.resolve()` or receive an `AdapterBundle` from the composition
root. It must not contain scattered `if platform == ...` branches or directly
import ALSA, CoreMIDI, WinMM, Android JNI, Windows named-pipe or packaging
implementations.

## What this rule does not mean

- It does not require the same native audio or IPC implementation everywhere.
- It does not force all platforms down to the lowest common denominator.
- It does not prohibit capability detection.
- It does not require a plugin framework or runtime discovery system.
- It does not mean every platform module implements unsupported features with
  fake success.
- It does not move platform policy into AMY core.
- It does not allow OMNI and MIDI behavior to diverge per platform.
- It does not make packaging scripts part of the portable application core.

A clear unavailable capability is better than a platform branch that pretends
to support it.

## Dependency direction

The intended dependency direction is:

```text
portable QML and QObject facade
             |
portable application and musical services
             |
small platform-neutral ports/value types
             ^
             |
platform adapter modules
             ^
             |
one composition/adapter-selection boundary
             ^
             |
platform launcher/package
```

The portable core defines what it needs. Adapters implement those needs. The
core never depends on a concrete platform adapter type.

Adapter modules may depend on portable event/value/protocol definitions.
Portable modules must not import adapter implementations. This prevents a
nominally separate module from leaving the actual dependency pointing outward
from the core.

## One selection point

Platform or capability selection must happen exactly once during startup,
before application services and background readers are constructed.

Preferred shape:

1. the identical `main`/composition root loads validated configuration;
2. it calls one imported adapter resolver, or a platform launcher supplies an
   adapter bundle;
3. the resolver inspects capabilities and the explicit test/development
   override;
4. it returns concrete implementations behind small ports;
5. the core thereafter sees capabilities and events, not the operating-system
   name.

Capability detection is preferred when an API can answer the real question.
For example, the Unix transport already attempts packet-preserving IPC and
falls back to stream framing by capability. Platform identity is acceptable
inside the resolver/adapter when the native API really is platform-defined,
such as ALSA versus CoreMIDI versus WinMM.

Do not replace scattered platform branches with scattered conditional imports.
Both have the same coupling problem.

## Small ports, not one platform god object

Avoid a large `PlatformServices` object exposing unrelated facilities. Use
small contracts aligned with separate reasons to change. Candidate ports are:

### `AmyCommandSink`

Owns command framing, priority/cancellation, connection health and close. Its
concrete implementations can use serial, Unix sockets or Qt local IPC. AMY
command generation remains portable.

### `MidiInputPort`

Reports immutable normalized note/control events, capability/status and
lifecycle. ALSA raw, ALSA sequencer, future CoreMIDI, WinMM and Android MIDI
belong in separate adapter modules. The portable MIDI player does not glob
`/dev` or load a native MIDI library.

### `RuntimePaths`

Provides already-resolved application data, user configuration, private IPC
and temporary/status locations. The core does not know that Android's Qt home
maps to an app-private files directory or that a platform launcher supplied a
pipe/socket name.

### `PackageTestHooks`

If packaged acceptance still needs runtime markers, isolate those hooks from
normal behavior and make the no-op production implementation explicit.
Android marker filenames and Windows headless-error reporting do not belong in
`app_core.py`.

### `DiagnosticsSink`

Receives portable structured diagnostics. Platform adapters may add concrete
backend/capability details without making the core read Linux display
environment variables or platform-specific device paths.

These names are illustrative. Do not create a port until an extraction has a
real second implementation or removes demonstrated coupling.

## Current code that belongs behind the boundary

The following are concrete audit findings, not an exhaustive move list:

### `code/midi_player.py`

`_LinuxRawMidiReader`, `_AlsaSequencerMidiReader` and the platform profile,
device-glob and unsupported CoreMIDI/WinMM/Android descriptions live beside the
portable MIDI performance engine and QObject backend. Extract native readers,
discovery and capability/status construction. The portable side should consume
normalized events and a list of capability/status values.

The shipped `tech_profile: linux` defect must be fixed through this boundary:
an optional explicit override is for tests/development; ordinary packages use
the adapter resolver. The common config must not encode Linux as the default
platform.

### `code/app_core.py`

`configure_android_runtime`, Android smoke marker names, Android private socket
resolution and Linux/XDG-specific diagnostic output are platform/runtime
adapter concerns. `app_core.main` should receive resolved paths, endpoint and
test hooks from composition. Musical/application startup stays unchanged.

### `code/amy_transport.py`

The shared lane/priority scheduling and AMY command plan are portable. Serial,
Unix socket and `QLocalSocket` byte-writing/resource ownership are adapters.
Prefer composition of a shared scheduler with a small byte sink over inheriting
Unix/Qt writers from a concrete serial writer.

### `code/main.py`

Windows `--windowed` console stream repair and package-smoke fatal-error file
handling are launcher/bootstrap concerns. The future portable composition root
must be explicit, but should not accumulate every platform exception.

### Existing packaging and services

`packaging/android`, `packaging/windows`, AppImage/macOS launchers,
`local_amy_service.py`, the Android AAR/Oboe service and native Windows service
are correctly platform-specific in purpose. They should remain outside the
portable core and implement/supply its endpoint contract. Separation does not
mean moving these native implementations into Python.

## QML and visible capability behavior

QML remains identical across platforms. It renders a capability/status model
provided by the backend; it must not contain `if Windows`, `if Android` or
fixed platform technology lists.

The model may legitimately differ at runtime:

- Linux can show ALSA raw, ALSA sequencer and OSS MIDI;
- other platforms can show their implemented or explicitly unavailable native
  MIDI technologies;
- connection/error details may name the concrete adapter.

The state semantics, LED colors, activity behavior, labels supplied by the
adapter contract and learn behavior remain common. Platform capability
differences are data, not different QML logic.

## Configuration rule

Configuration expresses user/product policy, not facts that the runtime can
derive more reliably from the selected adapter.

- A platform-neutral shipped config must not default to `linux`, a `/dev` path
  or a named-pipe convention.
- Platform adapter defaults stay with that adapter or its package manifest.
- An explicit profile/device override remains possible for tests, diagnostics
  and advanced users.
- The resolved typed runtime configuration records the selected adapter and
  effective values for diagnostics.
- Required common settings are validated before adapter construction;
  adapter-specific settings are validated by the selected adapter schema.

Do not solve platform separation by creating five near-identical complete
configuration files. That would move, rather than remove, drift.

## Error and lifecycle contract

Every adapter must expose the same lifecycle states and failure semantics even
when its native implementation differs:

- constructed but not started;
- starting/listening/ready as applicable;
- activity without changing musical state;
- failed with a typed, diagnostic cause;
- closing and closed;
- idempotent close;
- no callbacks after close completes.

Unsupported is a capability result, not an exception during ordinary startup.
Unexpected native failure is an observable adapter failure, not a red LED with
a silently dead worker.

The QObject thread owns view-model state. Native reader threads emit immutable
events through the one documented queued boundary. Platform extraction must
not preserve the current direct MIDI-note callback race merely in a new file.

## Testing contract

### Portable core tests

- construct the complete core with fake ports and no native platform module;
- run the same musical, preset, MIDI-binding and QML facade tests independently
  of the host operating system;
- prove identical semantic actions generate identical AMY wire sequences;
- prove unsupported/failed capability values do not change musical state.

### Adapter contract tests

Run one shared lifecycle/event/error contract against every concrete adapter
where the host permits it. Test native framing, event normalization, resource
ownership and failure reporting separately from musical behavior.

### Architecture enforcement

Use an AST/import check, not broad source-string matching, to reject in portable
core modules:

- imports of concrete platform adapter/native modules;
- `sys.platform`, `os.name`, `platform.system()` and QPA-name branching;
- hard-coded `/dev` paths, Windows pipe conventions and Android marker names;
- direct ALSA/CoreMIDI/WinMM/Android API access.

Maintain a narrow reviewed allowlist for the one resolver/bootstrap boundary.
Do not reject harmless platform-neutral Qt APIs just because Qt supports many
platforms.

### Package proof

Each of the five release package jobs must load the real shipped config and
verify:

- expected adapter/capability selection;
- no attempt to open another platform's devices;
- correct AMY endpoint and two-process boundary;
- common QML and public QObject contract;
- exact pinned AMY identity and existing native/package smoke behavior.

Optionally record hashes of portable core/QML inputs in the release manifest to
prove every platform was built from the same source. This is source-identity
evidence, not a claim that platform binaries are byte-identical.

## Incremental migration sequence

1. Inventory platform branches/imports, hard-coded paths and native resources;
   classify true platform code versus portable capability/status data.
2. Add characterization tests for current wire, QML, MIDI status and package
   behavior.
3. Define only the smallest event/value/port types needed for the first seam.
4. Extract MIDI reader/discovery adapters first, because this is current
   platform coupling and contains the demonstrated Linux-profile defect.
5. Extract runtime path/Android test-marker resolution.
6. Separate the common command scheduler from serial/Unix/QLocalSocket byte
   sinks without changing command order.
7. Move launcher/package exceptions out of the portable composition root.
8. Add AST/import enforcement after the target module set is genuinely clean.
9. Run all local suites and the full five-platform release after every merged
   behavior-bearing phase.

Do not move files and alter behavior in one unreviewable commit. First preserve
the public contract, then redirect imports, then delete the old implementation.

## Acceptance scenarios

- Adding a CoreMIDI implementation changes a macOS adapter, composition/package
  wiring and adapter/package tests; it does not modify musical services, QML or
  AMY command generation.
- Adding WinMM input follows the same common `MidiInputPort` event/lifecycle
  contract as ALSA without adding a Windows branch to `MidiPlayerBackend`.
- Moving from Unix socket to serial changes the `AmyCommandSink` instance while
  an identical user action produces the same AMY command sequence.
- Android private path or smoke-marker changes do not touch `app_core.py`.
- Importing and testing the portable core on any host does not probe `/dev`,
  load a native MIDI library or select a platform endpoint.
- Every released package reports its selected adapters, and package tests fail
  if a Linux adapter is selected on Windows, macOS or Android.

## Stop conditions

Pause and reconsider if an implementation:

- creates separate copies of core modules per platform;
- introduces platform branches in musical/UI/application modules;
- creates one large service locator or untyped platform dictionary;
- performs implicit adapter discovery after background work has started;
- lets adapter-specific dictionaries leak through the application;
- changes AMY wire output as a side effect of moving transport code;
- moves service lifecycle into the Qt application;
- replaces current native/package tests with fake-only tests;
- adds abstraction without removing a concrete platform dependency.

## Definition of done

- the portable module set has no platform/native imports or branches outside
  the single reviewed selection boundary;
- common QML, musical and AMY command sources are used by every package;
- platform code is grouped in named adapter/package modules with small typed
  contracts;
- configuration no longer fixes the ordinary runtime to Linux;
- all adapter lifecycle/events/failures meet shared contract tests;
- all current behavior and five-platform release gates pass;
- documentation states both verified native capability and remaining physical
  validation limitations per platform.
