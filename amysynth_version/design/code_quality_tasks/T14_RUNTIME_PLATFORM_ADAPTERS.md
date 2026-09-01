# T14 result: runtime paths, diagnostics and package hooks

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: application composition and platform runtime adapters
Applicability: source, AppImage, macOS, Windows and Android startup

## Outcome

- Moved asset-root and Qt private-files resolution into `runtime_paths.py`.
  Source, frozen/PyInstaller and Android flat staging retain the same lookup
  order, while `app_core.py` no longer reads `_MEIPASS` or `QStandardPaths`.
- Replaced Android mutation of the argparse namespace with a frozen
  `RuntimeOverrides` value. The Android adapter alone owns the private
  `amy.sock`, smoke enable/status filenames and marker consumption. Explicit
  socket/local-IPC choices remain authoritative.
- Added an immutable `PackageTestHooks` recorder. The portable startup uses one
  checkpoint method; environment status and Android status redirection are
  resolved outside it without changing checkpoint order or file format.
- Moved XDG, Wayland, DISPLAY and renderer diagnostic formatting to an injected
  diagnostics provider. `app_core` only prints the returned portable lines.
- Moved PyInstaller Windows `--windowed` stdout/stderr repair and fatal package
  smoke reporting to `windows_launcher.py`. `main.py` imports and invokes that
  adapter but contains neither implementation nor platform exception handling.
- Extended the explicit application dependency graph with four narrow seams:
  private-files resolver, package-runtime resolver, package-test-hook factory
  and diagnostics provider. No broad service locator was introduced.

## Compatibility and proof

- Android tests prove private socket selection, explicit transport priority,
  marker consumption/status reset, smoke activation and no changes on other
  profiles.
- Runtime tests prove deterministic diagnostics from explicit environment data,
  disabled/redirected checkpoints, environment status compatibility and fatal
  error recording for a windowed package.
- Packaging tests now locate Windows launcher behavior and frozen asset lookup
  in their named adapters rather than requiring those details in portable
  modules.
- Source guards reject `QStandardPaths`, Android marker constants and XDG/
  Wayland diagnostics in `app_core`, plus console/fatal implementation in
  `main.py`.
- Existing composition, packaging, Android runtime and refactor
  characterization tests pass. Quality passes with all five new modules under
  strict mypy.
- The complete quality, unit, frontend, serial, preset, native-control and
  native-rhythm suite passes.
- Removing the stale `QStandardPaths.HomeLocation` typing exception lowered the
  mypy ceiling from 43 to 42 errors.

## Findings and progressive insight

- Package smoke is cross-platform application acceptance, while the path that
  arms it can be platform-specific. Separating the recorder from Android marker
  resolution preserves one checkpoint contract without teaching the core why a
  smoke run was requested.
- Asset layout detection is packaging-dependent but does not need an OS branch.
  Keeping it as a small resolver avoids five platform copies and still removes
  frozen-runtime details from the core.
- Renderer environment mutation remains portable user policy (`--software`,
  `--opengl`, `--x11`, `--wayland`) and is deliberately not hidden in a native
  adapter. T14 removes derived platform diagnostics, not explicit CLI behavior.
- The historical checkpoint label `android-runtime-configured` remains because
  release scripts consume the exact package-smoke sequence. Renaming it would
  be a contract change unrelated to extraction.

## Follow-up task effects

No new task is required. T16 can inject transport diagnostics without creating
a platform service bundle. T17 and later core extractions can reuse the same
small-factory pattern; they must not expand these seams into a generic mutable
runtime dictionary.
