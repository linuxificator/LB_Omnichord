# LB Omnichord - Music Behaviour Specification

## Purpose

This document is a behavioural specification, not a summary. It records user-visible musical behaviour that implementations must preserve.

## Core model

The instrument is an Omnichord-style performance instrument:

- one interaction selects harmony;
- another interaction performs the strum/playing gesture;
- rhythm and accompaniment have their own state;
- the user should be able to perform continuously without unexpected retriggers.

## Architecture rule

The GUI creates musical intent and sends AMY wire commands. The GUI does not become the synthesizer.

## Chord state

Chord handling has multiple concepts that must not be mixed:

- selected chord
- chord activity level
- currently sounding accompaniment voices
- manually played/strummed notes
- rhythm-generated notes

A change in one state must not accidentally reset another state.

## Long press behaviour

A long press on a chord is a performance action, not simply repeated button activation.

Required behaviour:

- pressing and holding a chord must not repeatedly restart the complete accompaniment;
- the held chord can drive accompaniment behaviour;
- releasing the hold must restore the previous chord activity behaviour;
- rhythm that is already running must continue according to its own clock.

## Rhythm behaviour

When rhythm is running:

- rhythm timing is independent from chord selection events;
- changing chords must not restart the rhythm pattern;
- rhythm phase should remain continuous unless explicitly stopped;
- accompaniment changes must not create timing glitches.

## Debugging rule

When behaviour is wrong, inspect in this order:

1. UI event generation
2. internal state transition
3. generated AMY wire messages
4. transport
5. AMY interpretation
6. audio rendering

Do not change architecture because of a behaviour bug.

## Missing exact values

Exact widget coordinates, colors, and all timing constants are maintained in CODEX_GUI_SPECIFICATION.md after extraction from historical design discussions.
