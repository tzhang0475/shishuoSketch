---
schema: 1
stage: semantic-segmentation
report_type: shishuo-chapter-validation
normalized_input_count: 4
textual_heading_occurrence_count: 37
canonical_chapter_count: 36
missing_chapters: []
duplicate_chapters: []
ambiguous_boundary_count: 3
---

# Shishuo Xinyu semantic-segmentation validation

The normalized Markdown inputs are read-only.  Chapter boundaries are taken only from explicit headings in main-text FILE sections.  Entry splitting and knowledge extraction are intentionally not performed.

## Summary

- Canonical chapters expected: 36
- Canonical chapters detected: 36
- Textual heading occurrences: 37
- Missing chapters: none
- Unintentional duplicate chapters: none

## Canonical chapters

| # | Canonical heading | Observed heading(s) | Normalized file(s) | FILE section(s) | Start | End | Status |
|---:|---|---|---|---|---|---|---|
| 1 | 德行第一 | 德行第一 | KR3l0002_001.md | SB03n0058-001世説新語-卷上之上. | KR3l0002_001.md:normalized-line=699;source-line=643;page=<pb:KR3l0002_SBCK_001-1a> | KR3l0002_001.md:normalized-line=1044;source-line=988;page=<pb:KR3l0002_SBCK_001-16b> | detected |
| 2 | 言語第二 | 言語第二 | KR3l0002_001.md | SB03n0058-001世説新語-卷上之上. | KR3l0002_001.md:normalized-line=1045;source-line=989;page=<pb:KR3l0002_SBCK_001-16b> | KR3l0002_001.md:normalized-line=1792;source-line=1736;page=<pb:KR3l0002_SBCK_001-50b> | detected |
| 3 | 政事第三 | 政事第三 | KR3l0002_001.md | SB03n0058-001世説新語-卷上之下. | KR3l0002_001.md:normalized-line=1798;source-line=1742;page=<pb:KR3l0002_SBCK_001-51a> | KR3l0002_001.md:normalized-line=1967;source-line=1911;page=<pb:KR3l0002_SBCK_001-58b> | detected |
| 4 | 文學第四 | 文學第四 | KR3l0002_001.md | SB03n0058-001世説新語-卷上之下. | KR3l0002_001.md:normalized-line=1968;source-line=1912;page=<pb:KR3l0002_SBCK_001-58b> | KR3l0002_001.md:normalized-line=2624;source-line=2568;page=<pb:KR3l0002_SBCK_001-89a> | detected |
| 5 | 方正第五 | 方正第五 | KR3l0002_002.md | SB03n0058-003世説新語-卷中之上. | KR3l0002_002.md:normalized-line=69;source-line=13;page=<pb:KR3l0002_SBCK_002-1a> | KR3l0002_002.md:normalized-line=545;source-line=489;page=<pb:KR3l0002_SBCK_002-24b> | detected |
| 6 | 雅量第六 | 雅量第六 | KR3l0002_002.md | SB03n0058-003世説新語-卷中之上. | KR3l0002_002.md:normalized-line=546;source-line=490;page=<pb:KR3l0002_SBCK_002-24b> | KR3l0002_002.md:normalized-line=802;source-line=746;page=<pb:KR3l0002_SBCK_002-36a> | detected |
| 7 | 識鑒第七 | 識鑒第七 | KR3l0002_002.md | SB03n0058-003世説新語-卷中之上. | KR3l0002_002.md:normalized-line=803;source-line=747;page=<pb:KR3l0002_SBCK_002-36a> | KR3l0002_002.md:normalized-line=1013;source-line=957;page=<pb:KR3l0002_SBCK_002-46a> | detected |
| 8 | 賞譽第八 | 賞譽第八(上)<br>賞譽第八(下) | KR3l0002_002.md<br>KR3l0002_003.md | SB03n0058-003世説新語-卷中之上.<br>SB03n0058-003世説新語-卷中之下. | KR3l0002_002.md:normalized-line=1014;source-line=958;page=<pb:KR3l0002_SBCK_002-46a> | KR3l0002_003.md:normalized-line=462;source-line=418;page=<pb:KR3l0002_SBCK_003-19b> | multipart explicit 上/下 |
| 9 | 品藻第九 | 品藻第九 | KR3l0002_003.md | SB03n0058-003世説新語-卷中之下. | KR3l0002_003.md:normalized-line=463;source-line=419;page=<pb:KR3l0002_SBCK_003-19b> | KR3l0002_003.md:normalized-line=835;source-line=791;page=<pb:KR3l0002_SBCK_003-36b> | detected |
| 10 | 規箴第十 | 規箴第十 | KR3l0002_003.md | SB03n0058-003世説新語-卷中之下. | KR3l0002_003.md:normalized-line=836;source-line=792;page=<pb:KR3l0002_SBCK_003-36b> | KR3l0002_003.md:normalized-line=1033;source-line=989;page=<pb:KR3l0002_SBCK_003-45b> | detected |
| 11 | 捷悟第十一 | 捷悟第十一 | KR3l0002_003.md | SB03n0058-003世説新語-卷中之下. | KR3l0002_003.md:normalized-line=1034;source-line=990;page=<pb:KR3l0002_SBCK_003-45b> | KR3l0002_003.md:normalized-line=1081;source-line=1037;page=<pb:KR3l0002_SBCK_003-47b> | detected |
| 12 | 夙惠第十二 | 夙惠第十二 | KR3l0002_003.md | SB03n0058-003世説新語-卷中之下. | KR3l0002_003.md:normalized-line=1082;source-line=1038;page=<pb:KR3l0002_SBCK_003-47b> | KR3l0002_003.md:normalized-line=1122;source-line=1078;page=<pb:KR3l0002_SBCK_003-49b> | detected |
| 13 | 豪爽第十三 | 豪爽第十三 | KR3l0002_003.md | SB03n0058-003世説新語-卷中之下. | KR3l0002_003.md:normalized-line=1123;source-line=1079;page=<pb:KR3l0002_SBCK_003-49b> | KR3l0002_003.md:normalized-line=1194;source-line=1150;page=<pb:KR3l0002_SBCK_003-54a> | detected |
| 14 | 容止第十四 | 容止第十四 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1201;source-line=1145;page=<pb:KR3l0002_SBCK_002-1a> | KR3l0002_002.md:normalized-line=1331;source-line=1275;page=<pb:KR3l0002_SBCK_002-7a> | detected |
| 15 | 自新第十五 | 自新第十五 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1332;source-line=1276;page=<pb:KR3l0002_SBCK_002-7a> | KR3l0002_002.md:normalized-line=1357;source-line=1301;page=<pb:KR3l0002_SBCK_002-8a> | detected |
| 16 | 企羡第十六 | 企羡第十六 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1358;source-line=1302;page=<pb:KR3l0002_SBCK_002-8a> | KR3l0002_002.md:normalized-line=1379;source-line=1323;page=<pb:KR3l0002_SBCK_002-9a> | detected |
| 17 | 傷逝第十七 | 傷逝第十七 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1380;source-line=1324;page=<pb:KR3l0002_SBCK_002-9a> | KR3l0002_002.md:normalized-line=1476;source-line=1420;page=<pb:KR3l0002_SBCK_002-13b> | detected |
| 18 | 棲逸第十八 | 棲逸第十八 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1477;source-line=1421;page=<pb:KR3l0002_SBCK_002-13b> | KR3l0002_002.md:normalized-line=1560;source-line=1504;page=<pb:KR3l0002_SBCK_002-18a> | detected |
| 19 | 賢媛第十九 | 賢媛第十九 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1561;source-line=1505;page=<pb:KR3l0002_SBCK_002-18a> | KR3l0002_002.md:normalized-line=1792;source-line=1736;page=<pb:KR3l0002_SBCK_002-29b> | detected |
| 20 | 術解第二十 | 術解第二十 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1793;source-line=1737;page=<pb:KR3l0002_SBCK_002-29b> | KR3l0002_002.md:normalized-line=1854;source-line=1798;page=<pb:KR3l0002_SBCK_002-32b> | detected |
| 21 | 巧蓺第二十一 | 巧蓺第二十一 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1855;source-line=1799;page=<pb:KR3l0002_SBCK_002-32b> | KR3l0002_002.md:normalized-line=1912;source-line=1856;page=<pb:KR3l0002_SBCK_002-35a> | detected |
| 22 | 寵禮第二十二 | 寵禮第二十二 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1913;source-line=1857;page=<pb:KR3l0002_SBCK_002-35a> | KR3l0002_002.md:normalized-line=1938;source-line=1882;page=<pb:KR3l0002_SBCK_002-36b> | detected |
| 23 | 任誕第二十三 | 任誕第二十三 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=1939;source-line=1883;page=<pb:KR3l0002_SBCK_002-36b> | KR3l0002_002.md:normalized-line=2219;source-line=2163;page=<pb:KR3l0002_SBCK_002-49a> | detected |
| 24 | 簡傲第二十四 | 簡傲第二十四 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | KR3l0002_002.md:normalized-line=2220;source-line=2164;page=<pb:KR3l0002_SBCK_002-49a> | KR3l0002_002.md:normalized-line=2325;source-line=2269;page=<pb:KR3l0002_SBCK_002-54a> | detected |
| 25 | 排調第二十五 | 排調第二十五 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=2331;source-line=2275;page=<pb:KR3l0002_SBCK_002-55a> | KR3l0002_002.md:normalized-line=2669;source-line=2613;page=<pb:KR3l0002_SBCK_002-70b> | detected |
| 26 | 輕詆第二十六 | 輕詆第二十六 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=2670;source-line=2614;page=<pb:KR3l0002_SBCK_002-70b> | KR3l0002_002.md:normalized-line=2833;source-line=2777;page=<pb:KR3l0002_SBCK_002-78a> | detected |
| 27 | 假譎第二十七 | 假譎第二十七 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=2834;source-line=2778;page=<pb:KR3l0002_SBCK_002-78a> | KR3l0002_002.md:normalized-line=2940;source-line=2884;page=<pb:KR3l0002_SBCK_002-82b> | detected |
| 28 | 黜免第二十八 | 黜免第二十八 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=2941;source-line=2885;page=<pb:KR3l0002_SBCK_002-82b> | KR3l0002_002.md:normalized-line=2992;source-line=2936;page=<pb:KR3l0002_SBCK_002-85a> | detected |
| 29 | 儉嗇第二十九 | 儉嗇第二十九 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=2993;source-line=2937;page=<pb:KR3l0002_SBCK_002-85a> | KR3l0002_002.md:normalized-line=3027;source-line=2971;page=<pb:KR3l0002_SBCK_002-86b> | detected |
| 30 | 汰侈第三十 | 汰侈第三十 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3028;source-line=2972;page=<pb:KR3l0002_SBCK_002-86b> | KR3l0002_002.md:normalized-line=3106;source-line=3050;page=<pb:KR3l0002_SBCK_002-90a> | detected |
| 31 | 忿狷第三十一 | 忿狷第三十一 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3107;source-line=3051;page=<pb:KR3l0002_SBCK_002-90a> | KR3l0002_002.md:normalized-line=3145;source-line=3089;page=<pb:KR3l0002_SBCK_002-92a> | detected |
| 32 | 讒險第三十二 | 讒險第三十二 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3146;source-line=3090;page=<pb:KR3l0002_SBCK_002-92a> | KR3l0002_002.md:normalized-line=3170;source-line=3114;page=<pb:KR3l0002_SBCK_002-93a> | detected |
| 33 | 尤悔第三十三 | 尤悔第三十三 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3171;source-line=3115;page=<pb:KR3l0002_SBCK_002-93a> | KR3l0002_002.md:normalized-line=3277;source-line=3221;page=<pb:KR3l0002_SBCK_002-98a> | detected |
| 34 | 紕漏第三十四 | 紕漏第三十四 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3278;source-line=3222;page=<pb:KR3l0002_SBCK_002-98a> | KR3l0002_002.md:normalized-line=3328;source-line=3272;page=<pb:KR3l0002_SBCK_002-100b> | detected |
| 35 | 惑溺第三十五 | 惑溺第三十五 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3329;source-line=3273;page=<pb:KR3l0002_SBCK_002-100b> | KR3l0002_002.md:normalized-line=3386;source-line=3330;page=<pb:KR3l0002_SBCK_002-103a> | detected |
| 36 | 仇隟第三十六 | 仇隟第三十六 | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | KR3l0002_002.md:normalized-line=3387;source-line=3331;page=<pb:KR3l0002_SBCK_002-103a> | KR3l0002_002.md:normalized-line=3461;source-line=3405;page=<pb:KR3l0002_SBCK_002-106b> | detected |

## FILE section classification

| Type | Normalized file | FILE value | Start | End |
|---|---|---|---:|---:|
| preface | KR3l0002_000.md | SB03n0058-000世説新語-序. | 59 | 81 |
| catalogue | KR3l0002_000.md | SB03n0058-000世説新語-目録. | 83 | 120 |
| collation_notes | KR3l0002_001.md | SB03n0059-001世説新語校語-一卷. | 65 | 693 |
| main_text | KR3l0002_001.md | SB03n0058-001世説新語-卷上之上. | 695 | 1792 |
| main_text | KR3l0002_001.md | SB03n0058-001世説新語-卷上之下. | 1794 | 2624 |
| main_text | KR3l0002_002.md | SB03n0058-003世説新語-卷中之上. | 65 | 1195 |
| main_text | KR3l0002_002.md | SB03n0058-002世説新語-卷下之上. | 1197 | 2325 |
| main_text | KR3l0002_002.md | SB03n0058-002世説新語-卷下之下. | 2327 | 3461 |
| main_text | KR3l0002_003.md | SB03n0058-003世説新語-卷中之下. | 53 | 1194 |

## Ambiguous or intentionally deferred boundaries

- Chapter 8 has explicit 賞譽第八(上) and 賞譽第八(下) headings in different main-text FILE sections; they are grouped as one canonical chapter and both source positions are retained.
- Main-text source spellings 企羡第十六 and 巧蓺第二十一 are matched as observed; no character normalization is applied.
- Individual Shishuo entry boundaries are intentionally not inferred; each chapter file retains its contiguous source span and annotations.

## Editorial material excluded from chapter files

- `preface`: the FILE section ending in `序`.
- `catalogue`: the FILE section containing `目録`.
- `collation_notes`: the FILE section named `世説新語校語`.

All excluded material remains available in the corresponding files under `../editorial/` and in the untouched normalized inputs.
