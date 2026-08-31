# Codex handover: documentation and repository hygiene

Status: analysis; no product behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Documentation as an architecture product

The repository's design documentation is a strength: it records exact musical,
MIDI, QML, transport, platform and release contracts and gives Codex a required
reading route. It also contains historical handovers and repeated facts that
can become contradictory. Documentation quality therefore needs the same
ownership, validation and lifecycle discipline as code.

## Finding D1 — active documentation contradicts implemented MIDI support

`design/midi.md` correctly states that Linux ALSA sequencer input is
implemented and creates `LB Omnichord / MIDI In`.

Two other active-looking files remain stale:

- `design/unclear.md` calls direct ALSA sequencer support future work;
- `qt_frontend/INSTALL.md` says VMPK needs a virtual raw bridge and that direct
  ALSA sequencer input is not implemented.

`qt_frontend/docs/WINDOWS_NATIVE.md` also describes the current reader as Linux
ALSA-raw-only in a context where ALSA sequencer now exists; its statement that
Windows MIDI input remains unsupported can still be correct.

This is evidence that cross-file prose duplication is not a reliable source of
truth. Correct the contradictions as a dedicated docs change, but first declare
which document owns support status. Installation docs should link/summarize,
not independently redefine MIDI architecture.

## Finding D2 — documents lack uniform status and applicability metadata

Some files are authoritative contracts, some branch handovers, some historical
records and some unresolved-question lists. Their filenames/locations do not
always make that role obvious.

Add lightweight front matter or a standard header:

- Status: authoritative / analysis / proposal / historical / superseded;
- Owner: subsystem contract that resolves conflicts;
- Applies to: branch, release/config/schema revision where relevant;
- Last verified date and verification command/evidence;
- Supersedes / superseded by;
- Required reading: yes/no and task route.

Do not require every historical file to stay current. Require it to be clearly
historical and outside the active reading route.

## Finding D3 — exact facts are repeated manually

Pattern ranges, capacities, platform support, test counts, release tags and AMY
SHAs recur across design, install, handoff and workflow files.

Policy by fact type:

- behavior meaning: one authoritative design contract, linked elsewhere;
- current config value: source config/schema, optionally generated table;
- immutable release/incident history: may repeat exact commit/tag as a dated
  record;
- current branch state: root `CODEX_HANDOFF.md`, updated or explicitly archived;
- test count: label as observed at a dated run, not a timeless requirement;
- wire compatibility: executable contract tests plus owning protocol doc.

Avoid generating prose wholesale. Generate only exact tables/manifests that
would otherwise drift.

## Finding D4 — runtime datasets are duplicated in design

Nine runtime drum JSON files are byte-identical to files under
`design/rhythm_rework/new_patterns`. Design documentation should not become a
second data distribution. Replace the copies with links, schema/provenance and
hash/count evidence. See `CODEX_HANDOVER_MUSICAL_DOMAIN_AND_DATA.md`.

## Finding D5 — tracked temporary mutation scripts

The repository tracks large scripts named
`tools/tmp_apply_reverb_motion.py` and `tools/tmp_apply_local_amy.py`. No active
references were found. A tracked `tmp_` script that rewrites code/data is easy
to mistake for a supported tool and bypass normal review.

Recommendation:

- inspect history to confirm their one-off purpose;
- remove them if reproducible history is already in Git;
- if still useful, rename under `tools/migrations/` or `tools/generators/`, add
  inputs/outputs/idempotence documentation and tests;
- reject new tracked `tmp_*` files outside an explicit fixture directory.

Do not run mutation scripts merely to determine whether they are obsolete.

## Finding D6 — diagnostics need a clear namespace

The simple slider baseline programs are legitimate regression/reproduction
tools and were essential to isolating native Qt behavior. Place such tools
under `tools/diagnostics/`, document dependencies and expected output, and keep
them read-only by default. Distinguish them from production entry points,
generators and test-support servers.

Suggested tool categories:

- `tools/diagnostics/`: interactive observation, no repository writes;
- `tools/generators/`: deterministic source/data generation;
- `tools/migrations/`: one versioned input-to-output transform;
- `tests/support/`: test-only adapters/fixtures;
- `packaging/`: release/build behavior.

## Finding D7 — screenshot retention duplicates binaries

The root `screenshots/lb_omnichord.png` duplicates a frontend docs screenshot.
The current `omni.png` and several release-tagged `omni-R...png` files are also
byte-identical. Release-tagged names are intentionally useful because a file
states which release generated it; keeping every generated PNG in Git will,
however, grow history indefinitely even when pixels are unchanged.

Define a retention policy rather than removing them ad hoc:

- keep current README image in Git;
- keep latest N release-tagged images or only images whose content changed;
- attach full historical screenshots to releases/artifacts;
- retain release tag in filename/metadata as requested;
- verify PNG signature, dimensions and that the app—not an error dialog—fills
  expected regions;
- avoid an image-comparison system for merely deciding the filename.

The workflow's short semantic/sanity check remains necessary; a valid PNG can
still be a screenshot of a crash.

## Finding D8 — repository-wide editing policy is implicit

The root `.gitignore` only covers Python caches/bytecode. There is no
`.editorconfig`, explicit `.gitattributes`, contribution guide, security policy
or code ownership metadata.

Appropriate lightweight additions:

- `.editorconfig` for UTF-8, LF, final newline and language indentation;
- `.gitattributes` for line endings and binary files, especially Windows
  scripts and PNG/assets;
- `CONTRIBUTING.md` routing to design reading, branch/release policy and test
  commands;
- `SECURITY.md` with the supported release/security reporting route;
- optional CODEOWNERS if repository collaboration actually uses reviews;
- expanded ignores for local Qt/build/tool artifacts, without ignoring source
  fixtures.

Do not add governance files that nobody will follow; assign an owner and make
CI verify only objective parts.

## Finding D9 — root handoff ages quickly

`CODEX_HANDOFF.md` is valuable but its opening current-branch/release section
described the start of `rework/external_controls` and an older release before
this audit. Dated historical content is still useful; “current” pointers must
be updated whenever a branch explicitly creates a new continuation handoff.

Keep the root handoff compact at the top:

- current working branch and exact base;
- latest successful full release and screenshot-only main commit;
- mandatory reading links;
- active analysis/implementation next step;
- historical decisions below, clearly dated.

Do not copy the full content of every subsystem contract into it.

## Documentation validation

Add a test/tool that checks:

- every Markdown relative link resolves;
- every active contract has status/owner;
- routed files exist and are not marked superseded;
- generated configuration/range tables match source;
- no byte-identical runtime dataset tree exists under design;
- references to branches/tags/SHAs are labeled historical or current;
- no active doc contradicts the authoritative platform capability manifest.

Semantic contradiction detection cannot be fully automated. A small support
capability manifest can generate “implemented/not implemented” tables, while
human review owns nuanced behavior.

## Definition of done for a documentation change

- the owning contract is updated first;
- summaries link to it and do not create a second authority;
- stale/historical docs are labeled, moved or corrected;
- commands, paths and local links are verified;
- behavior-bearing claims cite executable tests or a release run;
- no Codex-only handover is copied into a clean upstream AMY offer branch;
- `git diff --check` and the documentation validation pass.
