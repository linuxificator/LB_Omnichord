# Volume Balance and Reset Audit

Status: implemented and verified
Owner: instrument catalogue, rhythm data and preset state
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-08

## Outcome

The old global bass compensation has been removed, while all 18 curated
factory bass-slider values remain unchanged. Fill output now has measured
headroom, all application-added DX7 attack envelopes are short enough for
ordinary played notes, and every visible `RST` scope has an integration
contract.

## Bass decision

Configuration revision 9 introduced `role_levels.bass = 3.2` (+10.1 dB) to
compensate an older signal path. After AMY's shared-bus mixer corrected that
path, the same compensation made bass parts too loud. Revision 12 changes only
the exact historical `3.2` value back to the original unity behavior. A custom
user value such as `1.4` is preserved, and the factory-preset bass volumes are
unchanged.

The repeatable audit in `qt_frontend/tests/factory_role_balance.py` does not
compare arbitrary held notes. It renders the actual default bass and chord
activity events, at their real tempo and gates (`0.30` versus `0.72` beat), for
all 18 factory presets and these eight cross-style rhythms:

- pop 8-beat
- funk
- jazz swing
- waltz
- breakbeat
- drum and bass
- bossa nova
- 7/8

Each bass event contains one of C2/E2/G2; each chord event contains C4/E4/G4.
The measurement uses the production patch corrections and preset volumes. Its
ITU-R BS.1770 K-weighting already reduces the measured contribution of very
low frequencies, corresponding to the established lower sensitivity of human
hearing there. This is preferable to adding a second arbitrary “bass hearing”
multiplier after measurement. The relevant standards are
[ISO 226:2023 equal-loudness contours](https://www.iso.org/standard/83117.html)
and [ITU-R BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I/en).

The audit confirms that patch spectrum, decay and the difference between a
short bass gate and a three-note chord gate dominate the numeric result. Across
the representative rhythms, the per-preset median bass-minus-chord values span
about -26.0 to -1.1 LU. That range is evidence against another global factor:
one multiplier cannot normalize a plucked DX7 bass, a sustained Juno bass and
three very different chord voices without making some combinations worse.
The original per-preset levels plus listening tests therefore remain the
musical authority. The audit is retained to make future comparisons use the
real musical timing rather than the invalid held-note shortcut.

All bass instruments selected by the factory presets have attack values from
0 to 40 ms, so none was excluded from this pattern measurement because of a
slow attack.

Run the audit from `amysynth_version/qt_frontend` after provisioning the pinned
AMY release:

```sh
./run_local.sh
../../.venv/bin/python tests/factory_role_balance.py \
  --report /tmp/factory-role-balance.json
```

The first command provisions the checkout-local environment and exact AMY pin;
closing the application after it starts is sufficient.

## Fill decision

Every one of the 270 Gamma9001 fills was rendered against the same-duration,
phrase-ending section of percussion activity level 3 for its own rhythm and
tempo. Both K-weighted loudness and sample peak were evaluated, because a
sparse kick/snare fill and a dense cymbal/tom fill can have similar energy but
very different transient impact.

The resulting data policy is intentionally small:

- a global fill gain of `0.72` (-2.85 dB) creates headroom;
- 38 sparse per-fill multipliers correct measured within-style loudness or
  transient outliers;
- a general correction compares the total normalized hit velocity within each
  rhythm's F1--F5 family, keeps its median unchanged, raises lighter fills and
  lowers denser fills, with either adjustment capped at 3 dB;
- event velocities, timing and instrument choices remain canonical data;
- normal drum activity is unchanged.

The integration correction is necessary because average loudness over a fill
window can rate a brief F1 transient and a long F5 sequence similarly, even
though the accumulated sequence is much more prominent in musical context.
Summed hit velocity is deliberately only a bounded correction proxy: the
native render measurements and sparse exceptions continue to account for the
very different spectra and envelopes of kicks, snares, toms and cymbals.

After correction, the complete catalogue has median delta +1.131 LU, p10
-4.001 LU, p90 +3.988 LU, and no clipped samples. The extreme loudness deltas
are -7.294 and +8.064 LU and the maximum peak delta is +7.107 dB. These wider
instantaneous bounds are expected after the bounded integration correction;
clipping and correction direction are enforced independently.

The reported examples now measure as follows against their replaced segment:

| Fill | Loudness delta | Peak delta |
| --- | ---: | ---: |
| Funk F3 | -0.868 LU | -2.154 dB |
| Breakbeat F1 | +2.643 LU | +2.403 dB |
| Breakbeat F5 | -4.578 LU | -0.892 dB |
| Garage 2-step F1 | +2.440 LU | +3.233 dB |
| Garage 2-step F5 | -2.746 LU | -0.976 dB |

`tests/drum_fill_balance.py --check` enforces catalogue loudness, peak and
clipping guardrails plus Funk F3 and the correction direction for Breakbeat
and Garage 2-step. Unit tests prove the general median and +/-3 dB rules:

```sh
../../.venv/bin/python tests/drum_fill_balance.py --check \
  --report /tmp/drum-fill-balance.json
```

## Instrument attack audit

The 124-entry catalogue contains two distinct envelope cases:

- Juno attack values come from AMY's native patch and may deliberately create
  a slow pad, string swell or ensemble. Those values remain intact.
- DX7 `attack_ms` is an extra application-owned output ADSR layered on top of
  the native six-operator envelopes. A long value here masks rather than
  preserves the patch's intended attack.

The extra DX7 attack is now capped at 40 ms for every DX7 entry. This changes
six formerly slower definitions, including MIDI M12 `STRINGS 8` from 350 ms to
40 ms. The native DX7 operator envelopes still provide their original timbre
and evolution. A catalogue test enumerates every DX7 attack, so another
inaudible added envelope cannot return unnoticed.

The final native sweep rendered all 124 instruments at MIDI notes 40, 60 and
84 with a 0.5-second gate: 372 captures, no effectively silent capture and no
clipped sample. Very quiet or register-specific factory patches are reported
rather than indiscriminately amplified; their native spectrum and dynamics are
part of the instrument. Regenerate and enforce that floor with:

```sh
../../.venv/bin/python tests/instrument_balance.py --render --check \
  --gate-seconds 0.5 --plan /tmp/instrument-plan.json \
  --wav-dir /tmp/instrument-wav --report /tmp/instrument-report.json
```

## RST audit

There are four reset scopes, all now covered by integration tests:

1. OMNI bass section: stored bass instrument, volume and unbound controls.
2. OMNI strum section: stored strum instrument, volume and unbound controls.
3. OMNI chord-synth section: stored chord instrument, volume and unbound
   controls.
4. MIDI synth row: stored instrument, MIDI channel, volume and unbound
   controls.

The separate chord-row `RST` restores chord type, octave and inversion for all
four rows. In every synth scope, values currently owned by an external-control
binding remain live and are not overwritten by reset. This is the same
authority contract used by preset switching.

The concrete M12 regression now selects `STRINGS 8`, edits Attack, invokes the
real backend reset and verifies that the model and visible native QML slider
return to the catalogue default. The backend reset code did not require a
repair: the old catalogue default itself was 350 ms, which made the former
behavior look ineffective when 40 ms was the usable value.

## Verification inventory

- `tests/test_audio_metrics.py`: metric amplitude, low-frequency weighting and
  silence behavior.
- `tests/test_instrument_defaults.py`: complete DX7 added-attack bound.
- `tests/test_sound_balance_features.py`: all 124 sweep entries and exact
  preservation of the 18 original factory bass volumes.
- `tests/integration/test_presets.py`: section, chord-row and MIDI-row reset
  scopes plus external-bound authority.
- `tests/test_qml_gesture_controls.py`: visible slider follows an RST-style
  model replacement.
- `tests/test_drum_patterns.py` and `tests/test_command_plans.py`: fill-gain
  data coverage and exact propagation into AMY wire bodies.
- `tests/drum_fill_balance.py --check`: native Gamma9001 render audit of every
  fill.
