# SFH2.2-A2OS — Target Alignment & Residual Gold Audit

This is an offline audit of the frozen 26-case A2O/A2OR occurrence cohort. It
uses no provider calls and does not change A2O, A2OT, A2OR, the active Gold,
or the frozen identity result.

## Audit unit

The semantic unit is the exact occurrence key:

```text
(case_id, story_id, mention_id, source_evidence_id,
 source_start, source_end, surface)
```

The audit validates the key against the frozen source packet and the SFH1
validated-mention ledger. Source offsets are zero-based and end-exclusive.
Gold's `semantic_basis` is retained as evidence for human review; it is never
used to resolve a target, choose an identity, or replace a model result.

All 26 spans validate. The exact tuple `(story_id, source_evidence_id,
surface)` is unique for every selected validated mention. A broader collision
audit finds 10 cases with repeated source-text surfaces or overlapping nested
validated spans. These are reported as structural warning signals, not
semantic decisions.

## Selection-intent finding

The historical challenge selector in
`scripts/sfh2_a0r_l/selection.py` matches on `story_id`, `surface`, and
`source_evidence_id`, then sorts matching mentions. It does not pin a
semantic target by `mention_id` and offsets.

There is one confirmed misalignment:

```text
case: sfh2-a0r-l-challenge-f245371d8f0cdf9c8773
story: 21-qiaoyi-011
surface: 顧
pinned target: source_start=0, source_end=1, 顧 in 顧長康...
Gold basis: the later 顧曰 occurrence
```

The later same-surface text occurrence is at offsets 22–23, while the
validated `顧` mention is the opening offset 0–1 occurrence. This is a
`target_gold_alignment_error`, not an A2OR model failure. The prospective
selection rule is to require `mention_id` plus evidence ID and exact offsets,
with Python enforcing only occurrence identity.

## Gold review candidates

No Gold is changed in A2OS. Two human-review candidates are emitted:

1. `顧`: `speaker/speaker_reference` → `participant/scene_participant`, because
   the selected opening occurrence is part of the narrator-framed event and
   does not identify the later speech-introducing occurrence.
2. `齊桓公`: `historical_exemplum/historical_exemplum` →
   `reference/annotation_person`, because the target is an entity mentioned
   inside the `史記` material explaining the invoked historical example; it is
   not automatically the occurrence that performs the exemplum function.

Both proposals are high-confidence audit hypotheses only and carry
`human_review_required=true`.

## Residual model errors

The exact-aligned `康伯` and `文度` cases remain model-error candidates:
their Gold bases describe the selected comparison references, while A2OR
overextended `reference` to `participant`. They are classified as
`reference_to_participant_overreach`, not as selection or Gold defects.

## Counterfactuals

Against the active, unchanged Gold, A2OR is 22/26. Applying only the `顧`
proposal would yield 23/26; applying only the `齊桓公` proposal would also
yield 23/26. Applying both audit proposals yields 24/26, with 6/6 reviewed
role cases and 18/20 challenge cases. These are evaluation-only
counterfactuals; no historical output or Gold bytes are rewritten.

Therefore the prior diagnosis of model quality insufficiency does not survive
unchanged: two apparent errors require target/taxonomy review first. Two
genuine model-error candidates remain. The recommended next step is
`sfh2_occurrence_gold_alignment_review_required`, followed by a corrected
A2OR rerun only after human decisions are promoted.

No reviewer/live stage or 188-Story run is started here.
