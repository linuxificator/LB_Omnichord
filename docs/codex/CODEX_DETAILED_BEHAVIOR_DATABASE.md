# LB Omnichord - Detailed Behavior Database

## Purpose

This document is not a summary. It is a behavioral contract for coding agents. It records observable user-facing behavior and implementation constraints. When implementing or changing code, preserve these behaviors unless the user explicitly requests a change.

## Critical architecture boundary

The frontend is a controller, not the synthesizer.

Allowed:

```
UI -> generate musical intent -> AMY wire messages -> AMY process -> audio
```

Forbidden:

```
UI -> import amy library -> render audio
```

A local bug must be debugged at the failing boundary, not fixed by collapsing components together.

---

# Musical interaction model

The instrument is based on the Omnichord idea:

- one hand selects chords;
- the other hand plays a strum surface;
- accompaniment can continue independently;
- rhythm is a persistent musical process, not a collection of retriggered sounds.

The user experience is more important than internal implementation details.

---

# Chord behaviour

## Chord selection

A chord selection changes the active harmonic context.

The chord selector is not simply a button that plays a sample. It changes the state used by accompaniment, strumming and bass/rhythm generation.

## Long press behaviour

Long press handling is intentional and must not be simplified to repeated button presses.

Required behaviour:

- A held chord can control the accompaniment state.
- Existing accompaniment continues according to the selected activity level.
- Releasing a chord must restore the previous logical state instead of leaving the system in an unintended retrigger state.

Do not implement long press as an uncontrolled stream of note-on events.

---

# Chord activity level

Chord activity is a separate concept from chord selection.

A chord can be active while the amount of accompaniment generated changes.

Important rules:

- Do not reset activity state unnecessarily when changing chords.
- A running accompaniment/rhythm should keep its timing.
- New chord information should be applied musically at the correct boundary.

---

# Rhythm behaviour

Rhythm is a running process.

Required behaviour:

- Starting rhythm creates a continuous timing source.
- Changing chords while rhythm runs must not restart the rhythm from zero.
- Rhythm timing remains stable while harmonic information changes.
- A chord change is not a reason to recreate the complete rhythm engine.

This distinction was important because earlier implementations incorrectly coupled chord changes and rhythm scheduling.

---

# Strum behaviour

The strum surface is an instrument control surface, not a decorative UI element.

Required debugging order:

1. Verify touch/mouse event reaches the widget.
2. Verify gesture conversion creates the intended musical event.
3. Verify AMY wire command generation.
4. Verify transport.
5. Verify AMY playback.

Do not replace AMY or redesign the architecture when the strum surface fails.

Known historical issue:

- Chords generated correct AMY commands.
- Touch and mouse worked elsewhere.
- Strum produced no sound.
- Correct next step was command logging and UI event tracing.

---

# Patch/instrument naming

Internal synth terminology must not leak into the UI.

Example of rejected behaviour:

```
Juno A82 PATCH
DX7 Bell PATCH
```

The user-facing name should describe the instrument/patch, not the implementation field.

---

# Debugging principles

Always separate:

- UI state
- generated musical commands
- transport
- AMY parsing
- synthesis
- audio output

A failure in one layer must not trigger changes in unrelated layers.

---

# Tests that must exist

## Smoke test

A basic test must prove:

- application starts;
- UI responds;
- AMY communication works;
- a patch produces audio.

## Chord test

Verify:

- chord selection changes harmony;
- holding chords behaves correctly;
- releasing chords restores correct state.

## Rhythm test

Verify:

- rhythm starts;
- rhythm continues while changing chords;
- rhythm does not restart unexpectedly.

## Strum test

Verify:

- mouse input;
- touch input;
- generated AMY commands;
- audible result.

## Regression rule

Every discovered behavioural bug becomes a regression test.

---

# Missing information policy

Where exact pixel coordinates, colors or assets are not yet extracted from the historical discussions, do not invent values. They belong in the GUI specification after extraction from the original discussions and screenshots.
