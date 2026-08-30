# SFH2.2-P2 — Blind Generalization Pilot

## Purpose

SFH2.2-P2 is an evaluation-only blind run of the frozen SFH2.2-P proposal-first architecture. It tests whether the same semantic proposal and identity-equivalence contracts generalize from previously reviewed cases to unseen occurrence-level cases. It does not modify the production historical database, add Stories, or score the model against a self-generated gold answer.

The authority boundary remains:

```text
reviewed human semantics > LLM proposal/equivalence > soft consistency > Python retrieval hints
```

Python validates schemas and evidence, performs registry lookup and candidate-ID allocation, and applies storage/safety gates. All outputs are candidate-only with `canonical_write_back=false`.

## Frozen design

- Baseline: `6237d9eafe44a29daab7dfcfb7256a1b39094871`
- Model: `deepseek-v4-flash`
- Temperature: `0`
- Thinking: disabled
- Proposal prompt/schema: the unchanged SFH2.2-P contracts (`sfh2-2p1-entity-proposal-v3`)
- Equivalence prompt/schema: the unchanged SFH2.2-P contracts (`sfh2-2p1-identity-equivalence-v1`)
- Seed: `sfh2-2p2-blind-v1`
- Selection hash: `d91589eada9018dcd8f1fbf70ab587549a3b07d41219dea7f385de7850f35c3b`
- Cases: 24 occurrence-level cases in 24 Stories
- Eligible pool: 723 validated mentions; 2,580 excluded by the recorded prior-case/story/surface filters

The selection is stored in `data/annotation/sfh2-2p2-selection.json`. It contains no expected identity, gold label, or evaluation answer. The separate `eligibility-audit.json` records the deterministic pool and selection basis and explicitly records that answers were not inspected.

Stratification is fixed at four cases each for direct/full personal, courtesy/style/nickname, and office/title/ruler references; three each for short/abbreviated and coreference/pronoun references; and two each for annotation-biographical, historical-exemplum/citation, and structural/non-Person controls.

## Execution and outputs

The run uses one proposal call for each selected case. Equivalence is called only for historical-person proposals with realized candidates. The authoritative raw responses are preserved under `data/generated/sfh2-2p2/live/sfh2-2p2-live-v1/raw-api/`; the cache index and transport manifest retain packet hashes, model, prompt version, usage, latency, and classification.

Generated artifacts include:

- frozen selection, eligibility, input-manifest, and architecture-freeze records;
- source-grounded case packets;
- validated entity proposals and candidate realization;
- equivalence judgments and final candidate-only decisions;
- automatic safety and internal-consistency audits;
- network-role audit;
- a JSON and Markdown human-review bundle;
- pre-review metrics, transport, validation summary, and recommendation.

The human-review bundle deliberately contains no expected answer or automatic correctness label. Historical correctness is `pending_external_review`; the tested pipeline does not ask the same model to grade itself.

## Structural results

The run produced 22 historical-person proposals and two collective-reference controls. There were 23 high-confidence and one low-confidence proposal. Eight proposals realized against existing production Persons and 14 realized as deterministic candidate-only historical entities. The 22 historical proposals received 22 equivalence reviews, with 46 `same_person`, 93 `different_person`, seven `related_person`, six `kinship_relation`, one `attribute_of`, and one `citation_relation` assessment across the supplied alternatives.

Final storage states were 8 `stable_entity_resolved`, 14 `local_candidate_resolved`, and two `structural_reference`. No historical accuracy conclusion is drawn from these states before external review.

The automatic safety audit recorded zero production Person creations, canonical fact writes, alias writes, profile mutations, occurrence-derived aliases, substring-derived candidates, related-person promotions, attribute-as-Person promotions, and internal semantic-contract errors. Four cases were explicitly excluded from core graph eligibility because their validated role was citation or collective-reference; this pilot does not perform graph-growth analysis.

## Provider accounting

The live run used 46 new calls: 24 entity-proposal calls and 22 equivalence calls. It had no retries, provider failures, invalid payloads, or truncations. Usage was 137,858 prompt tokens, 23,705 completion tokens, and 161,563 total tokens. Median latency was 2.969 seconds and maximum latency was 7.426 seconds. The run stayed below the 60-call total budget and the 26-call per-stage limits.

Two later offline cache replays were byte-stable across the deterministic root artifacts. They used the immutable live responses and did not add provider calls.

## Review workflow and limitations

Review `data/generated/sfh2-2p2/human-review.json` or `human-review.md` externally, beginning with the 23 high-confidence proposals. Reviewers should assess historical referent correctness, person/non-person classification, and whether equivalence judgments confuse `related_person` or other relations with identity. The pilot intentionally provides no automatic accuracy metric until that external adjudication is complete.

This is a small, stratified sample rather than a corpus-wide estimate. It excludes known repair and regression cases, so it cannot establish performance on those hand-tuned forms. It also does not evaluate graph saturation, Story expansion, or canonical migration. The preliminary recommendation is therefore `sfh2_2p2_pending_external_review`, not readiness for a production migration.
