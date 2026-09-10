# Bass sequence handover

Status: authoritative implementation contract
Owner: bass sequence planning and AMY transport integration
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-10

## Required behavior

A chord change and a riff change have different musical meanings.

- A chord/root change preserves the playing riff's local phase. It changes the
  pitches of future detached bass gestures as soon as their definitions reach
  AMY. A gesture which already started completes its original note-off or
  TB-303 release/slide chain.
- An explicit riff, bass-activity or rhythm-pattern change starts the selected
  replacement phrase at its local tick zero. It does so at the earliest
  guaranteed release-safe AMY-owned boundary available without observing the
  clock, rather than waiting for the old one- or two-bar repeat boundary.
- If a chord-suffix change makes the current riff incompatible and selection
  chooses another stable riff ID, it is a riff change rather than a pitch-only
  change.

The fastest safe boundary is not necessarily instantaneous. The bass synth is
monophonic and a TB-303 gesture ends with an all-off. Starting a new attack
before an older finite gesture's delayed all-off could silence the new attack.
Preserving the complete old release therefore takes precedence over unsafe
overlap.

## AMY-owned timing

The application must never query AMY's tick, infer its current phrase
position, mirror an execution, track an active bass note, or use a host timer
for this handover.

Python performs only static compilation and publication:

1. A repeating root sequence owns the riff phase and contains only child-start
   controls.
2. Every detached note, overlapping monophonic gesture or connected TB-303
   slide chain is a finite child sequence. The child owns all attacks,
   parameter changes and its final release.
3. A chord-only update republishes child definitions behind their stable tags.
   The running root is neither stopped nor redefined. AMY's immutable snapshots
   let an already-running child finish its old definition while its next start
   observes the new harmony.
4. A phrase change publishes the new children and root, then starts a finite
   handover controller. At AMY local tick zero that controller stops future
   launches from the old root. After the conservative gesture-drain bound it
   starts the newly published root, whose local tick zero is the start of the
   selected phrase.

The drain value is authored into the finite AMY controller as ticks. Waiting
and activation happen entirely in AMY. The frontend remembers only the largest
static gesture duration it has published since a known reset/explicit bass
clear. It does not know whether such a gesture is active or where the clock is.
This conservative bound keeps rapid consecutive user changes safe as well.

## Capacity

The bass range has 56 tags:

- tag 56: repeating phase-owning root;
- tags 57 through 110: up to 54 finite gesture definitions;
- tag 111: finite handover controller.

The current 1,664-riff catalogue needs at most 20 gesture definitions. A
steady bass adds one root and at most one child execution. A live phrase
replacement adds one transient handover execution, keeping the known global
worst case below the configured 40-execution limit.

Every active phrase must contain at least one real silent boundary somewhere
in its cycle. When a final note's release crosses the nominal phrase wrap, the
compiler rotates the finite-gesture partition at another silent boundary. The
crossing note and the first attack of the next cycle then remain in one child,
with deterministic attack/release ordering. A fully circular phrase with no
silent handover anywhere is normally rejected because splitting it would make
release ordering dependent on execution-slot order. A dense series of two or
more distinct, non-slide monophonic attacks is the deliberate exception: every
new attack already supersedes the previous note, so the compiler makes that
implicit boundary explicit by releasing one AMY tick before the next attack.
It does not apply this shortening to one sustained note or to a slide chain.

## Regression evidence

Tests prove that:

- transposing one stable riff changes only finite child payloads;
- chord/root input emits no root reset, root stop/start or handover definition;
- explicit riff selection emits a finite AMY stop/drain/start controller;
- the controller drain cannot shrink during rapid consecutive edits;
- TB-303 slide destinations, accent limitation and final all-off remain inside
  one immutable finite child;
- an ordinary activity note which crosses the nominal repeat boundary remains
  in one child with the next attack and therefore cannot release it from a
  different execution;
- a fully dense retrigger pattern receives explicit pre-attack releases, while
  sustained notes and slides are never shortened to manufacture a boundary;
- explicit bass-off cancels every possible bass child tag and sends an
  immediate synth release;
- all catalogue definitions fit tag, event, wire-frame and execution limits;
- source and native-AMY integration still produce bass audio through the same
  wire commands on every transport.
