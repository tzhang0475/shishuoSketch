# HNG2-V1 — Frozen Algorithm Fresh Holdout Validation

## Scope

This validation keeps the HNG2-C.3 algorithm frozen. The only pre-validation
changes are additive provenance/reporting boundaries:

- identity results now carry `identity_resolution_basis`; contextual name
  projection is distinct from direct evidence identity;
- temporal metrics declare the scanner scope as `H0A historical registry +
  explicit date patterns`;
- H0A disagreements are split into scene-affecting conflicts and harmless
  non-scene role disagreements.

Exact evidence grounding, H0A projection, identity propagation, and all
canonical-write protections remain fail-closed and unchanged.

## Frozen algorithm

Person:

```text
SELECT → READ EVIDENCE ATOMS → GROUND → FILL → RESOLVE/NORMALIZE → CANDIDATE DB
```

Temporal:

```text
SELECT → VISIBLE ANCHOR SCAN → READ TEMPORAL ATOMS → GROUND → FILL
→ H0A NORMALIZATION → CANDIDATE DB
```

The holdout performs one Person READ/FILL pair and one Temporal READ/FILL pair
per Story. There is no SearchPlan, ResearchGap loop, follow-up retrieval,
frontier expansion, or recursive repair.

## Fresh selection

Selection was frozen before the authenticated preflight. It contains 24
Stories with four Stories in each of the six deterministic temporal strata:

`explicit_year_reign`, `ruler_or_event_bounded`, `annotation_dependent`,
`quoted_precedent_background`, `later_outcome`, and
`weak_or_no_explicit_temporal_evidence`.

The exclusion snapshot found 54 Story IDs from prior HNG2 artifacts, tests,
docs, and scripts. The persisted overlap is `[]`; the selection hash is
`d7483a8f2698e6ce6da586d1b5aeff835adb35c966245510ca165ba0ca635b66`.

## Live result

The run used `deepseek-v4-flash`, temperature 0, and the frozen C.3 prompts.
It completed 96 semantic calls plus one authenticated preflight, with no
retries, provider failures, parse failures, or truncations. Prompt tokens:
133,476; completion tokens: 36,498; total semantic tokens: 169,974. Median
latency was 3.052 seconds and maximum latency was 10.126 seconds.

All hard safety gates passed:

- no wrong known-reference resolution, false identity promotion, non-person
  Person-ID leak, or collapsed non-identity self-relation;
- no unsupported relation promotion or false temporal scene promotion;
- exact provenance validation remained fail-closed;
- no prior-HNG2 overlap and no canonical write-back.

The scanner reported 46 visible surfaces and considered 36 by T1. Its scoped
recall misses are zero **within the declared lexical scope**. Eight H0A
evidence surfaces (`薨`, `崩`, `渡江`, `遇害`, `作亂`) are outside that scope
and remain reported as scope gaps rather than being added to the scanner.

## Interpretation

The holdout is a safety/generalization validation, not a tuning result.
Known-reference resolution was correct for 20 cases and unresolved for 2;
14 candidate-only new-person projections and 48 valid relation candidates
were produced. Temporal normalization yielded 16 H0A-compatible assertions,
zero scene-affecting conflicts, two non-scene role disagreements, seven
later-outcome exclusions, and four quoted/background exclusions.

The frozen algorithm passes the fresh-holdout safety validation. The remaining
out-of-scope temporal expressions are coverage limitations for future H0A
database work, not reasons to alter this algorithm run.
