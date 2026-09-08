# AMY reusable sequences

Status: current consolidated implementation record
Owner: LB Omnichord AMY integration
Last verified: 2026-09-08

## Public model

Repeated tagged `H` events accumulate in one reusable stored definition. `HR`
clears future contents and `HC` controls an execution with named API actions
`start`, `stop` and `gate` (wire values 1, 0 and 2). Untagged historical root
sequencer behavior is unchanged. The older nested-pattern and sequencer-group
prototypes are not part of the current model.

Definitions contain ordinary AMY events, including notes and parameter
changes. Executions own repeat/alignment/timing state. Stop/gate cleanup stays
inside AMY so callers do not mirror note or event lifetime. LB owns only
musical selection and sends generic wire operations.

## Publication and realtime ownership

Definition edits publish immutable generations through a short pointer swap.
Executions retain the generation they started with. Replaced generations are
retired through an intrusive list and reclaimed outside the render critical
path when no execution holds them. This RCU-like ownership avoids allocation,
copying or freeing from realtime rendering. Two-buffer ping-pong is
insufficient because long-lived executions can overlap more than two edits;
general garbage collection is unnecessary because reference ownership is
explicit.

Active executions have a bounded index; completed events and irrelevant event
classes are not repeatedly scanned, and uniform periodic definitions advance
from their previous due position. These are generic performance improvements
with unchanged ordering and tick semantics.

## Compatibility

The intentional source compatibility change is that repeating a stored tag
accumulates rather than overwriting its previous definition. Callers wanting
replacement issue `HR` first. Existing untagged scheduling remains byte- and
behavior-compatible. Host C/Python/API-generation tests, concurrency tests and
legacy scheduler comparisons cover the boundary.

The active LB release supplies 1,280 definition identities, 64 events per
definition and 40 active or alignment-pending executions. Inactive preloaded
fills consume memory but negligible realtime processing.

AMY release branch `releases/amy_omnichord_R20260908T005616` at
`e9a96c20da31b4130a243bf75b984408c1dff5e0` is the current immutable consumer
pin. Exact current pins remain authoritative in
`../../qt_frontend/packaging/release_inputs.json`.

