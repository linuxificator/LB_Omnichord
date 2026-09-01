# T11 result: one explicit application composition root

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: application construction and dependency boundaries
Applicability: source, headless integration, AppImage, Windows, macOS and Android

## Outcome

- `code/main.py` is now the sole production composition root. It explicitly
  creates immutable frontend paths and an `ApplicationDependencies` bundle for
  config resolution, every catalogue loader, the three AMY command-client
  factories and the final QObject facade factory.
- Removed the wildcard `app_core` import and all runtime assignments to
  `app_core.load_synth_catalog`, `load_amy_config`, AMY client classes and
  `InstrumentBackend`. Explicit compatibility exports preserve the supported
  headless import surface without changing another module.
- Added shared resource and graph constructors. GUI and headless integration
  now instantiate the same resource, typed-config, selected client and backend
  graph; tests pass fake serial/socket/local factories through that same API.
- `app_core.run_application` still owns the characterized Qt renderer/QGui/QML
  startup and shutdown sequence, but it cannot choose a concrete client,
  catalogue extension or backend class. QML context names/order and smoke-test
  checkpoint names are unchanged.
- AppImage passes `APP_ROOT` to `main.main` as ordinary data. Its former five
  assignments into `app_core` asset globals are gone.
- CLI serial overrides now create a new frozen transport config, update an
  isolated compatibility view and record `$.serial.port`/`$.serial.baud` as
  runtime provenance. Invalid baud overrides fail before a transport opens.
- Synth-default fallback warning text and selection behavior are preserved
  through an injected notice callback.

## Injected contracts

Only dependencies that are really selected at startup received seams:

- immutable `FrontendPaths`;
- resolved config and resource-loader callables;
- a minimal command-client protocol (`send_message`, `close`);
- client/backend factory protocols;
- immutable loaded resources and completed graph records.

The legacy QObject facade and resource model deliberately retain broad value
types at this boundary. Inventing a complete service interface before the
musical/platform extractions would only encode the current giant facade in a
second form. T13/T15/T17 narrow collaborators as they are actually extracted.

## Compatibility proof

- Frozen QObject property/signal/slot hashes are unchanged.
- Canonical config-loader identity and five platform-profile characterization
  remain green.
- A new AST test rejects wildcard imports and assignments into `app_core`.
- Fake graph tests prove exactly one of serial/socket/local is constructed,
  the same client reaches the backend, mutual transport selection fails and
  runtime overrides are typed/provenanced.
- Resource tests prove injected paths, fallback notices and every package-smoke
  checkpoint through `startup-synths-selected`.
- AppImage entrypoint tests prove path injection without module mutation.
- Complete quality, unit, frontend, serial, preset, native-control and
  native-rhythm suites passed.

## Type-quality result

The mypy ratchet dropped from 58 to 46 legacy errors. Every error formerly
owned by `code/main.py` disappeared: four `misc`, one `no-redef` and one
`arg-type`; removing concrete client assumptions also eliminated six errors in
`app_core.py`. `application_composition.py` joins the strict-mypy new-module
set, now six modules. The lower 46-error inventory is committed as the new
ceiling.

## Findings and progressive insight

- `midi_player.MIDI_FACTORY_DIR` still derives from `app_core.INSTRUMENT_DIR`
  at import time. Packaged layout discovery makes current packages correct,
  but T14 must inject runtime paths into platform/runtime adapters and remove
  this last cross-module path dependency.
- `app_core.run_application` remains a large Qt bootstrap function. Moving it
  now would create a large mechanical diff without clarifying ownership; its
  concrete choices are already outside it, so later service/facade extraction
  can proceed incrementally.
- The integrated backend still constructs its MIDI player internally. T13 owns
  MIDI adapter/thread extraction and T17 owns eventual facade separation;
  adding a speculative all-services interface in T11 would be rework.
- Explicit `main` aliases remain only for the supported headless entrypoint.
  T12 can remove whole-dictionary config compatibility independently now that
  construction no longer depends on monkey-patched globals.

## Follow-up task effects

No new queue item is needed. T12 has a stable typed/config composition seam;
T13 can inject platform MIDI adapters; T14 must remove import-time runtime-path
derivation; T17 can shrink the QObject facade without changing entrypoints.
