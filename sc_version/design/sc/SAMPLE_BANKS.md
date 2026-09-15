# SuperCollider sample-bank evidence

Status: source and local-inventory contract

Last verified: 2026-09-14

The bounded source catalogue is
[`../../supercollider/sample-bank-sources.json`](../../supercollider/sample-bank-sources.json).
It records the eleven pinned Git sources and the separate University of Iowa
discovery authority from the migration specification. A commit pin is source
identity; it is not evidence that a downloaded archive or its audio payload was
verified.

Large sample binaries remain outside Git and outside the application AppImage.
After installing a pinned bank, create a file-level asset lock with:

```bash
python sc_version/tools/banks/bank_source_catalog.py \
  sc_version/supercollider/sample-bank-sources.json \
  --bank-id vsco-2-ce \
  --root /path/to/verified/bank \
  --output /path/to/asset-locks/vsco-2-ce.json
```

The inventory records every supported audio path, byte size and SHA-256 and
rejects unresolved Git LFS pointer files. Keep generated full asset locks with
the installed asset set rather than committing tens of thousands of file
records to the application repository. Release evidence hashes the bounded
source catalogue and the normalized runtime manifest.

The current playable bank is VSCO 2 CE. Its normalized source manifest covers
all 75 source SFZ mappings, all 3,168 audio files and all 3,163 mapped regions.
Runtime reachability is narrower and explicit: 2,034 unique files are used by
those regions and another 132 are used directly by the PCM-drum catalogue.
The pinned runtime branch therefore contains 2,166 WAV files and omits the
remaining 1,002 recordings, which have no executable reference. This is a
derived packaging selection, not a claim that the omitted source recordings
were deleted from or unsupported by the full source inventory. The
checked-in [`vsco-opcode-coverage.json`](../../supercollider/vsco-opcode-coverage.json)
accounts for every preprocessed opcode in all 75 mappings and currently has no
unsupported entry. The audit records exact occurrence counts and a bounded set
of source locations, so its diagnostic value does not scale into a second copy
of every region. The
other selected banks and Iowa inventory remain migration backlog and must not
be represented as installed or playable until their own generated asset locks,
normalized manifests and audio acceptance evidence exist.

The runtime branch is `lb-omnichord-runtime-v1` at commit
`78b95e70efe4349eeb03855f7f7654cb81c8c62f`, derived from source commit
`440300901dfe9275fd84e0b7763af1f8443ae62e`. Installations are shallow clones;
the source history and unreachable recordings are not transferred. An atomic
`lb-omnichord-samples.json` receipt beside the samples lists all 2,166 selected
paths. Startup compares its parsed content with the checked-in required-sample
list and checks the file inventory before the engine can load a buffer. It does
not calculate recording hashes at startup; the pinned Git commit establishes
the contents of a downloaded collection.

The checked-in
[`salamander-opcode-coverage.json`](../../supercollider/salamander-opcode-coverage.json)
is a deliberately failing capability inventory of the single mapping at the
exact pinned Salamander revision. It finds 69 distinct opcodes, 49 of which
still require explicit normalization or a reviewed metadata disposition. This
artifact prevents a future importer from calling the piano complete after
merely reading its note/velocity regions: controller curves, start offsets,
release decay, sustain transitions, pedal noise and polyphony policy remain
visible work. Audit reports carry their bank ID and source pin so an opcode
count cannot be mistaken for evidence about a different checkout.

The offline SFZ compiler expands standard `#define` and inline or whole-line
`#include` directives before parsing, retains the originating file and line for
every region, and rejects undefined/recursive macros, include cycles and paths
escaping the bank root. This is required by Salamander and the Karoryfer/drum
banks; it is preprocessing support, not a claim that their much larger audible
opcode surfaces have already been normalized.

Audio inventory accepts the lossless PCM containers used by the selected
banks, including WAV, AIFF and FLAC, through the maintained libsndfile-backed
`soundfile` package. Decoded-content hashes use canonical signed 32-bit,
left-aligned, little-endian PCM, so the same lossless recording can be detected
across different containers without reducing source precision. Unsupported
floating-point or compressed lossy encodings fail rather than acquiring a
misleading `original_bit_depth` value.

The normalized trigger field now distinguishes attack, physical-key release
(`release_key`) and sustain-aware final release (`release`). The SC selector
never admits release recordings into an attack, and the owner-scoped sustain
state passes release velocity to the matching layer. Release candidates are
pinned for the complete held-note lifetime, including across a two-phase
program replacement. Because release velocity, random choice and sequential
round robin are not known at attack time, all release candidates for the key
and articulation are pinned; only the selected release layer is played at the
corresponding release boundary. This is the generic lifetime foundation; it is
not yet an implementation claim for bank-specific `rt_decay`, pedal-noise,
choke or CC-curve behavior.

A source-tree metadata audit at the pinned commits found 183 VCSL mappings, 1
Salamander mapping, 71 Black and Green, 64 Black and Blue, 39 Meatbass, 6 Emily
Guitar, 48 Bear Sax, 13 WereSax, 419 Virtuosity Drums and 152 Swirly Drums
mappings. The guitar, bass, sax and drum mappings use extensive CC modulation,
release/choke, loop and include semantics beyond the current VSCO runtime.
Unsupported audible opcodes must remain explicit compiler failures rather than
being silently discarded to inflate a nominal instrument count.
