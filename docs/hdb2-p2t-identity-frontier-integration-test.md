# HDB2-P2T — Identity Frontier Production Integration Test

P2T is a candidate-only integration test over the frozen HNG2, HDB1,
HDB2-P1, and HDB2-P1.1 outputs.  It does not change extraction, retrieval,
the Person catalogue, canonical facts, or the identity algorithm.

## Frozen cascade

Each concrete HDB1 identity observation is kept as its own occurrence:

```text
occurrence
  → semantic type
  → Python explicit resolution
  → Python structural interpretation
  → one P1.1 contextual LLM call only when ≥2 candidates remain
  → Python hard validation
  → candidate occurrence decision
```

Exact visible full-name and identity evidence can resolve without a model
call.  Compositional kinship, generic/non-person references, and unique
ruler/office structures are handled structurally.  The strict P1.1 function
schema is used unchanged for residual ambiguity.  A literal string `null` is
invalid as a non-candidate `candidate_key`; it is never coerced.

Surface equality is only a lookup/statistics aid.  It cannot merge occurrence
identities.  P1.1 decisions may contribute evidence only when tied to the
same Story context; they are not propagated by surface.

## Candidate projections

After independent occurrence decisions, P2T deterministically projects:

- newly endpoint-complete HDB1 relation candidates;
- candidate-only PersonKnowledgeDelta records for safely resolved existing
  Persons;
- a review queue for unresolved, preferred, or conflicting occurrences.

No production Person ID is allocated and no candidate is promoted to reviewed
or canonical status.  H0A/H0B facts remain read-only constraints.

## Outputs

The frozen selection is
`data/annotation/hdb2-p2t-occurrence-selection.json`.  The context projection
is `data/derived/hdb2-p2t-occurrence-cases.json`.  Live artifacts are under
`data/generated/hdb2-p2t/live/<run_id>/`; derived knowledge and unblocked-fact
projections are written under `data/derived/`.
