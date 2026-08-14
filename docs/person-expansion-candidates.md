# P3A Person Expansion Candidate Ranking

> Decision-support analysis only. This report does not materialize Persons, relations, PersonStory links, or publication records.

## Scope result

The current structured repository contains **35 scoped Persons** and **1130 canonical Shishuo Stories**. The eligible non-scoped identity universe is **295**; P3A.1 supplied **295** strong open-world review keys.

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

- Candidate identities: **295**
- Tier A / B / C / deferred: **1 / 5 / 74 / 215**
- Candidates in current SC1: **24**
- Median / maximum corpus Story coverage: **1.0 / 49**
- Strong identity-evidence candidates: **154**

## Top candidates

### 王隱

Rank: **1** · Score: **77.84** · Tier: **A**

- Current Stories: 0 main-text, 3 Liu-annotation-only
- Corpus Stories: 49 · unlock potential: 20
- Direct reviewed Relations to current scope: 0 · shared Stories: 23
- Risks: contextual_surface_association, single_source_unit

### 虞預

Rank: **2** · Score: **56.52** · Tier: **B**

- Current Stories: 0 main-text, 3 Liu-annotation-only
- Corpus Stories: 21 · unlock potential: 10
- Direct reviewed Relations to current scope: 0 · shared Stories: 13
- Risks: single_source_unit

### 嵇康

Rank: **3** · Score: **49.43** · Tier: **B**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 22 · unlock potential: 8
- Direct reviewed Relations to current scope: 0 · shared Stories: 9
- Risks: single_source_unit

### 山濤

Rank: **4** · Score: **46.14** · Tier: **B**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 17 · unlock potential: 6
- Direct reviewed Relations to current scope: 0 · shared Stories: 7
- Risks: contextual_surface_association, single_source_unit

### 阮籍

Rank: **5** · Score: **45.39** · Tier: **B**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 19 · unlock potential: 5
- Direct reviewed Relations to current scope: 0 · shared Stories: 6
- Risks: single_source_unit

### 徐廣

Rank: **6** · Score: **42.22** · Tier: **B**

- Current Stories: 0 main-text, 2 Liu-annotation-only
- Corpus Stories: 15 · unlock potential: 5
- Direct reviewed Relations to current scope: 0 · shared Stories: 7
- Risks: single_source_unit

### 羊祜

Rank: **7** · Score: **39.74** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 8 · unlock potential: 2
- Direct reviewed Relations to current scope: 0 · shared Stories: 3
- Risks: contextual_surface_association, single_source_unit

### 陶侃

Rank: **8** · Score: **38.65** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 5 · unlock potential: 4
- Direct reviewed Relations to current scope: 0 · shared Stories: 5
- Risks: contextual_surface_association, single_source_unit

### 劉伶

Rank: **9** · Score: **38.30** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 8 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: single_source_unit

### 荀顗

Rank: **10** · Score: **35.37** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 5 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: single_source_unit

### 孫盛

Rank: **11** · Score: **34.39** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 25 · unlock potential: 7
- Direct reviewed Relations to current scope: 0 · shared Stories: 7
- Risks: single_source_unit

### 王祥

Rank: **12** · Score: **33.30** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 3 · unlock potential: 0
- Direct reviewed Relations to current scope: 0 · shared Stories: 1
- Risks: single_source_unit

### 杜預

Rank: **13** · Score: **32.32** · Tier: **C**

- Current Stories: 0 main-text, 1 Liu-annotation-only
- Corpus Stories: 9 · unlock potential: 4
- Direct reviewed Relations to current scope: 0 · shared Stories: 5
- Risks: single_source_unit

### 王機

Rank: **14** · Score: **31.80** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 2 · unlock potential: 0
- Direct reviewed Relations to current scope: 0 · shared Stories: 1
- Risks: single_source_unit

### 李充

Rank: **15** · Score: **31.58** · Tier: **C**

- Current Stories: 0 main-text, 1 Liu-annotation-only
- Corpus Stories: 6 · unlock potential: 4
- Direct reviewed Relations to current scope: 0 · shared Stories: 5
- Risks: single_source_unit

## Current live Story gaps

- `05-fangzheng-023` — 王裒 (`candidate-identity-088-liezhuan-004-7bd860ca57e7`)
- `06-yaliang-027` — candidate-identity-067-liezhuan-002-e72bf92e965f (`candidate-identity-067-liezhuan-002-e72bf92e965f`)
- `06-yaliang-029` — candidate-identity-067-liezhuan-002-e72bf92e965f (`candidate-identity-067-liezhuan-002-e72bf92e965f`)

## Unresolved surface audit

These are review clusters, not ranked Persons. Frequency alone does not establish identity.

| Surface | Mentions | Stories | Existing candidate IDs | Reason |
| --- | ---: | ---: | --- | --- |
| 謝公 | 76 | 61 | person-006 | unresolved_scoped_identity |
| 王丞相 | 48 | 45 | person-003 | unresolved_scoped_identity |
| 王公 | 42 | 29 | person-001, person-003 | unresolved_scoped_identity |
| 王右軍 | 28 | 28 | person-001 | unresolved_scoped_identity |
| 謝太傅 | 28 | 28 | person-006 | unresolved_scoped_identity |
| 右軍 | 23 | 14 | person-001 | unresolved_scoped_identity |
| 丞相 | 22 | 14 | person-003 | unresolved_scoped_identity |
| 太傅 | 14 | 10 | person-002, person-006 | unresolved_scoped_identity |
| 郗公 | 8 | 5 | person-002 | unresolved_scoped_identity |

## Recommended P3B wave

This is a review recommendation only; no Person is materialized by P3A. Recommend the top **30** ranked P3A.1-backed candidates for a staged P3B review:

- Wave 1: ranks 1–10, prioritizing current SC1 gaps and the strongest Story traversal payoff.
- Wave 2: ranks 11–30, subject to identity/evidence review before materialization.

The exact wave boundary remains editorial: contextual surface associations, single-source biographies, and candidate identity risks must be reviewed before any P3B registry change.

## Method and safeguards

- Candidate keys are derived analysis keys (`candidate:<existing-source-id>` or `candidate:<p3a1-candidate-id>`), not production Person IDs.
- Current Story coverage, corpus coverage, and unlock Stories use resolved Shishuo mentions only.
- Direct connectivity counts only `reviewed` + `direct` Relation records. Derived Relations and co-occurrence are not counted as direct edges.
- Jinshu evidence can strengthen source depth/evidence for an eligible identity, but Jinshu text does not create Shishuo Story links.
- P3A.1 strong candidates are ranking inputs only; no Sanguozhi data, external research, canonical text, Mention, Relation, PersonStory, punctuation, or frontend data is changed by P3A.
