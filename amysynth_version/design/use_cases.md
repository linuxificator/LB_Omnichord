# Use Cases and Test Cases

## UC-001 Application startup

Given a clean start:

Expected:
- OMNI UI loads
- MIDI UI state initializes
- tuning coupling starts enabled
- generated audio actions are AMY wire commands

## UC-002 OMNI tuning change while coupled

Action:
- change tuning reference in OMNI

Expected:
- MIDI displays the same value
- MIDI note generation uses the new tuning

## UC-003 MIDI tuning change while coupled

Action:
- change tuning from MIDI screen

Expected:
- OMNI immediately reflects the same tuning

## UC-004 Independent tuning

Action:
- disable tuning link

Expected:
- OMNI and MIDI tuning values can differ

## UC-005 MIDI note routing

Input:
- MIDI note and channel

Expected:
- configured MIDI row receives the note
- pitch conversion uses active tuning
- AMY wire command is generated

## UC-006 Screen switching

Expected:
- switching OMNI/MIDI does not stop rhythm, notes or sequences

## UC-007 Local versus ESP32 AMY

Expected:
- identical musical actions create equivalent wire commands

## UC-008 Presets

Expected:
- OMNI presets and MIDI presets remain independent
