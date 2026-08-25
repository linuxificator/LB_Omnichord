# LB Omnichord - Music Behavior Specification

## Purpose

This document defines user-visible musical behavior. It is not implementation advice. Existing behavior must be preserved.

## Architecture boundary

The UI creates musical intent and sends AMY wire commands. The UI does not become the synthesizer.

Forbidden:
- importing AMY into the UI as a shortcut
- moving musical state into the frontend only because a bug is difficult

## Chord behaviour

The Omnichord model distinguishes between:

1. chord selection
2. chord activity level
3. rhythm activity
4. strum/manual playing

These are separate states and must not be accidentally coupled.

## Chord activity

Chord activity is a performance control, not just a visual value.

Changing chord activity changes how much automatic accompaniment is generated.

A long press on a chord is not equivalent to repeatedly pressing the chord button.

The expected behaviour is:
- select and hold the chord;
- accompaniment can temporarily change according to the active level;
- when released, the previous chord activity behaviour is restored;
- the held chord must not cause repeated retriggers.

## Rhythm behaviour

A running rhythm is a continuous musical process.

Rules:
- changing chords must not restart the rhythm clock;
- rhythm continues while chords change;
- rhythm state is independent from chord selection;
- changing patches must not accidentally reset unrelated running patterns.

## Strum behaviour

Strum is an independent user gesture.

The debugging order is:
1. verify touch/mouse event arrives;
2. verify chord/strum command generation;
3. verify AMY wire command transport;
4. verify AMY rendering.

Do not modify AMY when the failure is in UI event generation.

## Regression principle

Every discovered musical behaviour bug must become a regression test:

- reproduce the user action;
- record expected audible behaviour;
- record the failed behaviour;
- record the fix boundary.
