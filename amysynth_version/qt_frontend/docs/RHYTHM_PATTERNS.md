# Drum patterns and fills

This document is the implementation contract for LB Omnichord's five-level
drum patterns and five selectable fills per rhythm. AMY supplies only generic
two-level sequencer primitives. Instrument roles, fill order, continuation
policy, kit selection and the user controls are LB Omnichord behavior.

## Catalogue and storage

The timing catalogue contains 54 rhythms, five complete activity levels per
rhythm and five fills per rhythm: 270 unique fills in the current data set.
Activity levels are complete alternatives, not cumulative deltas. Timing is
stored at 96 PPQ and every shipped event is exactly representable at AMY's
48-PPQ sequencer resolution.

At process startup the frontend validates the complete timing, continuation
and selected-kit mapping, then authors every fill into AMY exactly once. Fill
indexes 1..1000 map to stored pattern IDs 0..999. IDs 1000 and above are
reserved for the small set of currently active base-role loops. The integration
profile therefore configures 1024 stored patterns, 64 events per pattern and
32 active or pending instances. The shipped 270-fill library, and a future
library of more than 700 fills, fit without creating hundreds of active
players. Only the current base roles and the few one-shots that are actually
sounding consume instance slots.

These enlarged limits are wrapper configuration on the LB release branch for
Python/local Unix, Windows, Android/Oboe and ESP32-P4. AMY's portable upstream
defaults remain deliberately smaller.

## Base rhythm

Each logical percussion role in the selected activity level is authored as a
separate AMY `LOOP` pattern and receives a stable instance tag. Splitting the
roles is what makes per-fill suppression generic: AMY does not know that a tag
means kick, hi-hat or another musical role.

A live activity or rhythm change atomically commits replacement definitions
and starts them on the next whole-bar boundary. It never stops `zY`, resets the
timebase or reauthors the fill library. Roles absent from the selected complete
activity level are stopped at that boundary and remain silent.

## Fill selection and scheduling

The upper percussion row selects one of five exclusive activity levels. The
lower `F1`..`F5` row is independent and multi-select:

- no selected F button means no fills;
- the first enabled fill starts a new deterministic cycle;
- enabling another fill puts it first in the next schedule;
- disabling a fill removes future launches but never truncates a one-shot
  which is already playing;
- selected fills subsequently rotate in order, including each fill's allowed
  start-beat alternatives.

Fill density is stored as bars between launches and has the exact choices
`/32`, `/16`, `/8`, `/6`, `/4`, `/3`, `/2`, `/1`. The frontend expands the
selected fills and their allowed starts into the smallest finite supercycle.
It installs that schedule with AMY root `zQA` events, relative to the next
whole-bar boundary. AMY owns the musical clock; there is no host timer and no
continuous stream of fill data.

Every fill is a `ONE_SHOT`. Its data-set duration covers whole beats, including
the silent lead-in or tail needed by a syncopated musical phrase. Suppression
therefore begins at the chosen whole-beat launch and lasts for the complete
stored duration.

## Continuation policy

The data file `drum_fill_continuation_roles.json` is an LB Omnichord whitelist.
When a fill is preloaded, LB adds a generic `zQM<instance-tag>,<duration>` event
for every base role that is not on that fill's continuation list. AMY mutes
only future onsets for that tagged loop; already-ringing audio is not cut off,
the loop phase keeps advancing, and it resumes on the first tick after the
fill. A whitelisted role which is absent from the current activity level is a
no-op and is never introduced by the fill.

This is the intentional ownership boundary:

- AMY implements stored one-shot/loop patterns, quantized trigger/stop,
  root scheduling and tag-targeted finite onset muting;
- LB Omnichord decides which drum role owns each tag and which roles continue
  for each fill.

No bus-mixer extension is used or required.

## Drum-kit mapping

Timing and sound choice are separate assets. `drums.kit` in
`config/amy_config.json` selects one of:

- `tiny` (default): AMY's tiny PCM bank;
- `gamma9001`: AMY compiled with the Gamma9001 bank;
- `general_midi`: AMY's engine-side patch-258 drum-note map.

`general_midi` describes familiar drum-note assignments, but remains AMY audio:
the frontend does not open a MIDI output or bypass the wire protocol. Changing
the kit requires restarting the AMY service/frontend so the stored library is
rebuilt consistently. The tests prove that all three mappings resolve every
role without changing any timing.

The published packages intentionally use the compact `tiny` bank. Local use of
`gamma9001`, and complete coverage of `general_midi` patch 258, require the
default Gamma-enabled CPython AMY build from the pinned release commit. Build
that variant without setting `AMY_PCM_BANK`; `prepare_local_amy.sh` deliberately
sets `AMY_PCM_BANK=tiny` because it prepares the release-compatible default.
The repeatable native audio checks are:

```sh
python tests/drum_kit_audio_smoke.py tiny
python tests/drum_kit_audio_smoke.py gamma9001
python tests/drum_kit_audio_smoke.py general_midi
```

Run each command with an AMY extension built for the selected bank. The checks
render every distinct realization used by the catalogue and reject silence;
they cover 13 tiny, 62 Gamma9001 and 24 General-MIDI realizations.

## Transport boundary

Explicit Start is a clean run boundary. It sends
`S(RESET_TIMEBASE|RESET_SEQUENCER)`; stored definitions survive, while frozen
instances and old root triggers are removed. Reset is applied by AMY at an
audio-block boundary, so the host waits across several blocks before creating
new instances. It then installs the current base loops immediately at tick
zero, plus the fill schedule, bass and chords, and sends `zY1` last. The
already-selected percussion level therefore sounds without a button reselection
or a silent first bar.

Live edits send neither reset nor a stop/start pulse. Stop sends `zY0` and
explicitly releases rhythm-owned voices because future scheduled note-offs no
longer fire while the sequencer is paused.

## Assets and regression gates

Runtime assets live below `music/drums/`; the files below
`design/rhythm_rework/new_patterns/` remain their design source. Every desktop
packager copies the full `music` tree, Android stages it recursively, and the
package self-test explicitly requires the drum timing, continuation and tiny
mapping files.

Unit tests validate every catalogue entry, all kit mappings, exact complete
activity-level selection, all 270 preloaded definitions, the 64-event limit,
continuation mutes, fill-order supercycles and the 1024/64/32 integration
profile. Serial and native suites additionally exercise the real wire path
against the exact AMY release pinned in both workflows. The native cold-start
gate renders real audio and requires the visible default level to become
non-silent within one second.
