# C2 — Large Frozen Payload Audit

## Scope and safety boundary

This audit was performed at `main` commit
`1d9cec4095f36fcbb5ada6df094a08fcd258e01a`. It hashed every tracked file
under `data/generated/` (58 top-level stages, 9051 files) and changed no
existing generated, canonical, Gold, annotation, manifest, or protection
file. The only C2 outputs are this report and
`data/derived/large-frozen-payload-audit-c2.json`.

The audit is structural. It uses Git's tracked-file list, byte sizes, SHA256
hashes, fixed-string repository reference scans, present builder/validator
paths, and metadata-stripped JSON comparison. It does not interpret
historical identity or rewrite any payload.

## Size findings

The audited generated payload is **684,648,065 bytes** (about 652.8 MiB)
across **9051 files**. The largest stages are:

| stage | tracked bytes | files | raw-api bytes | semantic/result bytes |
| --- | ---: | ---: | ---: | ---: |
| `hdb2-p1` | 185,310,821 | 103 | 229,462 | 185,058,171 |
| `hdb2-f` | 129,520,471 | 309 | 354,295 | 27,036,899 |
| `sfh1` | 71,711,728 | 3540 | 20,580,260 | 46,775,204 |
| `sfh2` | 71,549,599 | 157 | 282,602 | 70,393,981 |
| `sfh2r1` | 61,102,965 | 32 | 0 | 2,581,160 |
| `hng1` | 15,908,201 | 48 | 0 | 13,916,142 |

The `hdb2-f` semantic/result column is intentionally not used as a total
stage size: most of its bytes are frozen replay/debug evidence. The exact
breakdown for every stage is in the JSON (`stage_inventory`).

The audit counted:

- **6040 raw provider-response files**, totaling **28,766,609 bytes**.
  Their exact byte total is also available by stage in `raw_api_bytes`; raw
  bytes remain important provenance even when parsed results exist.
- **388 provenance/manifest files**, **30 human-review files**, **159
  transport diagnostics**, and **1237 replay/intermediate files**.
- **189 active semantic-input files** and **1009 frozen semantic-result
  files**.

## Duplicate and near-duplicate content

There are **284 exact duplicate groups**. Treating one path in each group as
the retained copy gives **84,499,177 bytes** of theoretical duplicate
savings (not a deletion recommendation). The biggest group is the pair of
HDB2-F live runs, with **58,716,324 bytes** repeated exactly between
`20260826T-HDB2-F-02` and `20260826T-HDB2-F-03`. Other substantial repeated
families are the PSL1.3 replay graph/prompt packets and repeated SFH replay
outputs.

The audit also found five metadata-only near-duplicate groups. They are
small manifest variants (for example, replay manifests differing in run
metadata). Their semantic equality was not assumed and no files were
normalized.

The detailed JSON records each exact duplicate's SHA256, size, paths,
duplicate count, and potential savings, plus the metadata-stripping rule
used for the near-duplicate candidates.

## Dependency and retention interpretation

The per-file `dependency_type` values distinguish:

- `DIRECT_RUNTIME_DEPENDENCY`: current builders, projections, retrieval
  code, or active experiment runners name and consume the stage family;
- `HASH_ONLY_PROVENANCE`: the reference is retained as a hash/manifest
  contract;
- `PATH_ONLY_PROVENANCE`: a tree/path is named for validation, replay,
  review, or provenance, but no per-file semantic import was established;
- `NO_LIVE_DEPENDENCY`: no current repository reference was found outside
  the payload.

This pass found no `NO_LIVE_DEPENDENCY` file in the current generated scope;
all retained families are named by at least a current validator, runner,
manifest, or downstream audit. The separate `raw_api_dependency_audit`
records distinguish **3630 raw files / 22,736,109 bytes** in trees directly
parsed by current replay/consolidation code from **2410 raw files /
6,030,500 bytes** whose current use is writing, hashing, path validation, or
provenance. A raw tree with a direct reader is therefore not a cold-archive
candidate until that reader accepts a verified content-addressed descriptor;
the remaining raw trees are still retained as frozen provenance rather than
being treated as disposable merely because their writers are no longer on the
active path.

The audit marks **552,462,379 bytes** as blocked by active dependencies and
**2,437,662 bytes** as blocked by frozen-hash contracts. These are not safe
to remove from HEAD without a separate contract migration. It marks
**39,140,132 bytes** `KEEP_IN_HEAD`, primarily protected manifests and review
authority, and **6,108,715 bytes** as cold-archive candidates. The cold
candidate label is a proposal only: a content-addressed archive descriptor,
byte verification, and validator support must be implemented before any
tracked file is moved.

The report also identifies **84,499,177 bytes** as exact content-addressable
deduplication candidates. This figure overlaps frozen/protected experiments;
it is a storage-design opportunity, not a C2 change. The combined raw
cold/dedup upper bound is **90,607,892 bytes** before accounting for
descriptor and validator overhead.

Reconstructability is separate from retention. The audit reports:

- **6,932 files /  network-required bytes** whose provider responses or
  semantic outputs cannot be recreated without the provider evidence or
  network;
- **263,353,257 bytes** of deterministic replay/rebuildable output that is
  nevertheless protected;
- **5,202,533 bytes** classified as deterministic-rebuildable without the
  stronger protected status;
- **39 files** not reconstructable from the present repository alone.

Rebuildable does not mean disposable: a later frozen hash or selection
contract can make an otherwise deterministic output part of the required
historical baseline.

## HDB2 dependency DAG

The actual static dependency edges recorded by the audit are:

```text
HNG2 → HDB1 wave 1 → HDB1 wave 2

HDB2-P1 → HDB2-P1.1 → HDB2-P2T → HDB2-F → HDB2-XE0
       └───────────────────────────────┘

HDB2-LJ0 → HDB2-PSL0 → HDB2-PSL1 → PSL1.1 → PSL1.2 → PSL1.3
                                                        ↓
                         PSL1.3A → PSL1.3B → PSL1.3C → PSL1.3D
```

The arrows describe payload/contract flow, not semantic endorsement. HDB2
rescue branches retain raw responses, reviewer packets, profile checks,
graphs, and fixed manifests separately because later validators and frozen
selections reference particular runs. The JSON records the exact payload
families and code basis for each edge.

In particular, repeated PSL1.x replay trees can be deduplicated only after
the path-based frozen validators accept a content-addressed reference. The
HDB2-F duplicate live runs are the clearest first storage candidate, but
their manifests, selected evidence, and review contracts must remain
verifiable.

## HNG2 and SRM

The retained HNG2 chain is:

```text
HNG0 → HNG0.1 → HNG0.2 → HNG0.2R → HNG1 → HNG1R → HNG1R2 → HNG2
```

HNG2 schema/controller variants use the frozen schema baseline, live
envelopes, SRM0 evidence, and replay manifests. SRM0 convergence rounds,
search traces, usage records, and repair states are separate research-memory
evidence; they are not interchangeable with HNG2 semantic results. The
current schema replay explicitly protects the SRM0 root. Raw/envelope
content may become archive material only with a descriptor and a replay
validator that can verify it.

## Git history and future storage

Three different size questions must not be conflated:

1. Reducing checked-out HEAD size requires a future tracked-file removal or
   replacement. It would reduce current working-tree and future clone
   transfer size only after the archive contract is migrated.
2. A cold archive can preserve the bytes outside the normal checkout while
   keeping a compact descriptor and SHA256 manifest in HEAD.
3. Removing a file in a later commit does **not** remove its historical Git
   objects. C2 performs no history rewrite. `git filter-repo`, orphan-history
   migration, and force-push are outside scope and require a separate
   destructive review.

## Recommended C3 boundary

The safest C3 boundary is a **descriptor-first, one-family-at-a-time
content-addressable archival migration**, beginning with exact duplicate
HDB2-F/PSL replay payloads that have no unique semantic or human-review
authority. C3 should first add an archive descriptor and a validator that
fetches/verifies every byte, then migrate only the proven duplicate/raw
subtrees while preserving manifests, selected semantic outputs, review
authority, and all downstream frozen hashes. HDB2-P1, HDB2-F semantic
frontier inputs, SFH1/SFH2 current inputs, HNG1R2/HNG2 baselines, and SRM0
should remain in HEAD until their consumers are explicitly migrated.

No C3 migration was performed in C2.

## Protected-state check

The observed SHA256 for `data/derived/sc1-site.json` remains
`cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8`.
The audit also recorded current hashes for WP1, the generated SC1 copy,
canonical people/relations/aliases, and reviewed SFH authority files in the
JSON. Existing historical/generated payloads were not changed.
