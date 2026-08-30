# Codex handover — percussion continuation during drum fills

## Scope

This handover accompanies:

`drum_fill_continuation_roles.json`

It extends the previously prepared kit-independent drum data:

- `drum_activity_timing.json`
- `drum_activity_instruments_tiny.json`
- `drum_activity_instruments_gamma9001.json`
- `drum_activity_instruments_general_midi.json`
- `drum_fills_timing.json`
- `drum_fills_instruments_tiny.json`
- `drum_fills_instruments_gamma9001.json`
- `drum_fills_instruments_general_midi.json`

This task is **information/design only**. No GitHub files were changed.

Repository context checked read-only:

- repository: `linuxificator/LB_Omnichord`
- branch: `main`
- commit: `387776cffad7394c1fcf6add1ced5d3e69a8d382`

## Requirement

A fill does not necessarily replace every currently playing percussion instrument.

Some normal accompaniment instruments should keep playing underneath it.

The implementation must be deliberately simple:

```text
for each normal drum-activity event during the active fill window:
    if event.role is in current_fill.continue_roles:
        let it play
    else:
        suppress it
```

That is the complete rule.

There is **no implicit exception**, including no hard-coded special case saying
"kick always continues".

The JSON contains an explicit whitelist for all **270** fills.

If a role is whitelisted but the current activity level has no event using that
role, nothing happens. This is normal and must not be treated as an error.

## Critical architecture rule: compare logical roles, not samples

The whitelist uses the same logical roles as `drum_activity_timing.json`.

Filtering must occur in this order:

1. obtain normal activity event;
2. compare `event.role` with the fill's `continue_roles`;
3. suppress or retain the normal event;
4. only then resolve the surviving role through the selected kit mapping:
   - tiny;
   - Gamma9001;
   - General MIDI.

Do **not** compare:

- AMY preset number;
- MIDI note;
- sample name;
- Gamma9001 patch;
- physical PCM sample.

This is particularly important for the tiny kit because several distinct logical
roles may deliberately map to the same physical PCM sample.

## Fill events are separate

`continue_roles` affects only the **normal activity groove**.

The fill's own events from `drum_fills_timing.json` always remain authoritative.

Conceptually:

```text
audible percussion during fill
    =
allowed normal activity events
    +
fill events
```

The continuation file never changes, shifts, quantizes or rewrites fill timing.

## Bass drum policy

The user's default musical expectation is that the bass drum commonly continues
while the hands play a fill.

The activity catalogue has two logical kick roles:

- `low_primary`
- `low_secondary`

They form one bass-drum family for continuation purposes.

If the fill does **not** contain `low_primary`:

```json
"continue_roles": [
  "low_primary",
  "low_secondary"
]
```

so the complete currently active normal bass-drum pattern can continue,
including normal kick pickups.

However, a number of fills are explicitly hand-foot / linear phrases and have
their own `low_primary` events.

For those fills the normal kick pattern is **not** continued. The fill owns the
coordinated foot pattern. Otherwise ordinary kick hits would be superimposed on
a deliberately composed kick/snare/tom phrase.

Therefore:

```text
fill contains low_primary
    -> suppress normal low_primary AND low_secondary
```

This is not an exception to "bass drum usually continues"; it is the musically
necessary case where the fill itself is already playing the bass drum.

## Cymbals and pedal hi-hat

Ordinary hand-played:

- closed/open hi-hat;
- ride;
- ride bell;
- crash / section accent;

are **not** allowed to continue by default.

A fill normally needs that acoustic space and the drummer's hands are occupied.

The deliberate exception is jazz:

- `jazz_swing`
- `jazz_waltz`
- `jazz_shuffle`

For those styles `timekeeper_foot` is whitelisted. A left-foot hi-hat pulse is
idiomatic independent timekeeping and may continue under hand/snare/tom fill
material.

Do not generalize this in code. The JSON is authoritative.

## Latin / Afro-Cuban timeline

In timeline-based styles a clave or bell is often an independent structural
layer rather than part of the drummer's fill gesture.

For relevant styles, `timeline_primary` is therefore allowed to continue **if
the fill itself does not use `timeline_primary`**.

If the fill itself contains `timeline_primary`, the normal timeline is
suppressed for that fill window. The fill is intentionally rephrasing or taking
ownership of that instrument; layering the normal timeline on top would create
duplicate or contradictory attacks.

So:

```text
timeline-based style AND fill does not contain timeline_primary
    -> normal timeline may continue

fill contains timeline_primary
    -> normal timeline is suppressed
```

Again: do not derive this rule at runtime. The result is already explicitly
stored per fill.

## Independent shaker / auxiliary texture

Selected Latin/Caribbean styles whitelist `texture_shaker`.

This models an ensemble situation: the shaker/continuous auxiliary percussion
can be a separate performer/layer while another player executes the fill.

The currently selected activity level may not actually contain a
`texture_shaker`; in that case the whitelist entry simply has no effect.

## Strict-whitelist semantics

This point is important for Codex:

**absence means stop/suppress.**

Do not interpret an absent role as "unspecified".

Examples:

```text
continue_roles = ["low_primary", "low_secondary"]

=> normal kick events continue
=> normal snare stops
=> normal hats stop
=> normal crash stops
=> normal tom/percussion layers stop
```

and:

```text
continue_roles = ["low_primary", "low_secondary", "timekeeper_foot"]

=> normal kick family continues
=> pedal hi-hat continues
=> hand-played cymbal/hats still stop
```

The code must not invent extra continuation based on style names, physical
instrument mappings or heuristics.

## Duplicate-hit handling

The catalogue has been constructed so the two important role-ownership cases
avoid a normal/fill collision:

- if a fill has `low_primary`, neither normal `low_primary` nor
  `low_secondary` is whitelisted;
- if a fill has `timeline_primary`, normal `timeline_primary` is not
  whitelisted.

Do not undo this by adding global "always keep kick" or "always keep clave"
logic.

Other roles are intentionally not continued where the fill commonly uses the
same hands/instruments.

## Relationship to activity level

The whitelist is independent of activity level 1..5.

Example:

```text
fill whitelist:
    low_primary
    low_secondary
    texture_shaker
```

At activity 1, perhaps only `low_primary` exists.

At activity 5, all three may exist.

The same fill data works correctly in both cases because only currently
scheduled normal events are candidates.

Do not create separate continuation tables per activity level.

## Kit independence

The same continuation file is used for all three percussion realizations:

- AMY tiny;
- AMY Gamma9001;
- General MIDI drum kit.

There must **not** be:

- `drum_fill_continuation_tiny.json`
- `drum_fill_continuation_gamma9001.json`
- `drum_fill_continuation_gm.json`

Continuation is a musical/timing-role decision, not a sample-library decision.

A tiny-kit surrogate does not change whether a logical role should continue.

## Runtime timing

The normal groove events that are allowed to continue retain:

- their original sequencer tick;
- their original velocity;
- their normal rhythm period.

Do not copy those events into the fill.
Do not shift them relative to the fill.
Do not generate a replacement kick pattern from the fill.

The fill window merely gates the existing normal percussion event stream by
logical role.

## Sequencer / architecture constraint

The current Omnichord design isolates percussion, bass and chord sequencer
lanes. Fill behavior remains a percussion-only operation.

Playing a fill must not:

- stop/reset transport;
- reset the AMY sequencer timebase;
- rewrite bass events;
- rewrite automatic-chord/arpeggio events;
- restart the rhythm;
- alter tempo.

The final implementation mechanism must respect the existing percussion tag
capacity and lane-local update rules.

This handover specifies **which normal percussion events are musically allowed
through**, not the eventual AMY tag scheduling mechanism.

## Validation requirements

Future implementation/tests must verify at least:

1. the continuation JSON parses;
2. it contains exactly 270 fill entries;
3. every `fill_id` exists in `drum_fills_timing.json`;
4. every fill in `drum_fills_timing.json` occurs exactly once;
5. every `continue_roles` value is a valid logical activity role;
6. no physical sample/preset/MIDI-note comparison is used for continuation;
7. a whitelisted but inactive role produces no event and no error;
8. a non-whitelisted normal percussion event is suppressed during the fill;
9. fill events themselves are never suppressed by this whitelist;
10. fills containing `low_primary` do not pass normal `low_primary` or
    `low_secondary`;
11. fills containing `timeline_primary` do not pass the normal
    `timeline_primary`;
12. kit selection does not change continuation behavior;
13. activity-level selection does not select a different continuation table;
14. allowed normal events retain their original timing and velocity;
15. bass/chord lanes and transport/timebase remain untouched.

## Coverage summary

The generated catalogue contains:

- fills: **270**
- unique fill IDs: **270**
- fills where normal bass drum continues: **194**
- fills where the fill owns the bass drum: **76**
- fills with jazz pedal-hi-hat continuation: **15**
- fills with independent timeline continuation: **8**
- fills where the fill owns/rephrases the timeline: **32**
- fills with independent texture/shaker continuation: **60**

## Final warning to Codex

Do not implement a fill as either:

```text
normal drums OFF, fill ON
```

or:

```text
normal drums ON, fill overlaid on everything
```

Both are musically wrong.

The correct behavior is:

```text
normal groove continues selectively
    filtered by the fill-specific continue_roles whitelist
+
the fill's own authoritative events
```

Filtering is done by logical percussion role **before kit mapping**.
