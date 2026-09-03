# GUI Design

Status: authoritative GUI structure contract
Owner: Qt/QML user interface
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-03

## Screens

The application has two main views:

- OMNI view: the Omnichord performance interface.
- MIDI view: MIDI instrument setup and preview interface.

The MIDI/OMNI switch changes only the visible UI. It must never stop, reset, or alter active music playback.

The large lower-left mode switch uses the shared rainbow button on both views.
Its MIDI/OMNI label is centered on the complete visible shape, including the
right-hand extension, and uses 55% of the button height so `OMNI` remains
inside the button at the supported layouts.

The title is centered in the horizontal space available on the OMNI screen.
The MIDI screen reuses that exact x-position and width, so changing screens
never makes the title jump. Across both screens, the pink reverb panel and
purple preset panel share one height and normal horizontal section gap. The
blue APG/LDR header panel uses that same height. The utility row is above them;
its bottom edge aligns with the APG/LDR panel and its vertical gaps match the
gaps between the other full-width sections.

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
the selected OMNI preset. APG plays chord tones; LDR plays the explicit,
music-theory-audited pitch set for that exact chord suffix, as defined in
`sound_balance.md`. The MIDI screen does not gain an APG/LDR control.

The purple preset panel is only as wide as its Store button and 18 equally
sized round preset buttons require. Its left/right inset equals the
top/bottom inset and the inter-button gap; the freed width belongs to the pink
reverb panel. Store is the same diameter as a preset button and uses a darker
purple fill. A pointer-down never changes a preset button's geometry. The
selected preset uses the normal single border at the normal width, changing
only that border color to white; it must not gain a second black ring.

The unused lower MIDI area fills from left to right with as many radio-style
MIDI CC knobs as fit at the current width. Each channel/controller pair owns
one activity identity. The knobs also provide the explicit MIDI-learn selection
and LED states defined in `midi_control.md`; an unbound knob remains display-only.
When the bar is full, eligible indicators follow genuine-change LRU replacement
and the outgoing knob flashes red twice.

The narrow unused gap between MIDI synth row 6 and the lower grey MIDI CC bar is
reserved for MIDI input tech LEDs. Each visible LED has a short label such as
`ALSA raw`, `ALSA seq` or `OSS MIDI`. Only techs relevant to the active platform
are shown. Red means unavailable to this runtime; green means available and
listened to; blinking green means recent incoming MIDI bytes on that tech.

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

The percussion, chord and bass activity groups form one top-aligned row.
Percussion activity has four equal buttons numbered 1 through 4. Chord
activity fills the complete yellow rhythm-bar height with two rows of five
buttons, using the same column width as bass activity. Its upper `1 2 3 4`
selection remains the exclusive automatic-chord onset activity; upper-right
`A` toggles arpeggio mode independently. Its lower `/1 /2 /3 /4` selection is
the exclusive arpeggio-note density and lower-right `U`/`D` toggles ascending
versus descending order independently. `U` is the idle/up state and `D` is the
selected/down state. When `A` is off, the complete lower row has no musical
effect, although it remains editable for the next arpeggio activation.

Bass activity retains the original button sizes and adds a fifth, equally
sized `R` button on the right. The wider chord and bass groups take their extra
horizontal space from the tempo slider. Chord activity has no zero button:
`CHORD ON/OFF` is the sole user-facing automatic-chord gate. While a manual
chord temporarily suppresses sequencer chords, none of the four upper
chord-activity buttons is selected; the stored level and independent
arpeggio controls remain unchanged.

With bass activity 1 through 4, the lower bass slider is labelled `bass
voicing` and keeps its `-6..6` inversion range. Selecting `R` changes that same
Qt slider to `riff selector`, with the discrete range `1..N` for the riffs
compatible with the current rhythm and chord suffix. No custom pointer or
gesture handling is introduced for either function.

The `CHORD ON/OFF` button reports its current state: `CHORD ON` means sequencer
chords are enabled and `CHORD OFF` means they are disabled. Its ON appearance
matches a selected chord-activity button; its OFF appearance matches an
unselected chord-activity button. This binary state exists independently of the
active chord and is available before a chord has been selected. Selecting,
pressing or releasing a chord must never change that state.

Each musical chord key uses one Qt `TapHandler` path for mouse, touchscreen,
stylus and other supported pointer devices. Qt owns press, release and
long-press classification and uses the platform long-press style hint; the
Omnichord backend contains no duplicate gesture timer. The handler retains the
button grab through release. Pointer-down starts and selects the chord.
Pointer-up immediately releases the directly played manual voice,
independently of rhythm timing, and the selected chord keeps its blue active
border after a quick tap.

Ordinary buttons use Qt Quick Controls button signals. Held increment/decrement
controls use `AbstractButton.autoRepeat`; sliders use `Slider.onMoved`; MIDI
manual takeover uses the first real `Slider.onMoved` value change or the first
increment/decrement step. Pressing a slider without changing its value does not
unlink it. Application code assigns the musical meaning after Qt has classified
the input and must not infer these gestures with elapsed-time or movement-count
thresholds.

Custom Qt Slider handles must expose `implicitWidth` and `implicitHeight`.
Setting only visual `width` and `height` can leave `implicitHandleWidth` at
zero, which makes the visible knob differ from Qt's actual drag handle.
While `Slider.pressed` is true, Qt owns the interactive slider value. Backend
property echoes or repeater model replacements must not force the handle back
to an older value during that press. After a real move, the native value and
its visible handle/fill remain at the accepted user value across release even
when the backend deliberately suppresses a live model refresh. A later external
backend change resumes synchronization. A press without movement and a gesture
consumed by MIDI learn synchronize immediately. This contract is identical for
mouse and touchscreen input on Linux, macOS, Windows and Android; application
code must not classify either gesture itself.

`BindableSlider.qml` is the single implementation of that native horizontal
slider interaction, visual-position mapping and semantic MIDI binding
presentation. `LabeledSlider.qml` and `ParameterSlider.qml` remain separate
domain/display wrappers and supply their own value formatting and conversion.
Both fill and handle derive from the same native `Slider.visualPosition`; the
primitive must not contain OMNI/MIDI musical policy. The two strum surfaces
share only clamped vertical pointer normalization, and utility screens share
only their passive section background.

`Main.qml` remains the top-level window/layout facade, while complete title and
strum-note-guide sections live in `OmniTitleSection.qml` and
`StrumNoteGuide.qml`. Child components emit semantic requests such as
`strumModeToggleRequested`; the root resolves global navigation/MIDI-learn
policy and calls the backend. Extracted sections do not reach through the root
to invoke unrelated backend functions.

The RST/UP/DWN block left of the first two chord rows ends at the bottom of the
second row. Its three controls are distributed evenly over that complete
height.

## UI state versus audio state

UI changes must first update application state and then generate AMY wire commands. The GUI never directly manipulates AMY internals.
