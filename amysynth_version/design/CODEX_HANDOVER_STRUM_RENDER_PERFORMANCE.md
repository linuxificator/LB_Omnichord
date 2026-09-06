# Codex handover: portable strum visual performance

Status: shared implementation and regression contract completed; physical
120 Hz post-fix audio validation pending
Recorded: 2026-09-06
Branch: `fix/raspberrypi-appimage-runtime`

## Reported behavior

The corrected Raspberry Pi AppImage rendered completely with V3D/OpenGL, but
on a 2 GB Raspberry Pi 4 the visual contact footprint lagged while strumming
and local AMY audio could skip during UI activity. The display was running at
1920x1080 and 120 Hz. Reducing the display rate was explicitly rejected as a
product solution: 120 Hz is the required operating mode.

Physical diagnostics ruled out the earlier graphics-startup failure and
obvious system distress:

- Qt used Wayland, the threaded render loop and a Broadcom V3D OpenGL 3.1
  context;
- no software-renderer option or Pi-specific disabled acceleration was active;
- `vcgencmd get_throttled` returned `0x0`, temperature was 52.5 C and the CPU
  reached its 1.5 GHz maximum;
- 1.2 GiB memory was available and the sampled `vmstat` interval performed no
  swap input/output. The 371 MiB already resident in zram was not active memory
  pressure.

The audio service and Qt frontend remain separate processes, but both have to
meet deadlines on the same machine. Process separation prevents architecture
coupling; it does not make excessive UI work free or reserve a CPU for audio.

## Root cause in the visual implementation

The original `Migraine.qml` was visually correct but expanded one 96x96
footprint into 183 Qt Quick child items:

- 168 `Emitter` items: 56 edge locations times three RGB registrations;
- one particle system plus three image-particle renderers and a wander
  affector;
- three dynamic `Shape` paths;
- JavaScript edge geometry and trigonometry rebound whenever pointer movement
  changed `morphPhase`.

The hardware GPU composed the result, but CPU-side binding evaluation,
particle simulation and path preparation were still driven by UI movement. At
120 Hz this could consume the scheduling margin required by local audio. The
existing tests asserted input, fade, overflow beyond the pad and a non-blank
chromatic image. None constrained item count, geometry cadence or render-work
amplification, so the expensive but visually valid implementation passed.

## Portable correction

The visual remains one shared QML component on every platform. It has no Pi
conditionals and no degraded Pi appearance.

- The seven-point path construction, hollow centre, three rotating RGB
  registrations, sharp inner edge, translucent outer color and 500 ms fade are
  retained.
- Particle simulation and all 168 emitters are removed. A broad translucent
  path underneath each sharp RGB path supplies the small fuzzy edge.
- The three color shapes are rendered below one `layer.enabled` item. Once
  cached, pointer position, smoothing and fade change one texture's ordinary
  transform/opacity instead of rebuilding the effect.
- Pointer movement only accumulates travelled distance. One 34 ms timer
  advances path morphology, limiting geometry changes to less than 30 Hz even
  on a 120 Hz input/display stream. The final shape phase remains
  distance-driven rather than time-driven.

The active effect now exposes six Qt Quick child items instead of 183: three
shape items, one repeater, the cached item and Qt's layer texture source. This
is a 96.7% reduction in visual object count. A before/after offscreen capture
showed the same pointed, hollow, RGB-misaligned footprint at its normal size.

Removing the last use of `QtQuick.Particles` also removes that QML plugin from
the reviewed runtime manifest and future packages. `QtQuick.Shapes` remains a
declared shared module.

## Regression evidence

`tests/test_migraine_render_budget.py` is intentionally separate from the
ordinary gesture suite. It proves:

1. an active footprint has no more than twelve Qt Quick children, exactly
   three shapes and no particle/emitter objects;
2. a synchronous burst of 120 movement updates causes no synchronous geometry
   rebuild, and only one or two morphology updates occur in the next 80 ms;
3. the rendered centre remains transparent while the edge contains substantial
   chromatic output.

The existing real-QML mouse tests still prove start/move/end delivery, fade and
rendering beyond the strum boundary. The new cost test is automatically part of
the unit suite and is also run explicitly by the Linux x86_64, Raspberry Pi
aarch64, macOS arm64, Windows x86_64 and Android host package jobs. That guards
one implementation and one budget instead of creating platform forks.

The three render-budget tests also passed with the Pi's own Python 3.13 and
PySide6 6.7 runtime. A source launch of the corrected component reached the
physical 1920x1080/120 Hz Wayland session with V3D acceleration. This proves
the shared component loads and satisfies the structural/cadence contract on
the target; it does not replace the audible live-strumming check below.

## Evidence boundary and next physical check

Hosted tests can deterministically prevent the exact object/cadence regression
and catch Qt-version rendering failures. A cloud arm64 runner is not a Pi 4
V3D system, software/offscreen rendering is not the physical compositor, and a
CI audio file does not prove that a live callback never missed a deadline.

Before merging to `main`, run the corrected source or AppImage on the physical
Pi 4 at 1920x1080/120 Hz while repeatedly strumming with rhythms, fills and
arpeggios active. Confirm both visual tracking and absence of audible skips.
Record that exact commit/artifact as physical evidence; do not generalize an
older package result to the corrected code.

## Relationship to the Raspberry Pi runtime repair

The earlier Pi work has two scopes:

- removing bundled `libstdc++.so.6` is strictly a Raspberry Pi AppImage
  packaging/runtime choice needed to match the host Mesa/V3D stack;
- publishing `midiBackend` and `PerformanceQmlAdapter` directly corrected a
  PySide6 6.7 inherited-meta-object limitation in shared application/QML code.

The latter touched portable Omnichord files, but it introduced no Pi branch and
duplicated no musical state. The same stable QML/backend surface now runs on
every platform. The strum optimization follows that same rule.
