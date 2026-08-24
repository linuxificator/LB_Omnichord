# Unclear items and conflicts

## AMY resource allocation

Need final verification of:
- exact oscillator allocation for MIDI voices
- final ESP32-P4 AMY configuration values
- final bus numbering

## MIDI drums

Clarify whether all MIDI drums remain inside AMY drum handling or require a dedicated mapping layer.

## Presets

Need final decision on whether tuning reference values are persistent. Coupling itself is not persistent.

## MIDI polyphony

Need final limits per MIDI channel and voice stealing behavior.

## USB MIDI

Need final Raspberry Pi MIDI device selection policy.

## Live parameter changes

Need rules for which changes affect currently playing notes and which only affect new notes.

## Migration

Need migration strategy for old presets after MIDI preset separation.
