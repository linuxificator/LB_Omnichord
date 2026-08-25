# LB Omnichord - GUI specification

## Status

This document contains verified GUI decisions. It must be extended with the complete extraction from the ChatGPT export before being considered complete.

## Current confirmed decisions

### Framework

- Qt frontend is the active implementation.
- Sonic Pi UI is historical only.
- The UI communicates with AMY; it is not the synthesizer.

### Input

Supported input:
- Touch screens.
- Mouse for desktop development/testing.

### Core interaction model

The Omnichord interaction model consists of:

- chord selection;
- strum area;
- rhythm controls;
- instrument/patch selection.

### Debugging rule

If a UI control does not work:

1. Verify the input event.
2. Verify generated AMY commands.
3. Verify transport.
4. Only then investigate AMY.

## Missing details to complete

The following must be extracted from historical chats and screenshots:

- exact colors;
- dimensions and placement;
- background assets;
- button styling;
- chord layout;
- strum visual behavior;
- rhythm UI behavior;
- patch selection behavior.

Do not invent these values.
