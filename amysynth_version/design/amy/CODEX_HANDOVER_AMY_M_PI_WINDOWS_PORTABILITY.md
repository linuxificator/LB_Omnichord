# Codex handover: AMY `M_PI` Windows portability correction

Status: source correction committed and cross-platform validation complete
Recorded: 2026-09-05
AMY baseline: Shorepine `main` at
`0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b`

## Decision

Keep the small `M_PI` fallback in the AMY sequence branch as its own commit,
even though the defect did not originate in the reusable-sequence patch.

The sequence work is based on current Shorepine main and should remain
buildable through the repository's supported Godot Windows path. Keeping the
correction separate preserves review causality: it can be inspected or
dropped independently from every sequence change.

No Codex-specific explanation is added to the Shorepine-facing AMY tree. This
handover is the diagnostic record for the LB Omnichord side.

## Why the current source needs it

ISO C does not require `<math.h>` to expose `M_PI`. Unix toolchains commonly
provide it as an extension, but MSVC does not provide it under this build's
current preprocessor settings.

AMY commit `73b6fece5277f9e6e3ea891e1f6a91eaa17bc578` introduced a Hann-window
calculation in `src/pcm.c` which uses `M_PI`. That sampler work entered main
after the last successful upstream Windows Godot run:

- upstream Godot run `32322968524`, head `fa14fa2e`, passed Linux, macOS and
  Windows, but that head did not contain the new sampler commit;
- current-main run `33349266667`, head `0fb0a00b`, passed Linux and macOS but
  failed Windows while compiling `src/pcm.c` because `M_PI` was undeclared;
- the sequence branch fails at the same source line, after its own
  `src/sequencer.c` has compiled.

This explains why older releases built successfully: their tested source did
not yet contain this use of `M_PI`. The failure is reproducible on current
upstream main and is therefore not a sequence regression.

## Correction

Immediately after the AMY includes in `src/pcm.c`:

```c
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
```

The guard leaves toolchains which already define `M_PI` unchanged. MSVC gets
the conventional double-precision constant, which the existing expression
explicitly casts to `float`. This avoids a Windows-specific compiler define,
does not add runtime initialization, and does not change the render path.

Defining `_USE_MATH_DEFINES` would couple common AMY source to MSVC include
ordering. Computing pi through a trigonometric call would add unnecessary
runtime work. An AMY-owned named constant could also work, but would be a
larger edit for this single existing use.

## Validation contract

The following must be true before merging into `rework/sequencer`:

1. Windows Godot debug builds beyond the former `M_PI` failure.
2. Windows Godot release also builds and uploads its artifact.
3. Linux and macOS Godot debug and release builds pass from the same sequence
   source before the guarded fallback is introduced; on those platforms the
   guard makes the source semantically unchanged.
4. Native C, Python, generated C/JavaScript/Godot API, audio-regression,
   AddressSanitizer, LeakSanitizer and ThreadSanitizer sequence validation
   remains green.

All four conditions passed. Temporary fork run `33952528751` built Linux and
macOS Godot debug and release from the sequence source. Its Windows job
reproduced the upstream `M_PI` failure. Temporary Windows-only run
`33954151514`, with the guarded fallback and otherwise the same AMY source,
then built Windows debug and release and uploaded the artifact successfully.
The portable source correction is AMY commit
`397488b3` (`Define M_PI portably for MSVC`).

The temporary GitHub workflow edits used to expose pull-request builds and to
isolate Windows validation are test fixtures. Only the guarded source fallback
belongs in the AMY merge.
