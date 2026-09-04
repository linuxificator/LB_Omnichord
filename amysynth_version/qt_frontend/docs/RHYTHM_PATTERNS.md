# Drum patterns and fills

This is the implementation contract for LB Omnichord's five-level drum
patterns and five selectable fills per rhythm. AMY supplies generic reusable
sequences; LB uses exactly one parent/child control level. Instrument roles, fill order,
continuation policy, kit selection and user controls are LB behavior.

## Catalogue and storage

The timing catalogue contains 54 rhythms, five complete activity levels per
rhythm and five fills per rhythm: 270 unique fills in the current data set.
Activity levels are alternatives, not cumulative deltas. Timing is stored at
96 PPQ and every shipped event is exactly representable at AMY's 48 PPQ.

At startup, LB validates timing, continuation and kit mappings, then defines
every fill in AMY once. Public AMY sequence tags are partitioned as follows:

- fill definitions: 256..1191, with the current 270 fills using 256..525;
- chord one-shots: 1192..1255;
- base percussion roles: 1256..1279;
- fill, bass and chord parent lanes: tags 0, 56 and 112 respectively.

The integration profile configures 1280 tags, 64 events per definition and 40
active or alignment-pending executions. The current 270-fill library and a
future library exceeding 700 fills fit without creating hundreds of active
players. Only loops and finite phrases that actually run consume execution
slots.

Each distinct velocity in the selected chord rhythm uses one stable child
sequence. An arpeggio child contains every note-on and matching note-off; a
block-chord child contains all note-ons and its release. `/1` through `/4`,
direction, pitch and chord changes reset and cumulatively rebuild the future
definition behind the same tag. An execution already started retains its old
copy-on-write snapshot and original releases. No rate banks, execution IDs or
host release timers are needed. The exhaustive overlap audit reaches 34 of the
configured 40 executions.

Definitions use ordinary tagged ticks commands:

```text
HR<tag>Z
H<local-tick>,<period>,<tag><event>Z
H<another-local-tick>,<period>,<same-tag><event>Z
```

Repeated tags cumulate events. `HR` explicitly resets future contents. A
period-zero-only definition is a finite one-shot; any nonzero event period
makes it repeat until stopped. `HC` starts, stops, aligns or gates a sequence.
An `H0,0,<tag>` message with a payload is a valid local tick-zero event; no
special period workaround is needed.

The enlarged limits are wrapper configuration on the LB release branch for
Python/local Unix, Windows, Android/Oboe and ESP32-P4. AMY's portable upstream
defaults remain deliberately smaller.

## Base rhythm

Each percussion role in the selected activity level is a separate repeating
AMY sequence. Splitting roles makes per-fill suppression generic: AMY does not
know whether a tag means kick, hi-hat or another musical role.

A live activity or rhythm change resets and rebuilds affected role definitions
and activates them at the next whole-bar boundary. It never stops `zY`, resets
the timebase or reauthors the fill library. Roles absent from the selected
complete level are stopped at that boundary.

## Fill selection and scheduling

The upper percussion row selects one of five exclusive activity levels. The
lower `F1`..`F5` row is independent and multi-select:

- no selected F button means no fills;
- the first enabled fill starts a new deterministic cycle;
- enabling another fill puts it first in the next schedule;
- disabling a fill removes future launches but never truncates a fill already
  running;
- selected fills rotate in order and through their allowed start beats.

Fill density has the exact choices `/32`, `/16`, `/8`, `/6`, `/4`, `/3`,
`/2`, `/1` bars. LB expands the selected fills and allowed starts into the
smallest finite supercycle and cumulates those child-start events behind root
tag 0. The root is replaced at its global alignment. There is no host timer,
AMY-clock mirror or continuous stream of fill data.

Every fill runs once. Its stored duration covers whole beats, including any
silent lead-in or tail required by the phrase. Suppression begins at the
chosen launch and lasts for that complete duration.

## Continuation policy

`drum_fill_continuation_roles.json` is an LB whitelist. When LB preloads a
fill, it adds a generic finite `sequence_control` gate for every base-role
sequence not on the continuation list. AMY suppresses event dispatch while
local phase advances. Ringing audio is not cut off, and dispatch resumes on
the unchanged phase. A whitelisted role absent from the selected activity
level remains absent.

The ownership boundary is deliberate:

- AMY implements cumulative definitions, immutable execution snapshots,
  finite/repeating lifetime, aligned control and payload-agnostic event gating;
- LB decides which musical role owns each tag and which roles continue.

No bus-mixer extension is used or required.

## Drum-kit mapping

Timing and sound choice are separate assets. `drums.kit` in
`config/amy_config.json` selects:

- `gamma9001`, the hosted-release default;
- `tiny`, retained for the separately sized ESP32-P4 target;
- `general_midi`, AMY's engine-side patch-258 drum-note map.

`general_midi` remains AMY audio: the frontend neither opens a MIDI output nor
bypasses the wire protocol. A kit change requires restarting the service and
frontend so the stored catalogue is rebuilt consistently. Tests prove all
three mappings resolve every role without changing timing.

`prepare_local_amy.sh` reads the bank, branch and immutable commit from
`packaging/release_inputs.json`, builds with `AMY_PCM_BANK=gamma9001`, and
requires both registration and linked PCM-data symbols. ESP32-P4 remains Tiny
until its storage profile supports Gamma9001.

Repeatable native audio checks are:

```sh
python tests/drum_kit_audio_smoke.py tiny
python tests/drum_kit_audio_smoke.py gamma9001
python tests/drum_kit_audio_smoke.py general_midi
```

Run each with AMY built for the selected bank. The tests render every distinct
catalogue realization and reject silence: 13 Tiny, 62 Gamma9001 and 24 General
MIDI realizations.

## Transport boundary

Explicit Start sends `RESET_TIMEBASE`. Stored definitions survive while active
executions are discarded. Because reset is applied at an audio-block boundary,
the writer waits across several blocks, installs current base roles and the
fill/bass/chord parents, then sends `zY1` last. The visible percussion level
therefore sounds without reselection or a silent first bar.

Live edits send neither a reset nor a transport stop/start pulse. Stop sends
`zY0` and explicitly releases rhythm-owned voices because future scheduled
note-offs no longer fire while transport is paused.

## Assets and regression gates

Runtime assets below `music/drums/` are the canonical executable source.
Historical design handovers remain under `design/rhythm_rework/new_patterns/`;
their manifest links discussed assets to the runtime tree. Packagers copy the
complete music tree and package tests require timing, continuation and direct
mapping files.

Loading is staged: schemas reject structural/version drift, typed loaders
check musical constraints, catalogue assembly verifies references and AMY
capacity, and only then are read-only indexes published.
`music/catalogue_provenance.json` records schema, checksum, item count and
known creation process. It records unresolved third-party licensing evidence
without implying a source citation grants redistribution rights.

The Gamma9001 direct-PCM map remains a reviewed Python data snapshot. Git
history and the pinned AMY source identify its origin, but no deterministic
generator was recorded. A future migration needs a checked byte-stable
generator before replacing it.

Unit tests validate every entry and mapping, complete activity selection, all
270 preloaded definitions, the 64-event bound, continuation gates,
fill-supercycles and the 1280/64/40 integration profile. Serial/native suites
exercise the same wire path against the exact pinned AMY release. The native
cold-start test renders real audio and requires the visible default level to
become non-silent within one second.
