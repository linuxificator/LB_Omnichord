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

The current playable bank is VSCO 2 CE. Its normalized manifest covers all 75
source SFZ mappings, all 3,168 audio files and all 3,163 mapped regions. The
remaining 1,134 source recordings are visible as `unmapped-source-audio`; that
is evidence of incomplete curation, not permission to silently omit them. The
other selected banks and Iowa inventory remain migration backlog and must not
be represented as installed or playable until their own generated asset locks,
normalized manifests and audio acceptance evidence exist.

The offline SFZ compiler expands standard `#define` and inline or whole-line
`#include` directives before parsing, retains the originating file and line for
every region, and rejects undefined/recursive macros, include cycles and paths
escaping the bank root. This is required by Salamander and the Karoryfer/drum
banks; it is preprocessing support, not a claim that their much larger audible
opcode surfaces have already been normalized.

A source-tree metadata audit at the pinned commits found 183 VCSL mappings, 1
Salamander mapping, 71 Black and Green, 64 Black and Blue, 39 Meatbass, 6 Emily
Guitar, 48 Bear Sax, 13 WereSax, 419 Virtuosity Drums and 152 Swirly Drums
mappings. The guitar, bass, sax and drum mappings use extensive CC modulation,
release/choke, loop and include semantics beyond the current VSCO runtime.
Unsupported audible opcodes must remain explicit compiler failures rather than
being silently discarded to inflate a nominal instrument count.
