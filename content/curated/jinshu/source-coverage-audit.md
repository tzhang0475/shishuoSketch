# Jinshu source coverage audit

This audit scans the raw Kanripo files for explicit source headings and
does not infer coverage from filenames alone. The local raw witness and
the upstream checkout were not modified.

## Result

- local main-text volume numbers: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]`
- upstream main-text volume numbers: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]`
- local missing from expected 卷一–卷一百三十: `[34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130]`
- upstream missing from expected 卷一–卷一百三十: `[34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130]`
- upstream itself incomplete: `yes`
- local/upstream common-file bytes identical: `yes`

The catalogue in `KR2a0015_000.txt` describes 晉書一百三十卷, but
catalogue references are not counted as surviving main-text blocks.

## Local Kanripo files

Directory: `/home/tzhang/projects/shishuoSketch/shishuoSources/jinshu`; file count: `35`.

`KR2a0015_000.txt`, `KR2a0015_001.txt`, `KR2a0015_002.txt`, `KR2a0015_003.txt`, `KR2a0015_004.txt`, `KR2a0015_005.txt`, `KR2a0015_006.txt`, `KR2a0015_007.txt`, `KR2a0015_008.txt`, `KR2a0015_009.txt`, `KR2a0015_010.txt`, `KR2a0015_011.txt`, `KR2a0015_012.txt`, `KR2a0015_013.txt`, `KR2a0015_014.txt`, `KR2a0015_015.txt`, `KR2a0015_016.txt`, `KR2a0015_017.txt`, `KR2a0015_018.txt`, `KR2a0015_019.txt`, `KR2a0015_020.txt`, `KR2a0015_021.txt`, `KR2a0015_022.txt`, `KR2a0015_023.txt`, `KR2a0015_024.txt`, `KR2a0015_025.txt`, `KR2a0015_026.txt`, `KR2a0015_027.txt`, `KR2a0015_028.txt`, `KR2a0015_029.txt`, `KR2a0015_030.txt`, `KR2a0015_031.txt`, `KR2a0015_032.txt`, `KR2a0015_033.txt`, `Readme.org`

### File-declared juan properties

| file | property |
| --- | --- |
| `KR2a0015_000.txt` | `0` |
| `KR2a0015_001.txt` | `卷一` |
| `KR2a0015_002.txt` | `卷二` |
| `KR2a0015_003.txt` | `卷三` |
| `KR2a0015_004.txt` | `卷四` |
| `KR2a0015_005.txt` | `卷五` |
| `KR2a0015_006.txt` | `卷六` |
| `KR2a0015_007.txt` | `卷七考證` |
| `KR2a0015_008.txt` | `卷八` |
| `KR2a0015_009.txt` | `卷九` |
| `KR2a0015_010.txt` | `卷十` |
| `KR2a0015_011.txt` | `卷十一` |
| `KR2a0015_012.txt` | `卷十二` |
| `KR2a0015_013.txt` | `卷十三` |
| `KR2a0015_014.txt` | `卷十四` |
| `KR2a0015_015.txt` | `卷十五` |
| `KR2a0015_016.txt` | `卷十六` |
| `KR2a0015_017.txt` | `卷十七` |
| `KR2a0015_018.txt` | `卷十八` |
| `KR2a0015_019.txt` | `卷十九` |
| `KR2a0015_020.txt` | `卷二十` |
| `KR2a0015_021.txt` | `卷二十一` |
| `KR2a0015_022.txt` | `卷二十二` |
| `KR2a0015_023.txt` | `卷二十三` |
| `KR2a0015_024.txt` | `卷二十四` |
| `KR2a0015_025.txt` | `卷二十五` |
| `KR2a0015_026.txt` | `卷二十六` |
| `KR2a0015_027.txt` | `卷二十七` |
| `KR2a0015_028.txt` | `卷二十八` |
| `KR2a0015_029.txt` | `卷二十九` |
| `KR2a0015_030.txt` | `卷三十` |
| `KR2a0015_031.txt` | `卷三十一` |
| `KR2a0015_032.txt` | `卷三十二` |
| `KR2a0015_033.txt` | `卷三十三` |

### Explicit main-text heading occurrences

| volume | occurrences |
| --- | --- |
| 卷1 | KR2a0015_001.txt:10 `晉書巻一`; KR2a0015_001.txt:457 `晉書巻一` |
| 卷2 | KR2a0015_002.txt:10 `晉書巻二`; KR2a0015_002.txt:454 `晉書卷二` |
| 卷3 | KR2a0015_003.txt:10 `晉書卷三`; KR2a0015_003.txt:635 `晉書卷三` |
| 卷4 | KR2a0015_004.txt:10 `晉書卷四`; KR2a0015_004.txt:377 `晉書卷四` |
| 卷5 | KR2a0015_005.txt:10 `晉書卷五`; KR2a0015_005.txt:474 `晉書卷五` |
| 卷6 | KR2a0015_006.txt:10 `晉書卷六`; KR2a0015_006.txt:510 `晉書卷六` |
| 卷7 | KR2a0015_006.txt:522 `晉書卷七`; KR2a0015_006.txt:852 `晉書卷七` |
| 卷8 | KR2a0015_008.txt:10 `晉書卷八`; KR2a0015_008.txt:439 `晉書卷八` |
| 卷9 | KR2a0015_009.txt:10 `晉書卷九`; KR2a0015_009.txt:436 `晉書卷九` |
| 卷10 | KR2a0015_010.txt:10 `晉書卷十`; KR2a0015_010.txt:391 `晉書卷十` |
| 卷11 | KR2a0015_011.txt:10 `晉書卷十一`; KR2a0015_011.txt:814 `晉書卷十一` |
| 卷12 | KR2a0015_012.txt:10 `晉書卷十二`; KR2a0015_012.txt:956 `晉書卷十二` |
| 卷13 | KR2a0015_013.txt:10 `晉書卷十三`; KR2a0015_013.txt:1032 `晉書卷十三` |
| 卷14 | KR2a0015_014.txt:10 `晉書卷十四`; KR2a0015_014.txt:825 `晉書卷十四` |
| 卷15 | KR2a0015_015.txt:10 `晉書卷十五`; KR2a0015_015.txt:430 `晉書卷十五` |
| 卷16 | KR2a0015_016.txt:10 `晉書卷十六`; KR2a0015_016.txt:485 `晉書卷十六` |
| 卷17 | KR2a0015_017.txt:10 `晉書卷十七`; KR2a0015_017.txt:748 `晉書卷十七` |
| 卷18 | KR2a0015_018.txt:10 `晉書卷十八`; KR2a0015_018.txt:824 `晉書卷十八` |
| 卷19 | KR2a0015_019.txt:10 `晉書卷十九` |
| 卷20 | KR2a0015_020.txt:10 `晉書卷二十` |
| 卷21 | KR2a0015_021.txt:10 `晉書卷二十一`; KR2a0015_021.txt:551 `晉書卷二十一` |
| 卷22 | KR2a0015_022.txt:10 `晉書卷二十二`; KR2a0015_022.txt:455 `晉書卷二十二` |
| 卷23 | KR2a0015_023.txt:10 `晉書卷二十三`; KR2a0015_023.txt:572 `晉書卷二十三` |
| 卷24 | KR2a0015_024.txt:10 `晉書卷二十四`; KR2a0015_024.txt:596 `晉書卷二十四` |
| 卷25 | KR2a0015_025.txt:10 `晉書卷二十五`; KR2a0015_025.txt:650 `晉書卷二十五` |
| 卷26 | KR2a0015_026.txt:10 `晉書卷二十六`; KR2a0015_026.txt:460 `晉書卷二十六` |
| 卷27 | KR2a0015_027.txt:10 `晉書卷二十七`; KR2a0015_027.txt:752 `晉書卷二十七` |
| 卷28 | KR2a0015_028.txt:10 `晉書卷二十八`; KR2a0015_028.txt:834 `晉書卷二十八` |
| 卷29 | KR2a0015_029.txt:10 `晉書卷二十九`; KR2a0015_029.txt:968 `晉書卷二十九` |
| 卷30 | KR2a0015_030.txt:10 `晉書卷三十`; KR2a0015_030.txt:675 `晉書卷三十` |
| 卷31 | KR2a0015_031.txt:10 `晉書卷三十一`; KR2a0015_031.txt:500 `晉書卷三十一`; KR2a0015_033.txt:572 `晉書卷三十一` |
| 卷32 | KR2a0015_032.txt:10 `晉書卷三十二`; KR2a0015_032.txt:317 `晉書卷三十二`; KR2a0015_033.txt:576 `晉書卷三十二`; KR2a0015_033.txt:883 `晉書卷三十二` |
| 卷33 | KR2a0015_033.txt:10 `晉書卷三十三`; KR2a0015_033.txt:887 `晉書卷三十三` |

### Catalogue references

Distinct catalogue volume references: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130]`.
Catalogue reference numbers absent from the 1–130 range: `[46, 47, 48, 49]`.
These gaps and the catalogue's repeated 卷四十三、卷四十四、卷四十五
references are catalogue anomalies, not evidence that the corresponding
main text is present or absent in the machine witness.

## Duplicate or discontinuous content markers

- 卷1: 2 explicit non-editorial markers — KR2a0015_001.txt:10 `晉書巻一`; KR2a0015_001.txt:457 `晉書巻一`
- 卷2: 2 explicit non-editorial markers — KR2a0015_002.txt:10 `晉書巻二`; KR2a0015_002.txt:454 `晉書卷二`
- 卷3: 2 explicit non-editorial markers — KR2a0015_003.txt:10 `晉書卷三`; KR2a0015_003.txt:635 `晉書卷三`
- 卷4: 2 explicit non-editorial markers — KR2a0015_004.txt:10 `晉書卷四`; KR2a0015_004.txt:377 `晉書卷四`
- 卷5: 2 explicit non-editorial markers — KR2a0015_005.txt:10 `晉書卷五`; KR2a0015_005.txt:474 `晉書卷五`
- 卷6: 2 explicit non-editorial markers — KR2a0015_006.txt:10 `晉書卷六`; KR2a0015_006.txt:510 `晉書卷六`
- 卷7: 2 explicit non-editorial markers — KR2a0015_006.txt:522 `晉書卷七`; KR2a0015_006.txt:852 `晉書卷七`
- 卷8: 2 explicit non-editorial markers — KR2a0015_008.txt:10 `晉書卷八`; KR2a0015_008.txt:439 `晉書卷八`
- 卷9: 2 explicit non-editorial markers — KR2a0015_009.txt:10 `晉書卷九`; KR2a0015_009.txt:436 `晉書卷九`
- 卷10: 2 explicit non-editorial markers — KR2a0015_010.txt:10 `晉書卷十`; KR2a0015_010.txt:391 `晉書卷十`
- 卷11: 2 explicit non-editorial markers — KR2a0015_011.txt:10 `晉書卷十一`; KR2a0015_011.txt:814 `晉書卷十一`
- 卷12: 2 explicit non-editorial markers — KR2a0015_012.txt:10 `晉書卷十二`; KR2a0015_012.txt:956 `晉書卷十二`
- 卷13: 2 explicit non-editorial markers — KR2a0015_013.txt:10 `晉書卷十三`; KR2a0015_013.txt:1032 `晉書卷十三`
- 卷14: 2 explicit non-editorial markers — KR2a0015_014.txt:10 `晉書卷十四`; KR2a0015_014.txt:825 `晉書卷十四`
- 卷15: 2 explicit non-editorial markers — KR2a0015_015.txt:10 `晉書卷十五`; KR2a0015_015.txt:430 `晉書卷十五`
- 卷16: 2 explicit non-editorial markers — KR2a0015_016.txt:10 `晉書卷十六`; KR2a0015_016.txt:485 `晉書卷十六`
- 卷17: 2 explicit non-editorial markers — KR2a0015_017.txt:10 `晉書卷十七`; KR2a0015_017.txt:748 `晉書卷十七`
- 卷18: 2 explicit non-editorial markers — KR2a0015_018.txt:10 `晉書卷十八`; KR2a0015_018.txt:824 `晉書卷十八`
- 卷21: 2 explicit non-editorial markers — KR2a0015_021.txt:10 `晉書卷二十一`; KR2a0015_021.txt:551 `晉書卷二十一`
- 卷22: 2 explicit non-editorial markers — KR2a0015_022.txt:10 `晉書卷二十二`; KR2a0015_022.txt:455 `晉書卷二十二`
- 卷23: 2 explicit non-editorial markers — KR2a0015_023.txt:10 `晉書卷二十三`; KR2a0015_023.txt:572 `晉書卷二十三`
- 卷24: 2 explicit non-editorial markers — KR2a0015_024.txt:10 `晉書卷二十四`; KR2a0015_024.txt:596 `晉書卷二十四`
- 卷25: 2 explicit non-editorial markers — KR2a0015_025.txt:10 `晉書卷二十五`; KR2a0015_025.txt:650 `晉書卷二十五`
- 卷26: 2 explicit non-editorial markers — KR2a0015_026.txt:10 `晉書卷二十六`; KR2a0015_026.txt:460 `晉書卷二十六`
- 卷27: 2 explicit non-editorial markers — KR2a0015_027.txt:10 `晉書卷二十七`; KR2a0015_027.txt:752 `晉書卷二十七`
- 卷28: 2 explicit non-editorial markers — KR2a0015_028.txt:10 `晉書卷二十八`; KR2a0015_028.txt:834 `晉書卷二十八`
- 卷29: 2 explicit non-editorial markers — KR2a0015_029.txt:10 `晉書卷二十九`; KR2a0015_029.txt:968 `晉書卷二十九`
- 卷30: 2 explicit non-editorial markers — KR2a0015_030.txt:10 `晉書卷三十`; KR2a0015_030.txt:675 `晉書卷三十`
- 卷31: 3 explicit non-editorial markers — KR2a0015_031.txt:10 `晉書卷三十一`; KR2a0015_031.txt:500 `晉書卷三十一`; KR2a0015_033.txt:572 `晉書卷三十一`
- 卷32: 4 explicit non-editorial markers — KR2a0015_032.txt:10 `晉書卷三十二`; KR2a0015_032.txt:317 `晉書卷三十二`; KR2a0015_033.txt:576 `晉書卷三十二`; KR2a0015_033.txt:883 `晉書卷三十二`
- 卷33: 2 explicit non-editorial markers — KR2a0015_033.txt:10 `晉書卷三十三`; KR2a0015_033.txt:887 `晉書卷三十三`

In particular, `KR2a0015_033.txt` has the following sequence:

- `晉書卷三十三` at line 10;
- a relocated `晉書卷三十一` marker at line 572;
- a new `晉書卷三十二` block at line 576;
- a closing `晉書卷三十二` marker at line 883;
- a second `晉書卷三十三` block at line 887.

The repeated 卷三十二/卷三十三 blocks are retained as source evidence;
this audit does not deduplicate or repair them.

## Upstream checkout

Directory: `/tmp/kr2a0015-audit`; commit: `82291520954e5af1fdade894971a2f5810fd4e31`; file count: `35`.

`KR2a0015_000.txt`, `KR2a0015_001.txt`, `KR2a0015_002.txt`, `KR2a0015_003.txt`, `KR2a0015_004.txt`, `KR2a0015_005.txt`, `KR2a0015_006.txt`, `KR2a0015_007.txt`, `KR2a0015_008.txt`, `KR2a0015_009.txt`, `KR2a0015_010.txt`, `KR2a0015_011.txt`, `KR2a0015_012.txt`, `KR2a0015_013.txt`, `KR2a0015_014.txt`, `KR2a0015_015.txt`, `KR2a0015_016.txt`, `KR2a0015_017.txt`, `KR2a0015_018.txt`, `KR2a0015_019.txt`, `KR2a0015_020.txt`, `KR2a0015_021.txt`, `KR2a0015_022.txt`, `KR2a0015_023.txt`, `KR2a0015_024.txt`, `KR2a0015_025.txt`, `KR2a0015_026.txt`, `KR2a0015_027.txt`, `KR2a0015_028.txt`, `KR2a0015_029.txt`, `KR2a0015_030.txt`, `KR2a0015_031.txt`, `KR2a0015_032.txt`, `KR2a0015_033.txt`, `Readme.org`

Files only local: `[]`.
Files only upstream: `[]`.
Common files with differing bytes: `[]`.

The upstream repository has no files or explicit main-text headings for
卷三十四–卷一百三十. No re-clone can restore those volumes from Kanripo;
the Wikisource 四庫全書本 witness is therefore registered as the separate
same-edition machine completion source.

## Scan errors

- local: `[]`
- upstream: `[]`

Result: upstream Kanripo coverage is genuinely partial at 卷一–卷三十三.

## Wikisource completion validation

- source directory: `/home/tzhang/projects/shishuoSketch/sources/downloads/jinshu/wikisource-siku`
- lock status: `complete`
- volume records: `130`
- contiguous volume sequence: `yes`
- missing volume records: `[]`
- duplicate volume records: `[]`
- raw/source hash and UTF-8 errors: `[]`
- volumes 1–33 structural alignment: `yes`
- alignment exceptions: `[]`
- retained raw API batch files: `14`

The base page `晉書 (四庫全書本)` is recorded as volume 1; its returned
source includes the volume-one text together with the supplied catalogue
material. Volumes 2–130 use the discovered zero-padded `/卷NNN` pages.

Wikisource heading counts for volume 32 and 33 pages: `{32: 2, 33: 2}`.
Each completion page is a single source page. Kanripo still contains
the previously observed relocated/duplicated 卷三十二/卷三十三 sequence
in `KR2a0015_033.txt`; the completion witness confirms coverage but does
not authorize deduplication or regeneration of the existing units.
