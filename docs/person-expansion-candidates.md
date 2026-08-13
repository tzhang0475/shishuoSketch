# P3A Person Expansion Candidate Ranking

> Decision-support analysis only. This report does not materialize Persons, relations, PersonStory links, or publication records.

## Scope result

The current structured repository contains **7 scoped Persons** and **1130 canonical Shishuo Stories**. The eligible non-scoped identity universe is **0**.

No additional stable Person identity is currently available for ranking. All resolved Shishuo/Jinshu `person_id` values are already in the seven-Person registry; other recurring surfaces remain unresolved or point only to scoped Persons.

This is an intentional stopping point: P3A does not turn a surface such as `王公` or `太傅` into a Person. An identity-resolution/materialization review pass is required before a P3B wave can be recommended.

## Ranking dimensions and weights

The composite is deterministic and interpretable:

`score = 100 × (positive weighted components − 0.15 × ambiguity_risk)`

Positive components use bounded linear normalization. Count dimensions are divided by the largest value in the eligible candidate universe and capped at 1. Identity evidence and ambiguity use the documented bounded sub-formulas in the generated JSON.

| Dimension | Weight | Meaning |
| --- | ---: | --- |
| Current SC1 Story coverage | 0.22 | current_story_coverage |
| Potentially connected non-SC1 Stories | 0.22 | story_unlock_potential |
| Reviewed direct Relation connectivity | 0.16 | current_network_connectivity |
| Full Shishuo Story coverage | 0.12 | corpus_story_coverage |
| Identity/evidence quality | 0.12 | identity_evidence_quality |
| Supported family/clan bridge value | 0.06 | clan_bridge_value |
| Useful historical naming forms | 0.05 | naming_richness |
| Distinct source-family depth | 0.05 | source_depth |
| Ambiguity penalty | 0.15 | ambiguity_risk |

Main-text Story presence receives more current-coverage weight than Liu-annotation-only presence. Shared Stories are kept separate from direct Relations and never create a Relation record.

## Distribution

- Candidate identities: **0**
- Tier A / B / C / deferred: **0 / 0 / 0 / 0**
- Candidates in current SC1: **0**
- Median / maximum corpus Story coverage: **0.0 / 0**
- Strong identity-evidence candidates: **0**

## Top candidates

There are no ranked identities, so a top-15 list cannot be truthfully produced.

## Current live Story gaps

No resolved non-scoped candidate Person appears in the current SC1 Stories. The visible gaps are unresolved surfaces, not stable candidate identities.

## Unresolved surface audit

These are review clusters, not ranked Persons. Frequency alone does not establish identity.

| Surface | Mentions | Stories | Existing candidate IDs | Reason |
| --- | ---: | ---: | --- | --- |
| 謝公 | 76 | 61 | xie-an | unresolved_scoped_identity |
| 王丞相 | 48 | 45 | wang-dao | unresolved_scoped_identity |
| 王公 | 42 | 29 | wang-dao, wang-xizhi | unresolved_scoped_identity |
| 王右軍 | 28 | 28 | wang-xizhi | unresolved_scoped_identity |
| 謝太傅 | 28 | 28 | xie-an | unresolved_scoped_identity |
| 右軍 | 23 | 14 | wang-xizhi | unresolved_scoped_identity |
| 丞相 | 22 | 14 | wang-dao | unresolved_scoped_identity |
| 太傅 | 14 | 10 | xi-jian, xie-an | unresolved_scoped_identity |
| 郗公 | 8 | 5 | xi-jian | unresolved_scoped_identity |

## Recommended P3B wave

No P3B Persons are recommended from this run. The repository must first add or review stable non-scoped identity records; doing so is outside P3A and cannot be replaced by guessing from generic titles or co-occurrence.

## Method and safeguards

- Candidate keys are derived analysis keys (`candidate:<existing-source-id>`), not production Person IDs.
- Current Story coverage, corpus coverage, and unlock Stories use resolved Shishuo mentions only.
- Direct connectivity counts only `reviewed` + `direct` Relation records. Derived Relations and co-occurrence are not counted as direct edges.
- Jinshu evidence can strengthen source depth/evidence for an eligible identity, but Jinshu text does not create Shishuo Story links.
- No Sanguozhi data, external research, canonical text, Mention, Relation, PersonStory, punctuation, or frontend data is changed by P3A.
