# LB Omnichord - Codex Uncertainties

This file contains information that must not be guessed by automated agents.

## Resolved

### AMY integration

Status: resolved.

Use AMY as an independent component controlled through AMY wire protocol.

Do not replace with embedded Python AMY usage.

### Sonic Pi

Status: resolved.

The Sonic Pi version is historical. Active development uses AMY.

## Needs verification

### Exact current Qt directory structure

The repository is still being reorganized. Before moving files, inspect the current tree and update references carefully.

### Android/Godot source location

The Android/Godot proof of concept is an architectural reference. If code is present, compare against it before changing transport architecture.

### MIDI finalization / ESP32-P4 multibus

Status: unresolved.

The previous branch name feature/midi-finalization-esp32p4-multibus no longer exists. Do not assume unfinished design choices from that branch.

### Hardware choices that were explored but not final

- two-board P4 designs;
- parallel buses;
- command queueing;
- alternative UART signaling.

Only implement these when confirmed by current design documents.

## Rule for Codex

When a conflict exists:

1. Do not choose the newer-looking idea automatically.
2. Do not redesign architecture.
3. Record the conflict.
4. Ask for confirmation when required.
