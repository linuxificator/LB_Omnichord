# LB Omnichord GUI Specification

## Purpose
This document is the GUI authority for Codex. It describes the intended user experience and the boundary between UI and synthesis. Missing information must be resolved from confirmed project history; Codex must not invent a new UI design.

## Architecture boundary

The Qt frontend is a user interface and controller only.

Responsibilities:
- display the instrument;
- process mouse and touch input;
- maintain UI state;
- create AMY wire protocol commands.

Non-responsibilities:
- running AMY internally;
- importing the AMY Python library as a shortcut;
- replacing the AMY service architecture.

## Interaction model

The design is based on the Omnichord concept:

- one area selects chords;
- another area provides continuous strumming interaction;
- rhythm and instrument controls are available without breaking the playing flow.

## Confirmed controls

The UI contains or is intended to contain:

- chord buttons/selection area;
- strum interaction surface;
- rhythm/drum controls;
- instrument and patch selection;
- tuning related controls where implemented.

## Input requirements

Both are required:

- touch input for the final instrument;
- mouse input for development and desktop testing.

A touch problem must not be diagnosed as an AMY problem without checking the UI event path.

Debug order:

1. input event received;
2. UI state changed;
3. AMY wire command generated;
4. socket/serial transport;
5. AMY parsing;
6. audio output.

## Visual rules

Confirmed:

- Preserve existing design language and assets.
- The tuba watermark/background is a deliberate design element in the AMY Qt version history.
- Technical names must not leak into the user interface. For example, do not display PATCH suffixes merely because AMY internally uses patches.

## Historical implementation notes

Known UI issues and lessons:

- Strum failure was investigated by adding command logging instead of changing the synth architecture.
- Chord command generation worked while strum input did not, proving that UI event paths must be debugged separately.

## Details still requiring extraction from historical conversations

The full export still needs to populate:

- exact color palette;
- exact dimensions;
- widget locations;
- font choices;
- screenshots as visual references;
- animations;
- final chord layout;
- final rhythm UI behavior;
- final patch browser behavior.

Until these are confirmed, Codex must preserve existing implementation and avoid redesign.
