# SFH2.2-A2OT — Narrative Function Taxonomy Audit

SFH2.2-A2OT is an offline audit of the frozen SFH2.2-A2O occurrence-function
pilot. It reads the 26 frozen Gold records, source packets, and A2O results;
it makes no provider calls and does not modify Gold or any A2O artifact.

## Scope and authority

The target occurrence is the unit of review. `provenance_layer` remains a
structural property copied from the target source evidence. `narrative_function`
is the semantic label whose meaning is clarified here. Python performs only
structured comparison and report generation; it does not infer a historical
answer from a surface string.

The pilot functions are:

- `participant`: the referent actively participates in the narrated event,
  unless a more specific function applies.
- `reference`: a generic entity reference without a more specific function.
- `speaker`: the target identifies the speaker of the current utterance or
  the speaker's self-reference.
- `addressee`: the target identifies the directly addressed recipient,
  including direct address or vocative use. An object of `召`, `諫`, or another
  interaction verb is not automatically an addressee.
- `citation_source`: the target itself identifies the source, author, or work
  introducing cited material. An entity inside quoted source content is not
  thereby the source.
- `historical_exemplum`: a historical person or entity invoked as comparison,
  precedent, example, or explanatory background.
- `person_attribute`: the target itself expresses an attribute or value of a
  bearer, rather than merely being a person described by a predicate.
- `collective_reference`: the target denotes a collective entity.
- `genealogy_reference`, `structural`, `other`, and `uncertain` cover their
  correspondingly narrow cases and fallbacks.

The review guidance prefers the most occurrence-specific function in this
order: special semantic form, source/exemplum, discourse, event participant,
generic reference, then fallback. This is semantic guidance for LLM/human
review, not executable Chinese lexical logic.

## Audit result

All 26 A2O Gold cases were inspected with exact target offsets, target source
evidence, nearby evidence, current Gold fields, and the frozen A2O
interpretation. Twenty-five cases are consistent with the clarified
occurrence-centric taxonomy. One case is emitted for human Gold review:

`02-yanyu-060 / 宣武` is the first occurrence in `簡文在暗室中坐召宣武...`,
at zero-based offsets 8–10. The current Gold calls it `addressee`, while the
clarified direct-address definition supports `participant` for the person who
is summoned and then arrives. A2OT does not change Gold; it records the
proposed function and legacy-role correction as a review candidate.

## Five explicit A2O mismatches

1. `齊桓公` — model source-scope error. The occurrence is content in the
   historical material quoted from 史記, not the citation source itself.
   Current Gold is retained as `historical_exemplum`.
2. `宣武` — Gold/taxonomy boundary candidate. Human review is required before
   changing `addressee` to `participant` and `addressee_reference` to
   `scene_participant`.
3. Liu-annotation `帝` — model discourse-role error. It is the object of
   `諫` in an annotation narrative, not automatically a direct addressee.
4. `顧` in `顧曰...` — model discourse-role error. The target identifies the
   speaker of the following utterance.
5. Liu-annotation `顗` — model target/attribute confusion. The predicate
   describes 顗; the person occurrence itself is a reference, not an
   attribute expression.

No additional latent Gold inconsistency was found by the structured pattern
audit. The same `liu_annotation + annotation_person` compatibility role can
legitimately project both participant and reference functions; this is an
expected many-to-one compatibility projection, not a taxonomy contradiction.

## Metrics and next step

The frozen A2O score is 21/26 (80.77%). If the single proposed `宣武` Gold
correction is later approved by a human reviewer, the counterfactual is 22/26
(84.62%). The proposal is not promoted by this stage, and the original
model-quality conclusion remains numerically below the 90% pilot target.

The resulting recommendation is `sfh2_occurrence_gold_review_required` with
next stage `SFH2.2-A2OR`: human Gold promotion first, followed by a rerun of
the same 26-case cohort using the clarified taxonomy. No Historian B,
adjudicator, provider call, canonical write, or production run is part of
A2OT.

Machine-readable details are in `data/generated/sfh2-a2ot/`, especially
`gold-taxonomy-audit.json`, `gold-review-candidates.json`,
`function-consistency-matrix.json`, `five-error-review.json`, and `metrics.json`.
