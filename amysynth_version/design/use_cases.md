# Use cases and test cases

## UC-001 Start application

Expected:
- OMNI loads
- MIDI loads
- tuning starts coupled
- only AMY wire commands are produced

## UC-002 Change OMNI tuning while coupled

Expected:
- MIDI shows same tuning
- MIDI notes use new tuning

## UC-003 Change MIDI tuning while coupled

Expected:
- OMNI shows same tuning

## UC-004 Disconnect tuning

Expected:
- OMNI and MIDI tune independently

## UC-005 MIDI note input

Input:
- MIDI note number

Expected:
- channel routing selects configured synth
- pitch is converted to fractional AMY pitch
- AMY receives wire command

## UC-006 MIDI channel change

Expected:
- only selected channel routing changes
- duplicate channels remain allowed

## UC-007 Screen switching

Expected:
- audio state is unchanged

## UC-008 MIDI preset load

Expected:
- MIDI instruments, parameters, volumes and channels restore
- OMNI presets are untouched

## UC-009 Local versus ESP32 AMY

Expected:
- identical wire command stream for identical actions
