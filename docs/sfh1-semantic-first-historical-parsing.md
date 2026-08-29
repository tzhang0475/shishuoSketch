# SFH1 — Semantic-First Historical Parsing

## Decision boundary

SFH1 adopts one project-wide authority rule:

> Semantic Authority belongs to the LLM. Deterministic Authority belongs to Python.

The model reads historical and classical-Chinese meaning. Python prepares immutable source packets, checks exact quotations and offsets, owns candidate IDs, applies hard constraints, runs the frozen collective model, controls provenance, and is the only storage gate. Model output cannot allocate a production Person ID or write canonical history.

SFH1 is a parallel candidate-only projection. It does not replace HNG2, HDB2, HDA2, HGE1 Wave A/B, or any canonical artifact. Every generated record carries `candidate_only=true` and `canonical_write_back=false`.

## Why the old path failed

Wave B exposed a category error in the old target builder: string-oriented selection logic was asked to make semantic decisions. That produced targets such as `謝萬在兄前欲起索`, `簡文在暗室`, `顧長康畫裴叔則頰`, and `弓為太丘`. Suffix and nearest-person rules also confused lexical forms, kinship, holders, patrons, and co-occurring participants.

The old functions remain only for historical replay or retrieval ranking. `_trim_target_surface`, kinship suffix interpretation, nearest-anchor logic, and single-character special cases no longer have authority in the SFH1 core path. The complete disposition is recorded in `data/generated/sfh1/python-semantic-heuristic-audit.json`.

## L0–L9 pipeline

1. **L0 source packets** — deterministic Story/main-text/Liu boundaries, evidence IDs, exact text and hashes.
2. **L1 mention reading** — blind, one-Story semantic reading. The model extracts all person-related references without Python labels. It copies surfaces and returns null offsets; Python locates the exact span to avoid provider/code-point offset conventions.
3. **L2 mention validation** — exact source membership, offsets, evidence IDs, schema, overlap ledger, stable mention IDs, non-person isolation.
4. **L3 reference semantics** — model-owned reference type, coreference, distinctness, holder/patron/anchor roles, and semantic relation assertions. Dense Stories are split into bounded four-target chunks while all Story mentions remain available as context.
5. **L4 candidate retrieval** — Python searches canonical Persons, provenance-valid forms, HDA2 suppression overlays, prior candidate Persons, local mentions, and grounded cross-story forms. Candidate keys are Python-owned.
6. **L5 identity judgment** — the model assesses only supplied candidate keys and supplied evidence.
7. **L6 hard constraints** — Python rejects invalid IDs/evidence, non-person candidates, validated structural collapses, and explicit grounded contradictions.
8. **L7 collective consistency** — the frozen PSL/HL-MRF implementation is retained without weight changes. It consumes semantic predicates; it cannot repair mention boundaries.
9. **L8 adversarial review** — risky existing-Person proposals are challenged in bounded batches. Invalid or missing review demotes to review.
10. **L9 storage gate** — emits only stable existing, local candidate, review, unresolved, structural-reference, or non-person research states.

Mention extraction, reference semantics, identity assessment, temporal interpretation, and adversarial review use separate strict function schemas and separately versioned cache keys. Raw provider responses are immutable under `data/generated/sfh1/live/sfh1-v1/raw-api/`. Checkpoints make interrupted runs resumable; raw sequence allocation scans existing files and is concurrency-safe.

## Validation universe

The frozen growth universe remains 187 Stories: 143 production Stories, Wave A's 20, and Wave B's 24. `04-wenxue-023` is added only as an explicit mention-regression control, producing 188 SFH1 reading packets without changing HGE1 scope. A deterministic 30-Story blind-audit projection is stored separately.

The completed live/replay snapshot contains:

- 188 Story packets;
- 3,303 exact-grounded mentions: 2,867 person, 363 collective-person, and 73 non-person;
- 86 independently rejected malformed/ungrounded mention items;
- 2,219 grounded semantic relation assertions, 574 with both endpoints complete;
- 1,295 grounded temporal assertions;
- 599 stable existing-Person decisions, 597 local candidate decisions, 945 review-required, 483 unresolved, and 606 structural references;
- 56 unique existing Persons reached and 542 unique candidate Person observations across the full audit.

Bounded provider recovery completed every frozen Story checkpoint. Two unusually dense L1 packets and one L3 packet still fail closed after exhausting the configured output/retry boundary; their 15 affected occurrence decisions are explicitly attributed to `provider_failure`. None is a known regression control. All known boundary controls pass, `佛經` is not a Person, the anonymous `北來道人` remains descriptive rather than a fabricated full name, and forbidden stable identity resolutions remain zero.

## Old versus new targets

For the 44 old Wave A/B Python targets, 27 were exact matches to the new mention ledger. Fifteen were identified as boundary/compound-target artifacts (seven too-long boundaries and eight missed-multiple-mention cases); two remain ambiguous. The descriptive old-target precision is 61.36%, with a 34.09% boundary-error rate. These are regression-grounded architecture diagnostics, not a manually reviewed corpus-wide gold estimate.

The corrected ledger demonstrates multiple mentions in one clause (`顧長康`, `裴叔則`) and separates descriptive, collective, pronoun, kinship, office, ruler, and non-person references. Candidate creation is not one-per-Story and existing Persons are searched before local candidates.

## Recalibrated HGE1 counterfactual

The original HGE1 measurements remain unchanged. SFH1 stores a separate counterfactual series:

| Point | Stories | Candidate Persons | PersonStory | Graph nodes | Graph edges | Components |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 143 | 13 | 330 | 347 | 996 | 6 |
| Wave A SFH1 | 163 | 62 | 402 | 416 | 1,068 | 25 |
| Wave B SFH1 | 187 | 92 | 439 | 468 | 1,105 | 45 |

Fifteen old compound/boundary target artifacts were removed, but semantic-first reading exposed additional grounded person references, yielding 79 distinct Wave A/B candidate IDs versus 44 old mechanical candidates. The recalibrated Node Novelty Rate is 1.7955 and Edge Novelty Rate 4.5227 per Story. Candidate-aware existing-node densification is not yet demonstrated: complete existing-Person relation edges are zero. The larger candidate frontier is therefore evidence of improved mention recall, not proof of 79 new historical people; human audit and identity deduplication remain necessary before interpreting the growth curve as linear discovery.

## Cost and failure attribution

Across the initial run, schema correction, chunked rebuild, and bounded recovery attempts, the immutable transport ledger records 4,087 calls/attempts, 973 cache hits, 9,072,595 prompt tokens, 5,524,129 completion tokens, and 14,596,724 total tokens. Median request latency is 7.809 seconds and maximum is 37.818 seconds. These deliberately conservative totals include superseded prompt-version attempts, truncations, cache recovery, and provider-refused retries; final-projection stage detail remains in `metrics.json`.

Failures are attributed separately to mention/provider failure, uncertain reference semantics, candidate recall, insufficient identity evidence, hard constraints, collective ambiguity, and reviewer rejection. They are not collapsed into one generic unresolved state.

## Validation results

- Two independent offline rebuilds were byte-identical.
- The focused SFH1 layer suite passes 16 tests.
- The exact portable repository suite passes 1,177 tests.
- HDA1, HDA2, HGE1 Wave A/B, HDB1 Wave 1/2 and aggregate, HDB2-F, HDB2-XE0, HNG2 closeout, H0A, and H0B validators pass.
- Frontend TypeScript checking, production build, and production artifact validation pass.
- `git diff --check`, exact evidence validation, candidate-only gates, and protected canonical hashes pass.

No canonical file, prior HGE wave artifact, production Person ID, reviewed relation, or temporal anchor was changed.

## Safety and migration recommendation

Canonical protected hashes remain frozen. No production Person ID was created, no canonical relation or temporal anchor changed, and no model-created candidate key can mutate storage. The review gate remains fail-closed.

Recommendation: **`hybrid_more_validation_needed`**.

LLM-first extraction eliminates every demonstrated compound-boundary failure and relation semantics are materially richer than regex marker counts. It is not yet safe to make SFH1 the default: the 30-Story blind packet has not received human review, three dense packets remain fail-closed, candidate observations still require identity deduplication, and the recalibrated network does not establish existing-node densification. The next action should be blind human audit and targeted packet-size engineering—not another semantic heuristic patch and not Wave C.

In the requested migration terms:

1. LLM-first mention reading removed all known Python boundary regressions; broader precision still awaits blind human review.
2. Fifteen of 44 old Wave A/B targets were boundary or compound-target artifacts.
3. Across the complete SFH1 universe, 599 resolved occurrences reach 56 existing Persons. Within Wave A/B, the conservative identity gate currently attaches only two occurrences to one existing Person.
4. The recalibrated curve is `143/13/996 → 163/62/1,068 → 187/92/1,105` for Stories/candidate Persons/edges.
5. Candidate observations continue to grow, but the unreviewed candidate frontier cannot establish linear unique-Person discovery.
6. Existing-node densification is not demonstrated (`0` completed existing-Person edges in the Wave A/B counterfactual).
7. Semantic relation extraction yields 199 Wave A/B assertions and raises the recalibrated edge delta from the original 44 to 109, but endpoint identity remains the bottleneck.
8. The cumulative architecture run used 4,087 provider attempts and 14,596,724 tokens, including failed and superseded recovery attempts.
9. Target trimming, suffix-based kinship decisions, nearest-anchor office assignment, and single-character identity special cases can leave the core path; exact grounding and registry constraints remain deterministic.
10. The authority boundary is safe, but the projection is not ready to become the default until blind audit and dense-packet completion confirm precision and operational cost.

## Remaining risks

- Provider availability and high annotation density materially affect completion and cost.
- Model mention recall is not gold; the 30-Story blind packet requires human inspection.
- Two dense mention packets and one reference-semantics packet remain fail-closed, so aggregate relation and identity metrics are slightly conservative.
- Candidate retrieval needs broader provenance-safe office/ruler/temporal indexing before default migration.
- No production migration or canonical materialization is authorized by SFH1.
