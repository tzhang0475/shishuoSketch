# P3A Person Expansion Candidate Ranking

> Decision-support analysis only. This report does not materialize Persons, relations, PersonStory links, or publication records.

## Scope result

The current structured repository contains **7 scoped Persons** and **1130 canonical Shishuo Stories**. The eligible non-scoped identity universe is **323**; P3A.1 supplied **323** strong open-world review keys.

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

- Candidate identities: **323**
- Tier A / B / C / deferred: **0 / 6 / 80 / 237**
- Candidates in current SC1: **10**
- Median / maximum corpus Story coverage: **1.0 / 49**
- Strong identity-evidence candidates: **182**

## Top candidates

### 桓溫

Rank: **1** · Score: **59.11** · Tier: **B**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 41 · unlock potential: 4
- Direct reviewed Relations to current scope: 0 · shared Stories: 5
- Risks: contextual_surface_association, single_source_unit

### 劉惔

Rank: **2** · Score: **51.31** · Tier: **B**

- Current Stories: 1 main-text, 1 Liu-annotation-only
- Corpus Stories: 36 · unlock potential: 0
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: contextual_surface_association, single_source_unit

### 庾亮

Rank: **3** · Score: **50.80** · Tier: **B**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 33 · unlock potential: 7
- Direct reviewed Relations to current scope: 0 · shared Stories: 7
- Risks: contextual_surface_association, single_source_unit

### 王敦

Rank: **4** · Score: **46.28** · Tier: **B**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 40 · unlock potential: 5
- Direct reviewed Relations to current scope: 0 · shared Stories: 5
- Risks: contextual_surface_association, single_source_unit

### 袁宏

Rank: **5** · Score: **44.57** · Tier: **B**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 14 · unlock potential: 2
- Direct reviewed Relations to current scope: 0 · shared Stories: 3
- Risks: contextual_surface_association, single_source_unit

### 温嶠

Rank: **6** · Score: **41.05** · Tier: **B**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 20 · unlock potential: 5
- Direct reviewed Relations to current scope: 0 · shared Stories: 5
- Risks: contextual_surface_association, single_source_unit

### 王濛

Rank: **7** · Score: **39.93** · Tier: **C**

- Current Stories: 0 main-text, 1 Liu-annotation-only
- Corpus Stories: 21 · unlock potential: 2
- Direct reviewed Relations to current scope: 0 · shared Stories: 3
- Risks: single_source_unit

### 孫晷

Rank: **8** · Score: **39.32** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 14 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: single_source_unit

### 王遐

Rank: **9** · Score: **37.36** · Tier: **C**

- Current Stories: 1 main-text, 0 Liu-annotation-only
- Corpus Stories: 6 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: single_source_unit

### 蘇峻

Rank: **10** · Score: **37.35** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 19 · unlock potential: 4
- Direct reviewed Relations to current scope: 0 · shared Stories: 4
- Risks: single_source_unit

### 王隱

Rank: **11** · Score: **36.35** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 49 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 1
- Risks: contextual_surface_association, single_source_unit

### 周顗

Rank: **12** · Score: **33.03** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 24 · unlock potential: 2
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: contextual_surface_association, single_source_unit

### 謝尚

Rank: **13** · Score: **32.70** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 24 · unlock potential: 2
- Direct reviewed Relations to current scope: 0 · shared Stories: 2
- Risks: contextual_surface_association, single_source_unit

### 王恭

Rank: **14** · Score: **31.77** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 33 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 1
- Risks: contextual_surface_association, single_source_unit

### 王戎

Rank: **15** · Score: **31.77** · Tier: **C**

- Current Stories: 0 main-text, 0 Liu-annotation-only
- Corpus Stories: 33 · unlock potential: 1
- Direct reviewed Relations to current scope: 0 · shared Stories: 1
- Risks: contextual_surface_association, single_source_unit

## Current live Story gaps

- `02-yanyu-069` — 劉惔 (`candidate-identity-075-liezhuan-006-8fa047488139`)
- `02-yanyu-071` — 孫恩 (`candidate-identity-100-liezhuan-010-96bcbe2d3579`)
- `02-yanyu-083` — 袁宏 (`candidate-identity-092-liezhuan-013-76b547bbee32`)
- `04-wenxue-036` — 向秀 (`candidate-identity-049-liezhuan-003-1e8de1e68064`)
- `05-fangzheng-023` — 王裒 (`candidate-identity-088-liezhuan-004-7bd860ca57e7`), 孟陋 (`candidate-identity-094-liezhuan-016-86bd1f390c7b`)
- `05-fangzheng-055` — 劉惔 (`candidate-identity-075-liezhuan-006-8fa047488139`), 王濛 (`candidate-identity-093-liezhuan-010-e8abd34dc108`), 王遐 (`candidate-identity-093-liezhuan-011-9b983af9b748`)
- `06-yaliang-027` — candidate-identity-067-liezhuan-002-e72bf92e965f (`candidate-identity-067-liezhuan-002-e72bf92e965f`)
- `06-yaliang-029` — candidate-identity-067-liezhuan-002-e72bf92e965f (`candidate-identity-067-liezhuan-002-e72bf92e965f`), 孫晷 (`candidate-identity-088-liezhuan-007-ca650e9ceb0f`), 桓溫 (`candidate-identity-098-liezhuan-003-7859332a18d3`)

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
