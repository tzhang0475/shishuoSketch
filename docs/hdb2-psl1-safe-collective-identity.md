# HDB2-PSL1 — Safe Collective Identity Resolution

PSL1 is an isolated candidate-only experiment over the frozen HDB2-LJ0
regression selection and a separate deterministic holdout.  It does not alter
HDB2 decisions, canonical data, or the extraction pipeline.

## Identity predicates

The PSL1 graph replaces PSL0's broad contextual compatibility edges with
identity-specific predicates:

- `AliasMatch`, `IdentityContextSupport`, and `CrossStoryIdentitySupport` are
  positive identity evidence only when the supplied evidence specifically
  links the occurrence to the candidate.
- `IdentityContradiction` is negative evidence.  A grounded strong
  contradiction can veto a candidate.
- `Distinct` is a pair-level hard veto when local syntax explicitly names two
  mentions separately.
- `TimeCompatible` and `SameStory` remain context diagnostics.  Neither can
  establish identity by itself.

Coreference is canonicalized as one unordered mention-pair variable.  A
contradictory duplicate orientation is rejected instead of becoming
asymmetric graph pressure.

## Pipeline

```text
frozen occurrence cases
  → Python candidate graph and hard vetoes
  → one strict predicate function call per useful occurrence
  → fixed-weight collective inference
  → Python threshold and provenance checks
  → adversarial strict reviewer for residual review_required cases
  → candidate-only result
```

The reviewer can retain review or reject a leading candidate.  A reviewer
confidence value never performs a state transition by itself; accepted
evidence must reference the supplied packet, and Python still checks the
candidate key and hard conflicts.

The `02-yanyu-054` regression is intentionally explicit: the source lists
`王長史、劉尹` as separate mentions.  When the grounded identity support for
`劉尹 → 劉惔` is present, `Distinct` preserves that supported side and vetoes
the shared `劉惔` candidate for `王長史`; without a supported side it vetoes
both rather than choosing by surface order.

## Selection and artifacts

`data/annotation/hdb2-psl1-selection.json` freezes the 24 PSL0 regression
occurrences and 20 holdout occurrences.  The holdout is selected from the
current review frontier while excluding every regression occurrence.

`scripts/run_hdb2_psl1.py` creates immutable raw response artifacts under
`data/generated/hdb2-psl1/live/<run-id>/`.  Its `--replay` mode revalidates
those responses and reruns inference without an API call.  The experiment is
candidate-only and `canonical_write_back` is always false.
