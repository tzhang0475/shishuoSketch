# SFH2.2-A2OVB — Blind Participant/Reference Boundary Validator

## Purpose

A2OR is the frozen general occurrence-semantic historian and A2OV is the
frozen primary-aware reviewer. Both leave two reviewed errors in the same
boundary family: a comparison/reference occurrence is over-called as an event
participant. A2OVB tests whether a narrowly framed, same-model judgment can
detect that boundary without being shown the general historian's answer.

This is a pilot, not a new identity pipeline and not a second full historian.
It does not change the frozen identity, source provenance, Gold, or legacy
compatibility projection.

## Inputs and blindness

The 26-case cohort is the exact A2OR cohort. Python routes the 15 cases whose
cached A2OR function is `participant` or `reference`; this is routing from an
already-declared structured output, not semantic inference from Chinese text.
The other 11 cases are copied from the A2OR result unchanged.

The boundary provider packet contains the pinned occurrence, source evidence,
structural provenance, frozen identity/semantic kind, and generic task
definitions. It does not contain the A2OR function, confidence, explanation,
A2OV review, Gold, residual-error labels, or correctness information. The
validator is therefore primary-blind, Gold-blind, and residual-error-blind.

The provider output is restricted to:

```json
{
  "case_id": "...",
  "boundary_judgment": "event_participant | referential_only | uncertain",
  "confidence": "low | medium | high",
  "supporting_evidence_ids": [],
  "reason_summary": "..."
}
```

`event_participant` maps to `participant`, `referential_only` maps to
`reference`, and `uncertain` preserves the A2OR function. The mapping and the
legacy-role projection are deterministic structural mechanics; Python does
not decide historical meaning.

## Experimental interpretation

A2OVB differs from A2OV in one causal respect: it is a specialized boundary
task and is blind to the prior function. It uses the same `deepseek-v4-flash`
model, temperature zero, and disabled thinking configuration. It is not
independent Historian B evidence. If the same-model blind validator cannot
recover the residual boundary, a future A2OVX cross-model experiment is the
appropriate next test. A2OVB does not add an adjudicator.

All live transport records are compact accounting metadata; raw provider
responses remain external under the generated-artifact lifecycle policy.
The run uses one strict schema probe and one call per routed boundary case,
with at most one retry only for a transient transport failure. HTTP 400 is not
retryable.

## Safety and reproducibility

The stage is candidate-only:

- no Person creation, canonical write, alias/profile mutation, or identity replacement;
- no retrieval-candidate gate, substring identity, or surface-specific rule;
- provenance is copied from evidence metadata;
- non-boundary and uncertain final semantics are exact copies of A2OR;
- a boundary override can change only `narrative_function`.

Gold is loaded only after provider inference for evaluation. Two offline
replays derive results from the cached boundary responses and must make zero
provider calls with byte-identical derived semantic artifacts. Existing A2O,
A2OT, A2OR, A2OS, A2OSP, and A2OV outputs remain immutable.

The pilot recommendation is determined from computed recovery and damage:
both residuals recovered with no harmful override supports qualification; one
recovery with no damage is promising; no recovery with no damage indicates a
same-model boundary limitation; any harmful override indicates reviewer
damage. No result authorizes the 188-Story run by itself.
