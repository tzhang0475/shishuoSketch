# C2.1 — Git object-level storage audit

This read-only audit was performed at baseline `99b82e3d5a1665a6909682d76b1cf0cac475ea8e`. It adds no payload descriptors, does not regenerate data, and does not rewrite Git history. The machine-readable measurements are in [git-object-storage-audit-c2-1.json](../data/derived/git-object-storage-audit-c2-1.json).

## Executive result

The large same-HEAD duplicates identified by C2 are mostly a working-tree/path concern, not a Git blob-storage duplication concern. All 284 exact duplicate groups already resolve to one Git blob SHA per group. The 156,477,130 duplicate occurrence bytes imply 84,499,177 bytes of avoidable checked-out path content, but the actual incremental Git blob cost is **0 bytes**; only tree entries and path names are repeated.

The HDB2-F F02/F03 family is the clearest example: its 45 duplicate groups account for 58,716,324 working-tree bytes that could theoretically be represented once, but add no second blob payload to Git. A descriptor layer would therefore improve checkout/path layout only; it would not materially reduce the current Git object database by itself.

The recommended C3 boundary is consequently a constrained cold-archive pilot for selected unique, low-authority payloads, with content-addressed descriptors designed and validated before any migration. Do not build a descriptor layer solely to remove exact duplicate paths.

## Distinct storage measures

These values are deliberately not added together:

| Measure | Bytes / count | Meaning |
| --- | ---: | --- |
| Working-tree tracked bytes | 972,949,514 | Bytes in all tracked files checked out at HEAD |
| HEAD occurrence bytes | 972,949,514 | Sum over tracked paths, counting repeated content per path |
| HEAD unique blob bytes | 877,109,525 | Uncompressed content of 12,570 unique HEAD blobs |
| HEAD unique blob physical storage | 135,099,152 | `git cat-file` physical sizes for those unique blobs |
| Git object database | 208,010,800 | Packs, indexes, reverse indexes, loose objects, and object metadata |
| Reachable history, uncompressed | 1,643,611,859 | All reachable blobs, trees, and commits from HEAD/all refs |
| Historical-only reachable content | 765,632,204 | Reachable objects outside the current HEAD tree and commit |

`git count-objects -vH` reported 1,719 loose objects, 14,365 packed objects, three packs, 59.77 MiB of loose-object accounting, and 143.23 MiB of pack data. The exact pack bytes were 149,776,979; pack indexes were 405,436 bytes and reverse indexes 57,616 bytes.

## Largest current stages and payload classes

The largest current generated stages by path-occurrence bytes are:

| Stage | Files | Occurrence bytes | Unique blob bytes |
| --- | ---: | ---: | ---: |
| `hdb2-p1` | 103 | 185,310,821 | 185,310,821 |
| `hdb2-f` | 309 | 129,520,471 | 70,804,147 |
| `sfh1` | 3,540 | 71,711,728 | 71,708,696 |
| `sfh2` | 157 | 71,549,599 | 71,549,596 |
| `sfh2r1` | 32 | 61,102,965 | 61,102,965 |

Across the C2 generated scope, the main unique-content classes are:

- semantic outputs: 272,808,133 bytes;
- deterministic projections: 126,983,180 bytes;
- HDB2-P1: 185,310,821 bytes;
- HDB2-F: 70,804,147 bytes;
- SFH1: 71,708,696 bytes;
- SFH2: 71,549,596 bytes;
- SFH2R1: 61,102,965 bytes.

These category totals overlap by design because they are classification views over paths, not additive repository partitions. The JSON contains the required top 100 unique HEAD blobs with path examples, Git blob IDs, uncompressed sizes, occurrence counts, physical sizes, stage, role, and C2 archive status.

## Exact duplicates and Git addressing

C2 supplied 284 exact duplicate groups. The audit resolved every occurrence to its Git blob SHA and found that every group already shares one Git blob object. Therefore:

- duplicate path occurrence bytes: 156,477,130;
- working-tree avoidable bytes: 84,499,177;
- actual avoidable Git blob bytes: 0;
- actual incremental Git blob cost of duplicate paths: 0.

For HDB2-F F02/F03 specifically, `rescue-search-results.json` is 7,206,140 bytes at both paths and both paths use blob `c569d4e4210ece7c098c01d8661b0f25016208e1`. Its packed representation is 418,711 bytes. The repeated path names remain in separate tree entries, but the payload is content-addressed once.

## Raw provider payloads

The current generated raw-api classification contains 6,040 paths and 28,766,609 occurrence bytes, of which 5,843 unique blobs account for 28,373,787 bytes. The narrower raw-provider dependency audit identified 114 response files totaling 2,350,786 bytes:

- 89 files / 1,661,945 bytes have direct runtime parser dependencies;
- 25 files / 688,841 bytes are path/provenance-only.

The direct consumers include current HNG2 schema-controller/live and consolidation paths, SFH1 semantic transport, and the retained SFH2 experiment runners. Raw responses must not be removed merely because a parsed output exists: some are direct replay inputs, while others are provenance-only and may be future content-addressable archive candidates. The per-tree dependency classifications and paths are recorded in the JSON.

## Pack and delta analysis

The repository has three packs totaling 149,776,979 bytes and 14,365 packed objects. There are 8,868 delta objects. `verify-pack` reports the stored delta instruction-stream size; the audit reconciles expanded object sizes with `git cat-file` so deltified blobs are not mistaken for their smaller delta instructions.

The packed object set has 1,468,064,725 bytes of expanded object content represented by 149,776,883 bytes of packed data. The largest expanded packed blobs include an 80,531,987-byte non-delta base, 80,421,489- and 80,417,988-byte delta descendants, a 53,637,599-byte historical base, and current HDB2-P1 descendants of 52,605,821, 49,928,423, 41,358,392, and 39,070,478 bytes. These large JSON payloads receive substantial delta/compression reuse; no destructive repack was performed.

## Historical cost

The current reachable object graph contains 1,335 historical-only blobs totaling 761,478,286 uncompressed bytes, plus historical-only trees and commits. The current generated-path history scan found 38 historical-only generated blobs totaling 54,841,852 bytes. The most material hotspot is HDB2-F: the current 7,206,140-byte rescue result has a 53,637,599-byte historical base retained in reachable history. This is a history-version cost, not same-HEAD duplicate blob cost.

Deleting a file from a future HEAD would remove its current tree occurrence and, if it is unique at the tip, its current-tip content from a new checkout. It would **not** remove the historical blob while an ancestor commit remains reachable. Normal clones that include history therefore receive no corresponding object-store reduction without separate history rewriting.

## Cold-archive candidates

C2 identified 1,397 current-path candidates totaling 6,108,715 occurrence bytes. Of these, 5,857,295 bytes are unique current-tip content that would disappear from the checked-out HEAD if the candidates were removed and not duplicated elsewhere. The current audit estimates zero Git-object or normal full-clone reduction without history rewriting because the blobs remain reachable through existing commits.

The candidates are not automatically safe to archive. Direct semantic inputs, human review authority, frozen selections, and reproducibility manifests remain protected until a descriptor can restore and verify them. A future archive descriptor should carry stage/run identity, every original path, SHA256, byte size, and a content-addressed archive checksum. C2.1 proposes this boundary but implements no descriptor or migration.

## C3 decision matrix

| Strategy | Working-tree effect | Git object effect without history rewrite | Complexity / risk | Assessment |
| --- | --- | --- | --- | --- |
| A — do nothing | none | none | minimal / minimal | Correct for exact duplicates because Git already stores one blob. |
| B — descriptor/content-addressed payload layer | up to 84,499,177 theoretical duplicate-path bytes | 0 | medium / medium-high validator and reproducibility risk | Not justified solely by repeated paths. |
| C — cold archive unique payloads | up to 6,108,715 candidate bytes, with 5,857,295 unique-content bytes | 0 for ordinary clones with history | medium-high / high until verified | Appropriate as a small, descriptor-first C3 pilot. |

Strategy C is the recommended future boundary only for carefully selected unique diagnostic/replay payloads. Keep semantic inputs, human-reviewed authority, frozen selections, active HNG/HDB frontiers, SFH1/SFH2 inputs and results, and SRM evidence in HEAD until each consumer has an independently verified archive/retrieval contract. Strategy A remains the recommendation for the exact duplicate families.

## History rewrite is separate

The 761,478,286 bytes of historical-only blob content are large enough to justify evaluating a separate destructive history-reduction milestone. C2.1 did not run `filter-repo`, prune, or repack. A rewrite would invalidate commit SHAs, rewrite tags and branches, break compatibility with external clones/forks, risk provenance references to frozen commits, and require a reproducibility migration for every historical baseline. It must not be conflated with a current HEAD archive migration.

## Protection and validation

Only this report and its JSON companion are intended to change. No builder was run. The protected SC1 SHA256 remains:

```text
cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8
```

The audit records observed hashes for WP1, canonical people/aliases, reviewed semantic authority, and test-contract artifacts. C2.1 performs no changes to those files or to HNG/HDB/HGE/SFH/SRM payloads. `git diff --check` and the focused current test-contract tests are the required low-risk validation; the portable current suite remains subject to the repository's pre-existing optional-dependency limitations and is not repaired by this audit.
