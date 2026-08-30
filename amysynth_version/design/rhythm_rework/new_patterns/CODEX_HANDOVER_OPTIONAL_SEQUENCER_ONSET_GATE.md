# Codex handover — optional explicit sequencer onset gate

## Status and scope

This is an optional future route. It is not implemented and it is not required
by the current LB Omnichord rhythm implementation.

The current application already solves automatic-chord/arpeggio lifetime with
short immutable AMY `ONE_SHOT` children. Every sounding child owns its note-on
and normal note-off. `/1`, `/2`, `/3` and `/4` use disjoint pattern families,
so a rate change replaces future triggers without shortening a running note.

No AMY source file should be changed merely because this handover exists.

## Motivation

AMY currently has finite pattern muting:

```text
zQM<instance-tag>,<duration-ticks>
```

LB uses that operation inside drum fills to suppress selected base-role loop
instances for the known fill duration. A future feature may need explicit state
instead: turn suppression on now, and turn it off later, without calculating a
large sentinel duration or coupling the first command to a fixed window.

The desired abstraction is an **onset gate**, not an audio mute and not an
all-notes-off.

## Recommended generic semantics

A possible wire shape is:

```text
zQG<instance-tag>,1Z   # gate future onsets
zQG<instance-tag>,0Z   # allow future onsets
```

The letter and exact syntax are provisional. Preserve the existing `zQ`
sequencer-control family and target the nested pattern's public instance tag,
not an LB-specific drum role, instrument name, sample, patch or rhythm lane.

Required behavior:

1. `ON` blocks only future positive-velocity note-on events emitted by the
   targeted sequencer pattern instance.
2. Note-offs always execute at their normal scheduled tick while the gate is
   on. A sounding note is never shortened and can never hang because its off
   was suppressed.
3. Non-note control events continue unless the final generic AMY API explicitly
   defines a narrower, separately tested rule.
4. Pattern phase and tick progression continue unchanged.
5. `OFF` allows the next normally scheduled onset; it does not retrigger missed
   events and does not restart or requantize the pattern.
6. Direct/manual wire events outside the targeted sequencer instance are
   unaffected.
7. Several tagged instances can be gated independently.
8. Repeating `ON` or `OFF` is idempotent.
9. Reset/stop/instance-retirement behavior must be explicit. Prefer state keyed
   by public instance tag so a quantized replacement using that same tag cannot
   leak onsets between `ON` and `OFF`.

The operation must remain musically generic. LB Omnichord may decide that an
instance tag represents a kick, hi-hat or another role, but AMY must not know
that meaning.

## Why current `zQM` is not an implicit on/off switch

Do not encode `ON` as `zQM<tag>,UINT32_MAX` and `OFF` as a zero duration without
first defining rollover, replacement and reset behavior. That would turn a
finite-duration API into hidden state and would eventually expire at unsigned
tick wrap.

More importantly, the current AMY implementation skips ordinary child events
while an instance is muted. That includes releases; it does not yet implement
the stronger onset-only rule above. Documentation or naming which suggests
"only future onsets" is insufficient proof—engine behavior and tests must
distinguish note-on from note-off.

## Ordering and nesting

If the command is stored inside another pattern, process due gate controls
before ordinary events on the same tick. This is the existing useful property
of fill-start suppression: an onset must not leak merely because its target
instance occupies an earlier player slot.

Keep nesting at AMY's existing two levels. The gate is a leaf control and must
not introduce recursive pattern execution.

## What this does not solve by itself

An onset gate does not transfer ownership of already-scheduled releases. Code
must still avoid replacing or deleting the only note-off for a sounding note.
The current chord implementation solves that with immutable one-shot children;
do not replace it with a root-tag drain merely because an explicit gate becomes
available.

The gate also does not express LB's musical policy. Fill continuation remains a
whitelist of logical drum roles in LB Omnichord. AMY only supplies a generic
tag-targeted mechanism.

## Required AMY proof before adoption

Any future implementation needs rigorous API and wire tests for at least:

1. legacy sequencer API and wire behavior remains byte-for-byte compatible;
2. gate-on before a same-tick onset prevents that onset;
3. a note already sounding receives its original off while gated;
4. gate-off does not replay missed onsets;
5. loop phase continues through the gated interval;
6. two tagged instances remain independent;
7. an untagged instance cannot be targeted accidentally;
8. quantized tagged replacement has the documented inheritance behavior;
9. repeated on/off is idempotent;
10. tick wrap, reset, stop and instance retirement clear or preserve state only
    as documented;
11. direct/manual notes and unrelated synths are unaffected;
12. API calls and wire commands have equivalent behavior.

Only after those AMY tests pass should LB add integration tests and consider
using the command.

## Repository workflow if implemented later

Develop the generic primitive in a clean AMY upstream branch based on the then
current `shorepine/amy` main. Keep LB-specific names and Codex handovers out of
that upstream branch. Integrate the tested commit into a new fork release branch
using the established AMY release workflow, then update LB Omnichord's pinned
AMY commit and all platform builds together.

Do not modify the already offered nested-sequencer pull request merely to add
this optional feature.
