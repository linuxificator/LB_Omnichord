# Instrument slider defaults

`synt​hs.json` contains explicit initial values for every slider of every curated AMY instrument.

## Source of the timbre controls

The primary source is AMY's generated built-in patch table, `shorepine/amy/src/patches.h`. AMY documents patches 0–127 as Juno patches and 128–255 as DX7 patches. `generate_defaults.py` reads that patch table and copies values which have a direct meaning in the Omnichord controls instead of inventing replacements.

For Juno instruments this includes filter cutoff, resonance, LFO rate, pitch-LFO depth, filter-LFO depth, pulse width, PWM depth, portamento and the native amplitude-envelope values. For DX7 instruments it includes algorithm, feedback, LFO rate and pitch-LFO depth. Portamento defaults to zero unless we later expose a native value for it.

The generated JSON is checked into the repository; the Raspberry Pi application does not download anything at startup.

## Envelope policy

The AMY Juno envelope is normally retained. A few deliberate corrections are applied because the Omnichord retriggers notes digitally and an effectively instantaneous VCA attack can produce an objectionable click:

- **Harpsichord 1 / 2:** 20 ms attack. The decay/sustain/release remain derived from the AMY patch, preserving the plucked character while removing the hard edge heard with the prior setting.
- **Orchestral Pad:** 600 ms attack, 1800 ms decay, 0.78 sustain, 1800 ms release. Pads/ensemble strings need a rounded onset and release rather than a percussive gate.
- **Synth Pad:** at least 350 ms attack, 0.70 sustain and 1200 ms release.
- **Organs:** at least 10 ms attack as a de-click ramp; sustain/release remain otherwise patch-derived.

The DX7's six operators already contain their own native envelopes. The four Omnichord ADSR controls are an *additional global ALGO-output envelope*, so there is no one-to-one native value to copy. Conservative profiles are therefore assigned by musical family (brass, strings, piano/e-piano, bass, vibes, mallets, organ, pipes/winds, guitar, chimes and atmospheric sounds). The native operator envelopes still do most of the shaping.

The envelope choices follow conventional ADSR synthesis practice: plucked/struck instruments have fast attacks and decaying envelopes; organs maintain a high sustain; blown instruments have a short but nonzero onset and short release; pads/strings have slower attacks and releases. A few milliseconds of attack also avoids the hard discontinuity/click that a zero-time digital envelope can produce.

## Regenerating

Download the AMY patch table and regenerate the checked-in catalogue:

```bash
curl -L https://raw.githubusercontent.com/shorepine/amy/main/src/patches.h -o /tmp/amy-patches.h
python3 instruments/generate_defaults.py /tmp/amy-patches.h instruments/synths.json
```

Review the diff before committing. If AMY changes its factory patches, direct timbre defaults may change as a consequence; the explicit musical corrections in `generate_defaults.py` remain stable until deliberately edited.
