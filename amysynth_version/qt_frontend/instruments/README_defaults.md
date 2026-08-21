# Instrument slider defaults

`synths.json` contains explicit initial values for every slider of every curated AMY instrument.

## AMY source policy

This project intentionally follows the latest AMY `main` branch for the instrument catalogue and wire semantics. During the August 21, 2026 slider/default work, the current AMY `main` was commit `b6626ec22de5f6cedbbf4c34677ad8b8b6d0149c`, version 1.2.155.

The primary source is AMY's generated built-in patch table, `shorepine/amy/src/patches.h`. AMY documents patches 0–127 as Juno patches and 128–255 as DX7 patches in its tutorial: <https://shorepine.github.io/amy/tutorial.html>. `generate_defaults.py` reads that patch table and copies values which have a direct meaning in the Omnichord controls instead of inventing replacements.

For Juno instruments this includes filter cutoff, resonance, LFO rate, pitch-LFO depth, filter-LFO depth, pulse width, PWM depth, portamento and the native amplitude-envelope values. For DX7 instruments it includes algorithm, feedback, LFO rate and pitch-LFO depth. Portamento defaults to zero unless we later expose a native value for it.

The generated JSON is checked into the repository; the Raspberry Pi application does not download anything at startup.

## Slider ranges and runtime updates

The old frontend used `-1` inside each slider range as a sentinel for "leave the factory patch value unchanged". That sentinel is no longer part of the UI because every instrument now has an explicit default. It caused several bad UI effects, most visibly on Sustain: a `-1..1` range put `0.00` in the middle of the track, and negative values were displayed without their numeric value.

The catalogue now uses physical/control minima instead: Sustain is `0.00..1.00`, envelope times and modulation depths start at zero, filter cutoff starts at 20 Hz, Juno resonance at 0.51, pulse width at 0.05, and DX7 algorithm at 1. Legacy negative values are still accepted while reading old preset JSON and mean "unspecified/use the current instrument default"; they are never presented as slider positions.

A slider edit also no longer blindly retransmits every other parameter. The frontend may send a complete logical parameter snapshot, but `AmySerialClient` diffs it against the previous snapshot and generates AMY wire commands only for controls that actually changed. This is particularly important for patches such as Juno A73 Repeater: changing Sustain updates only the amplitude breakpoint (`A` field) and does not resend filter cutoff/resonance (`F`/`R`). On an instrument change the old parameter snapshot is cleared, the new factory patch is loaded, and then the complete saved/default state for the newly selected instrument is applied.

## Envelope policy

The AMY Juno envelope is normally retained. A few deliberate corrections are applied because the Omnichord retriggers notes digitally and an effectively instantaneous VCA attack can produce an objectionable click:

- **Harpsichord 1 / 2:** 20 ms attack. The decay/sustain/release remain derived from the AMY patch, preserving the plucked character while removing the hard edge heard with the prior setting.
- **Orchestral Pad:** 600 ms attack, 1800 ms decay, 0.78 sustain, 1800 ms release. Pads/ensemble strings need a rounded onset and release rather than a percussive gate.
- **Synth Pad:** at least 350 ms attack, 0.70 sustain and 1200 ms release.
- **Organs:** at least 10 ms attack as a de-click ramp; sustain/release remain otherwise patch-derived.

The DX7's six operators already contain their own native envelopes. The four Omnichord ADSR controls are an *additional global ALGO-output envelope*, so there is no one-to-one native value to copy. Conservative profiles are therefore assigned by musical family (brass, strings, piano/e-piano, bass, vibes, mallets, organ, pipes/winds, guitar, chimes and atmospheric sounds). The native operator envelopes still do most of the shaping.

The envelope choices follow conventional ADSR synthesis practice. Sound On Sound's synthesis references describe plucked acoustic sounds as having an immediate bright transient followed by decay, while sustained bowed/blown sounds build and hold differently; its ADSR reference defines attack/decay/sustain/release in the conventional way. Very short digital attacks can also produce audible clicks. References:

- <https://www.soundonsound.com/techniques/synth-school-part-2>
- <https://www.soundonsound.com/glossary/adsr-attack-decay-sustain-release>
- <https://www.soundonsound.com/techniques/synthesizing-brass-instruments>

## Regenerating

Download the current AMY `main` patch table and regenerate the checked-in catalogue:

```bash
curl -L https://raw.githubusercontent.com/shorepine/amy/main/src/patches.h -o /tmp/amy-patches.h
python3 instruments/generate_defaults.py /tmp/amy-patches.h instruments/synths.json
```

Review the diff before committing. Because this project follows latest AMY, direct timbre defaults may change when AMY changes its factory patches; the explicit musical corrections in `generate_defaults.py` remain stable until deliberately edited.
