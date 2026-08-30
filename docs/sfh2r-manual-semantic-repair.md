# SFH2R — Manual Semantic Repair

SFH2R is a bounded repair/replay stage for the SFH2 candidate projection. It
does not rerun the 188-Story semantic pipeline and it does not write
canonical history. The reviewed file
`data/annotation/sfh2r-manual-semantic-authority.json` is the semantic
authority for this repair set. Historical semantics were reviewed by a human;
Python only locates the named records, applies them mechanically, validates
provenance, and rebuilds candidate-only indexes.

## Why the repair was necessary

The earlier pipeline treated an observed surface as if it were a global alias.
That allowed a source-local reading, a comparison participant, or a title/
attribute fragment to leak into an unrelated Person profile. Examples included
the shared courtesy forms `景真`, `敬祖`, `萬年`, `無忌`, `安國`, `大業`, `世將`,
and `子相`, as well as the bad `子少` extraction for 郭象. The repair keeps
source evidence and old snapshots for audit, but filters the explicitly
rejected rows from the active alias/profile projections.

The invariant is:

> Occurrence(surface S) → Person P does not imply Alias(P, S).

Only `exact` forms can be used as a global exact retrieval key. Shared forms
are retained with `contextual` or `shared_or_contextual` behavior. A profile
form must carry its exact occurrence, identity observation, evidence reference,
status, and identity basis.

## Materialized repairs

The active `data/aliases.json` preserves alias IDs and raw witness snippets.
The ten reviewed alias records are marked with an `sfh2r_manual_repair` trace;
only the evidence IDs named by the authority are removed or retained. The
`子少` row is replaced by `子玄` while its source snippet remains unchanged;
the corrected reading is a derived semantic repair, not a raw-source rewrite.

Eight occurrence repairs are represented in the isolated
`data/generated/sfh2r/` projection. They suppress `齡`, `閔氏`, and `字景真`
as independent people; replace the `亮`, `勒`, and `興公` readings with
candidate-only historical entities; and classify the two 管仲/管夷吾
occurrences as `historical_exemplum`, excluded from the core Story social
graph. `石勒`, `孫綽`, and `桓亮` use stable `sfh2r-manual-candidate-*` IDs;
no `person-NNN` is allocated.

## Semantic precedence

For future stages the authority order is:

1. reviewed human semantic decision;
2. validated LLM semantic judgment;
3. soft collective consistency;
4. deterministic retrieval hint.

Python constraints may veto an unsafe storage operation, but lexical or
nearest-neighbor heuristics may not overturn reviewed semantic meaning. A
missing production registry entry results in a candidate historical entity,
not a fallback to an unrelated Person.

## Validation and offline replay

`scripts/validate_sfh2r.py` checks the authority schema, active alias evidence,
profile provenance, candidate namespaces, rejected associations, safe W4
aliases, HDA2 suppression non-reentry, old SFH2 hashes, and canonical hashes.
`data/generated/sfh2r/regression-results.json` contains the mechanical targeted
bundle (32/32, including the 14 safe W4 aliases). The offline replay is a
mechanical overlay over the existing SFH2 observations: 3,303 observations in
the 188-Story packet universe, with no model calls. The old SFH2 graph and
relation projection are intentionally not rewritten; role exclusions and
candidate additions are recorded as an isolated reprojection audit.

The current repair audit removed 41 explicitly rejected alias-evidence rows
and seven additional rows while replacing the corrupt `子少` record with its
reviewed `子玄` evidence (48 rows removed from the ten repaired records in
total), retained 23 reviewed evidence rows, removed four active profile forms,
and reused three candidate historical entities. It made zero canonical writes
and used zero LLM calls. These figures describe contamination removal, not a
new historical completeness or network-saturation measurement.

## Remaining risks

This authority covers the reviewed high-propagation W4/SFH2 failures only.
Unreviewed short forms and unresolved occurrences remain unresolved or governed
by their prior candidate state. The old SFH1/SFH2 artifacts remain immutable
provenance witnesses and must not be treated as higher-priority semantic truth
than this reviewed overlay. A future stage should use a small additional human
contamination audit or identity consolidation before any canonical materializa-
tion; SFH2R itself does not perform that next stage.

## Frozen-input compatibility

The active alias/profile rebuild necessarily changes derived inputs recorded
by the completed SFH2 and HDA2 experiments. `repair-manifest.json` contains
one explicit byte-level pre/post transition for those five active inputs.
The older validators accept that transition only when the current bytes equal
the recorded post-repair bytes; any later unrecorded change still fails.
Canonical and H0A/H0B hashes are not covered by this exception and remain
hash-frozen. No prior semantic API response or experiment output is rewritten.
