# CRL1 Corpus Reading Layer Audit

本报告由 `scripts/build_shishuo_reading_layer.py` 生成；CRL1.1 将 review status 与 punctuation basis 分开记录。它不包含自动句读的人工背书。Wikisource 四部叢刊 comparison view 当前没有句读，因此不能作为第二个句读参考。

- canonical entries: 1130
- reviewed: 1
- aligned: 0
- candidate: 1069
- disputed: 60
- review_status=reviewed: 1
- review_status=unreviewed: 1129
- punctuation_basis=human_reviewed: 1
- punctuation_basis=trusted_reference_exact: 0
- punctuation_basis=reference_candidate: 1069
- punctuation_basis=disputed: 60
- story_reader_ready: 1
- punctuation generated: 1070
- technically exact transfers: 348
- transfer class exact_character_transfer: 348
- transfer class character_mismatch_around_punctuation: 721
- transfer class structural_or_boundary_mismatch: 59
- transfer class missing_reference: 2
- simplified reading available: 1070
- display overrides: 0
- exact character alignments: 348
- one-to-one character-disagreement alignments: 721
- exact two-reference punctuation agreements: 0
- one-reference-only exact/transfer candidates: 1069
- punctuation disagreements: 0
- character disagreements: 721
- alignment failures: 61
- persisted disputed records after reviewed overrides: 60
- queue A trusted/reference-ready: 1
- queue B exact-transfer awaiting source qualification: 348
- queue C punctuation-review candidate: 721
- queue D disputed/structural review: 60

## Source qualification

- witness: `shishuo-local-reference-txt`
- qualification: `provisionally_qualified`
- source: `sources/local/shishuo/reference-txt/shishuo.txt`
- source SHA-256: `843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205`
- trusted_reference_exact promotion: disabled because tracked provenance remains unresolved and the witness is only provisionally qualified.

## Persisted disputed-case categories

- structural alignment failure: 60
- reference deletion: 44
- reference insertion: 14
- missing usable numbered reference: 2

## Chapter counts

| chapter | reviewed | aligned | candidate | disputed | reader-ready |
|---|---:|---:|---:|---:|---:|
| 01 | 0 | 0 | 47 | 0 | 0 |
| 02 | 0 | 0 | 103 | 5 | 0 |
| 03 | 0 | 0 | 25 | 1 | 0 |
| 04 | 0 | 0 | 98 | 6 | 0 |
| 05 | 0 | 0 | 62 | 4 | 0 |
| 06 | 1 | 0 | 40 | 1 | 1 |
| 07 | 0 | 0 | 27 | 1 | 0 |
| 08 | 0 | 0 | 149 | 7 | 0 |
| 09 | 0 | 0 | 86 | 2 | 0 |
| 10 | 0 | 0 | 27 | 0 | 0 |
| 11 | 0 | 0 | 6 | 1 | 0 |
| 12 | 0 | 0 | 6 | 1 | 0 |
| 13 | 0 | 0 | 12 | 1 | 0 |
| 14 | 0 | 0 | 38 | 1 | 0 |
| 15 | 0 | 0 | 2 | 0 | 0 |
| 16 | 0 | 0 | 6 | 0 | 0 |
| 17 | 0 | 0 | 19 | 0 | 0 |
| 18 | 0 | 0 | 14 | 3 | 0 |
| 19 | 0 | 0 | 28 | 4 | 0 |
| 20 | 0 | 0 | 11 | 0 | 0 |
| 21 | 0 | 0 | 14 | 0 | 0 |
| 22 | 0 | 0 | 5 | 1 | 0 |
| 23 | 0 | 0 | 49 | 5 | 0 |
| 24 | 0 | 0 | 16 | 1 | 0 |
| 25 | 0 | 0 | 61 | 4 | 0 |
| 26 | 0 | 0 | 29 | 4 | 0 |
| 27 | 0 | 0 | 14 | 0 | 0 |
| 28 | 0 | 0 | 9 | 0 | 0 |
| 29 | 0 | 0 | 9 | 0 | 0 |
| 30 | 0 | 0 | 9 | 3 | 0 |
| 31 | 0 | 0 | 8 | 0 | 0 |
| 32 | 0 | 0 | 3 | 1 | 0 |
| 33 | 0 | 0 | 17 | 0 | 0 |
| 34 | 0 | 0 | 6 | 2 | 0 |
| 35 | 0 | 0 | 7 | 0 | 0 |
| 36 | 0 | 0 | 7 | 1 | 0 |

## Method and limits

1. Canonical main text comes from the existing entry Markdown and is never rewritten.
2. The local structural TXT is parsed by chapter and printed ordinal; it supplies the only punctuation-bearing reference in this run and is provisionally qualified for exact-transfer analysis only.
3. Traditional-to-simplified conversion is used only for comparison keys and derived display text; it is never used to replace canonical characters.
4. Exact or one-to-one variant alignment produces an unreviewed `reference_candidate`; exact character equality is recorded separately as `exact_transfer=true`.
5. The local reference has no 文學第23 and no 賞譽第100 numbered paragraph; those entries remain `disputed` and are not repaired by neighboring text.
6. The existing reviewed `06-yaliang-019` record remains authoritative and is the only current `human_reviewed` record. Its machine comparison is retained only in the derived audit record.
7. Detailed human review is limited to C and D; B is a technically exact intermediate class awaiting source qualification, not silent publication.
