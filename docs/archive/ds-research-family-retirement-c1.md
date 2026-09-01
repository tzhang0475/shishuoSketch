# C1 — DS research family retirement

## Scope

C1 retires the obsolete DS1 → DS1.2 → DS1.2R → DS2 local-evidence
research family from the active repository contract. The family investigated
whether a bounded historical context packet, local evidence retrieval, and
deduplicating retrieval policy could improve cautious Story-level semantic
context candidates. The final DS2 stage extended that experiment to seven
Stories.

These stages produced non-canonical research candidates only. They never
owned canonical Persons, Relations, Gold annotations, frontend source data,
or production historical facts. Retirement therefore removes obsolete
execution and validation dependencies without invalidating the historical
experiment results.

## Dependency boundary

The final historical chain was:

```
DS1 fixed context
  → DS1.2 bounded local-evidence retrieval
  → DS1.2R deduplicating retrieval/identity hardening
  → DS2 seven-Story context generalization
```

The generated DS1/DS1.2/DS1.2R/DS2 trees, their stage-only runners,
validators, schemas, and tests are retired. The shared `scripts/ds1_common.py`
module is retained unchanged because SRM0.5 freezes and imports its generic
filesystem/serialization helper contract. The separate DS2.1A derived
Person-research surface remains active because HNG/HDB/HGE/SRM paths consume
it; it is not the retired data/generated/ds2/ pilot.

The site retains its existing optional DS1 preview loader/rendering as a
404-safe compatibility path. There was no committed public preview at
retirement, so the obsolete preview producer was removed from build:site
and the current build no longer consumes retired DS input.

## Provenance

All retired bytes remain recoverable from Git history. The pre-deletion
hashes, deterministic stage tree hashes, source commits, associated paths,
and dependency proof are recorded in:

data/retired/ds-research-family-c1.json

The retirement baseline is
c16aedd5845f172160752091fcef924079d34d2e. The family originated in
3325a2d52d02e390dd6cc73569d4704ea656cd61; the two validator files also
received a later SFH2R compatibility update in
e176342e7bd1f3dd9d04a6733361cee0abb4b719.

The blank/pending review records are preserved unchanged under
data/annotation/archive/ds/. Historical design documents are preserved
under docs/archive/ds/. Git history remains the byte-level archive for
generated outputs, code, schemas, and tests; no large generated copies were
created.

The generated stage trees were classified as machine-only experiment state.
The DS1 pending review record and the blank DS2 pilot review record were
classified as human-review provenance and archived unchanged. No DS annotation
has an external active consumer.

## Current test contract

C1 adds registry-driven suite commands:

- npm test and npm run test:current: current required contract.
- npm run test:historical: opt-in frozen/experiment reproducibility.
- npm run test:source: opt-in source-payload checks.
- npm run test:network: explicit live/network experiments.

The C0 classification remains the before-state. The C1 registry removes only
the four retired DS test modules; the active test_ds2_1a.py remains because
it validates the separate DS2.1A surface.

## Follow-up

C1 does not retire any HNG, HDB, HGE, SFH, SRM, SC1, WP1, canonical, Gold, or
reviewed semantic artifact. A future cleanup may revisit the dormant DS1
preview compatibility path only after a separate product decision and review
of its external consumers.
