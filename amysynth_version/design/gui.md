# GUI Design

## Screens

The application has two main views:

- OMNI view: the Omnichord performance interface.
- MIDI view: MIDI instrument setup and preview interface.

The MIDI/OMNI switch changes only the visible UI. It must never stop, reset, or alter active music playback.

The large lower-left mode switch uses the shared rainbow button on both views.
Its MIDI/OMNI label is centered on the complete visible shape, including the
right-hand extension, and uses 55% of the button height so `OMNI` remains
inside the button at the supported layouts.

## Common controls

The following remain available in both screens:

- Panic button: stops active notes.
- Fullscreen toggle.
- Tuning controls.
- A brown master-volume tap slider for that screen's complete audio section.
- Mode switch.

The master slider sits between tuning and `PNC!`. `PNC!` and `FSC`/`ESC` are
shifted right so the fullscreen button's right edge aligns with the right edge
of the pink reverb panel. The slider's center is a mute switch: unmuted shows a
white `MUT` panel with black text; muted shows a black `UMT` panel with white
text. OMNI and MIDI master volume and mute state are independent.

## MIDI view

The MIDI view contains:

- M1-M18 MIDI presets.
- Six instrument rows.
- MIDI channel selectors.
- Instrument selection.
- Instrument parameters.
- Volume controls.
- MIDI preview strum.
- Independent MIDI reverb controls for level, liveness, damping and drum send.
- Independent MIDI master volume and mute.

No watermark is shown on the MIDI screen.

The OMNI strum header has an APG/LDR switch owned by the backend and stored in
the selected OMNI preset. APG plays chord tones; LDR plays
the chord-family ladder defined in `sound_balance.md`.

The unused lower MIDI area fills from left to right with as many radio-style
MIDI CC knobs as fit at the current width. Each channel/controller pair owns
one activity identity. The knobs also provide the explicit MIDI-learn selection
and LED states defined in `midi_control.md`; an unbound knob remains display-only.
When the bar is full, eligible indicators follow genuine-change LRU replacement
and the outgoing knob flashes red twice.

On the OMNI screen, MIDI learn is shown by a blinking red LED inside the large
`MIDI` mode button, immediately to the right of its label. It is absent rather
than grey when learn is inactive. The green binding-location LED remains on
the left side of the same button. Details are defined in `midi_control.md`.

While MIDI owns rhythm tempo, both rhythm UP/DWN buttons are disabled and grey.
While MIDI owns the effective tuning reference, both tuning UP/DWN buttons on
each affected screen are disabled and grey; coupled tuning applies this lock to
both screens when either reference is bound.

If a preset moves one channel/controller binding from one numeric target to
another, both affected handles show the two-second handoff defined in
`midi_control.md`: outgoing flashes red and incoming flashes blue, then outgoing
returns to its normal free color and incoming becomes steady green.

The rhythm start symbol uses the same geometrically centered Canvas triangle as
the bass start symbol. It must not use a font glyph whose visual side bearings
make it appear off-center. Both transport canvases repaint when their backend
running state changes.

The percussion, chord and bass activity groups form one top-aligned row. Each
group has the same width and four equal buttons numbered 1 through 4. Chord activity
has no zero button: `CHORD ON/OFF` is the sole user-facing automatic-chord gate.
While a manual chord temporarily suppresses sequencer chords, none of the four
chord-activity buttons is selected; the stored level remains unchanged.

The `CHORD ON/OFF` button uses the yellow rhythm-section palette. Its binary
state exists independently of the active chord and is available before a chord
has been selected. Selecting, pressing or releasing a chord must never change
that state.

## UI state versus audio state

UI changes must first update application state and then generate AMY wire commands. The GUI never directly manipulates AMY internals.
