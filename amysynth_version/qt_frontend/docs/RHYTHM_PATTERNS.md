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
indexes 1..936 map to stored pattern IDs 0..935. IDs 936..999 are reserved for
small automatic-chord one-shots and IDs 1000 and above for the currently active
base-role loops. The integration
profile therefore configures 1024 stored patterns, 64 events per pattern and
32 active or pending instances. The shipped 270-fill library, and a future
library of more than 700 fills, fit without creating hundreds of active
players. Only the current base roles and the few one-shots that are actually
sounding consume instance slots.

The chord bank holds separate `/1`, `/2`, `/3` and `/4` note-one-shot
families. Each child contains one note-on and its normal note-off; whole chords
use the same ownership model in a compact multi-note child. The complete
catalogue needs at most 58 of the 64 reserved chord patterns. An exhaustive
tick audit includes every overlapping chord child, the maximum current drum
roles and one fill, and reaches 30 of the configured 32 instances.

Stored events use AMY's `zQE<pattern>,<tick>[,<period>[,<tag>]]<event>Z`
operation. It carries the root sequencer's familiar tick/period/tag model
inside the existing `zQ` extended-control family; LB does not use or require a
separate top-level pattern-authoring command.

The inherited tag semantics make `tick=0,period=0,tag=N` a clear operation,
not a stored onset. LB therefore writes every tagged local-tick-zero event with
the pattern length as its period. It fires once in a `ONE_SHOT` and once per
cycle in a `LOOP`; tagged events at later local ticks use period zero. This
applies equally to drum hits and the `zQM` controls embedded in fills.

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

- `gamma9001` (hosted-release default): AMY compiled with the Gamma9001 bank;
- `tiny`: AMY's compact PCM bank, retained for the separate ESP32-P4 target;
- `general_midi`: AMY's engine-side patch-258 drum-note map.

`general_midi` describes familiar drum-note assignments, but remains AMY audio:
the frontend does not open a MIDI output or bypass the wire protocol. Changing
the kit requires restarting the AMY service/frontend so the stored library is
rebuilt consistently. The tests prove that all three mappings resolve every
role without changing any timing.

The hosted packages intentionally use Gamma9001. `prepare_local_amy.sh` reads
the exact bank, release branch and commit from `packaging/release_inputs.json`,
builds that source with `AMY_PCM_BANK=gamma9001`, and requires both the
registration and linked PCM-data symbols. The ESP32-P4 firmware remains Tiny
until its separate storage profile can support Gamma9001.
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

Runtime assets below `music/drums/` are the single canonical executable and
design data source. The historical design handovers remain below
`design/rhythm_rework/new_patterns/`; their machine-readable
`canonical_drum_data_manifest.json` links each discussed file to the runtime
tree and records its reviewed SHA-256. Every desktop packager copies the full
`music` tree, Android stages it recursively, and the package self-test
explicitly requires the drum timing, continuation and both supported direct
mapping files.

Loading is intentionally staged: a versioned schema first rejects structural
or version drift, the typed loader then checks each row's musical constraints,
the assembled catalogue checks references and AMY capacity, and only then are
read-only indexes published. Schemas live in `music/schema/` and ship as part
of the complete music asset tree. `music/catalogue_provenance.json` records
the schema, SHA-256, item count and known manual/generation process for every
runtime bass/drum catalogue. It also records the unresolved third-party data
licensing evidence explicitly rather than implying that a source citation is
a redistribution license.

The Gamma9001 direct-PCM map remains a reviewed Python data snapshot. Git
history and the pinned AMY source identify its origin, but no deterministic
generator was recorded; changing only its file format would therefore not
improve reproducibility. A future migration first needs a checked generator
whose output is byte-stable and compared with the complete existing mapping.

Unit tests validate every catalogue entry, all kit mappings, exact complete
activity-level selection, all 270 preloaded definitions, the 64-event limit,
continuation mutes, fill-order supercycles and the 1024/64/32 integration
profile. Serial and native suites additionally exercise the real wire path
against the exact AMY release pinned in both workflows. The native cold-start
gate renders real audio and requires the visible default level to become
non-silent within one second.
