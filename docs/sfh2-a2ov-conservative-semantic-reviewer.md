# SFH2.2-A2OV — Conservative Occurrence Semantic Reviewer

A2OV tests a narrow, primary-aware semantic reviewer over the immutable 26-case
A2OR occurrence cohort. It does not rerun the A2OR historian, reopen identity,
or introduce an adjudicator.

The reviewer sees the exact pinned occurrence, source evidence, structural
`provenance_layer`, frozen identity context, clarified taxonomy, and the A2OR
primary hypothesis. It may confirm that hypothesis, abstain, or revise only
`narrative_function`. It cannot emit identity, provenance, legacy-role,
relation, candidate, or production fields.

This is deliberately not an independent blind Historian B experiment:
`reviewer_is_primary_aware` is true. The reviewer has a higher burden for
revision because A2OR already supplies a mostly-correct primary hypothesis.
Python validates the closed contract, copies the primary result for confirm or
abstain, applies only the declared function revision, and reuses the generic
compatibility projection. It performs no lexical or surface-specific semantic
inference and writes no canonical data.

The live run consists of one strict contract probe followed by the 26 reviewer
calls using `deepseek-v4-flash`, temperature `0`, and disabled thinking. Raw
provider envelopes remain outside Git; compact accounting and bounded errors
are committed with the stage outputs. Gold and residual-error labels are loaded
only after inference for offline evaluation.

The stage is qualified only by reviewer value, not by aggregate accuracy alone:
at least one A2OR error must be recovered, no previously correct case may be
damaged, all records must be valid, provenance and identity must be preserved,
and the six reviewed role cases must remain correct. The resulting
recommendation is evidence for a future production decision, not a claim of
100% historical accuracy.
