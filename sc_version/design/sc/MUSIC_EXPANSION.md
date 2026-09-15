# SuperCollider music expansion

Status: authoritative implementation and data contract
Owner: SuperCollider musical catalogue
Applies to: `sc_version`
Last verified: 2026-09-15

## Scope and ownership

The SuperCollider edition owns its musical data separately from the retained
AMY edition. Python resolves immutable musical plans and publishes them over
the typed OSC protocol. SuperCollider alone owns clocks, execution, note
lifetimes, gates and sample playback. Neither the Qt UI nor its controller
handlers inspect sequencer phase or schedule musical events by wall-clock
time.

The generated catalogues under
`sc_version/qt_frontend/music/sc_expansion/` are the runtime authority. They
are produced deterministically by `tools/build_sc_music_expansion.py` from the
reviewed source bundle, whose input hashes are preserved in the generated
manifest. Runtime code never imports the build tools or the source bundle.

## Catalogue inventory

The drum browser has fifteen explicit kits:

- nine PCM kits: Old Parlour, Tight Studio PCM, Concert Percussion, Marching
  Battery, Son and Salsa, Brazilian Colours, Hand and Wood, Gongs and Metal,
  and Prepared Metal;
- five native SuperCollider kits: SC Basic, SC 808, SC Electro, SC Oto 309 and
  SC SOS;
- the legacy VSCO PCM kit retained for existing presets and users.

The generated expansion contains:

- 54 rhythm identities for each of the fifteen kits: 810 exact arrangements;
- five authored activity levels per arrangement;
- five fill levels per arrangement: 4,050 exact fill variants;
- 1,664 neutral bass riff definitions plus 810 kit/rhythm articulation
  contexts;
- 18 complete factory presets.

The largest activity sequence has 57 events. The largest fill plus its exact
continuation has 84 events, below the reviewed 96-event budget. No runtime
heuristic invents, simplifies or truncates these event lists.

## PCM drum playback

The nine new PCM kits reference 51 reviewed sample sets and 262 WAV aliases.
Each set declares inclusive velocity layers and deterministic round robins.
Round-robin state is scoped by musical owner, kit, pad and velocity layer, so
an OMNI rhythm and an independently played MIDI drum row cannot disturb each
other's sequence.

Every hit carries a semantic musical role and a concrete kit pad. The semantic
role drives continuation and gating; the pad selects the exact PCM or native
program. Sample start offsets, fixed playback rates, gain, filters, pan, choke
group, fade time and duration cap are data, not frontend conditionals. Event
duration caps are optional: zero means the sample profile owns its full
duration, otherwise the shorter of profile duration and event cap is used.

The external VSCO sample source is acquired from the pinned runtime snapshot at
commit `78b95e70efe4349eeb03855f7f7654cb81c8c62f` of the configured repository.
Its 2,166 audio files are the exact union of playable SFZ-region references
and direct PCM-drum references. Runtime admission does not require Git
metadata: an existing checkout or ordinary copy is accepted only when every
required path exists. The installation receipt records the full selected path
list and is compared as JSON content rather than serialized bytes. No hashes
are calculated during startup. This makes every PCM alias reproducible across
source runs and packages without downloading unreachable source recordings.

The generated compact drum catalogue retains the source kit-calibration
records rather than treating them as build-only metadata. A source-level test
qualifies every kit against one common reference groove and every pad against
the same peak window. This evidence is independent of preset role volumes:
presets remain musical choices, while kit calibration makes those choices
comparable.

## Rhythm and fill behavior

Each arrangement retains its authored period, event timing, role, pad,
velocity, microtiming and duration metadata. Activity selection changes the
published immutable definition without moving transport phase.

Fills are finite executions over a snapshot of their published definition.
The selected kit and revision therefore remain stable until that fill ends,
even if the user changes the current kit in the meantime. A fill gates only
the semantic role-and-slot streams which it replaces. Unchanged root events
continue at their original phase and level; omitted but desired continuation
events are reintroduced exactly. This supports sparse `/8` patterns, odd
meters, foot-pattern exceptions, Son-style timelines and dense level-five
fills with the same mechanism.

The controller chooses a fill and publishes definitions, but the engine clock
owns its quantized launch and completion. Disabling fills lets an already
started fill finish and prevents later scheduled launches.

## Bass articulation

The 1,664 bass riffs keep their original onset, pitch, role, velocity, accent
and slide source data. A pure resolver combines one neutral riff with the
selected kit/rhythm context and activity level. Resolution is deterministic,
does not mutate the source riff and never changes pitch or onset.

Voice capabilities are explicit data. A gated voice may reuse one handle for
ties and legato glide; a sample or unknown voice gets conservative detached
attacks with bounded fallback durations. Native acid voices additionally own
an accent trigger. On a linked note, glide time and destination frequency are
changed without retriggering, and a reviewed destination accent is fired at
that same sequencer tick. Programs that do not advertise that capability do
not receive invented articulation.

The resolver prevents a link chain from crossing the phrase boundary, so every
gesture has an explicit final release. The frontend never tracks held bass
notes or calculates when that release is due.

## Factory presets and compatibility

The eighteen factory presets are complete snapshots: rhythm, activity levels,
kit, fill order and density, bass selection, chord/arpeggio settings, program
choices, tuning and mixer state are imported together. Existing user presets
remain user-owned and are not overwritten. The factory-bank revision controls
only the shipped defaults.

Older SuperCollider runtime configurations are migrated additively to current
configuration revision 7 and protocol revision 2. Older bass-riff documents
without expansion articulation still load with neutral links. The legacy PCM
kit and prior native kit identities remain available.

## Evidence boundary

Executable tests validate every arrangement/activity combination, every fill
and exact continuation, every context/rank bass resolution, all source riff
timing and harmony, all factory preset identities, every inclusive PCM velocity
boundary, owner-scoped round robin, source offsets and duration caps. The SC
bank tests parse all runtime sample identities and render production sample
SynthDefs from deterministic mono and stereo fixtures.

CI cannot redistribute the external sample recordings. The checked-in
manifest records every referenced WAV path and SHA-256; a real sample tree is
verified locally against it, while packages install the pinned source on first
launch when no tree is present.
Automated evidence establishes identity, routing, bounded output and lifetime
behavior; subjective musical balance still requires listening on physical
audio hardware.

A production-QML source pass on Linux exercised 836 public actions, selected
all fifteen drum kits in both percussion locations, changed every rhythm and
ran simultaneous rhythm, bass and arpeggio playback. A subsequent four-cycle
pass exercised 3,306 actions and the complete SYN/PCM catalogue. Its twelve
independently captured PipeWire windows remained non-silent, reported no
clipped samples and had no gap longer than 0.60 seconds. The owned `sclang`,
Supernova and frontend processes shut down cleanly with no server failure or
buffer exhaustion.
