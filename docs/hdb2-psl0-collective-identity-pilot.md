# HDB2-PSL0 — Collective Identity Resolution Pilot

PSL0 is an isolated, candidate-only experiment over the frozen 24-occurrence
HDB2-LJ0 selection.  It does not change HDB2/LJ0 decisions, canonical data,
Person IDs, or reviewed facts.

## Algorithm

Python reuses the frozen LJ0 occurrence cases and applies the existing hard
exclusions before constructing a small sparse graph.  The graph contains
mention nodes, candidate nodes, and these predicates:

```text
AliasMatch(M,P)
TimeCompatible(M,P)
Coreference(M1,M2)
SameStory(M1,M2)
KnownRelation(P1,P2)
OfficeCompatible(M,P)
KinshipCompatible(M,P)
ContextCompatible(M,P)
CrossStoryCompatible(M,P)
```

`Coreference`, `ContextCompatible`, and `CrossStoryCompatible` are the only
model-owned predicates.  DeepSeek receives local candidate keys and supplied
evidence IDs only; it never selects the final identity or sees production
Person IDs.  Python validates every predicate and runs four fixed-weight
collective iterations.  Links are normalized to `[0, 1]`, and hard Python
vetoes are applied before inference.

No-ID candidates are occurrence-local.  Equal surfaces are never an identity
merge.  Existing Persons and reviewed H0A ruler registry entries may share a
graph node because their identity is supplied by existing structured data,
not inferred from surface equality.

## Outputs

The frozen selection is recorded in
`data/annotation/hdb2-psl0-selection.json`.  Live and replay artifacts are
written under `data/generated/hdb2-psl0/live/`.  `decisions.json`,
`comparison.json`, `metrics.json`, and the diagnostic for
`05-fangzheng-011` are candidate-only outputs.

`--replay RUN_DIR` revalidates the saved strict predicate payloads and reruns
the complete graph inference without an API call.

## Interpretation

`high_confidence_collective` is an experimental thresholded link result, not
historical truth and not a probability.  `collective_gain` counts only cases
that were unresolved by LJ0, resolved by PSL0, and whose top link received a
collective predicate contribution.  No human gold labels are available in
this pilot, so false-unresolved ground truth is not estimated.  The output is
for review/prioritization analysis only.

## Frozen live run

Run `20260827T-HDB2-PSL0-04` used the same 24 LJ0 cases and made 23
predicate calls (one case had no requested predicate).  All 23 responses were
parsed and validated; there were no retries, provider failures, truncations,
or validation failures.  The result states were 11
`high_confidence_collective`, 8 `review_required`, 4
`genuinely_unresolved`, and 1 `structural_reference`.  Compared with LJ0's
4 resolved and 20 review cases, PSL0 produced 11 resolved and 13 review cases,
including 4 collective-gain candidates.  This is an experiment result, not an
automatic review removal decision.

The `05-fangzheng-011` diagnostic connects the supplied `帝`/`武帝` pair to
the shared existing H0A ruler node `ruler-jin-wudi`; its registry forms include
`晉武帝` and `司馬炎`.  `和嶠` remains contextual evidence and `王濟` is not
invented as a candidate because it is not supplied by the frozen packet.
Safety diagnostics were all zero: no surface-only merge, compositional
collapse, non-person Person ID, hard-veto promotion, invalid candidate key, or
invalid evidence reference.  No human truth labels were available to claim a
measured false-resolution rate.
