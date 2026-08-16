# Historical-source witness policy

The repository keeps each historical work as a set of named witnesses. A
witness is an identifiable edition or derivative with its own provenance; it
is never silently replaced by another witness.

`shishuoSources/` remains the local upstream Kanripo area. It is ignored by
the repository Git configuration and is treated as immutable source material.
The registry files in `sources/registry/` describe the witnesses, while
`config/sources.yaml` gives future processors repository-relative roots.

## Authority and use

“Primary” means the default diplomatic machine-text witness for processing.
It does not claim that the witness is philologically superior for every
reading. Secondary, critical, structural, and visual witnesses remain
distinct and are used for:

- missing-text detection;
- structure comparison;
- boundary verification;
- variant detection; and
- page-level visual checking.

OCR is a convenience derivative for search and alignment only. It is not
textual authority and must never silently replace diplomatic source text or
page-image evidence. Large scans and other downloaded payloads remain
outside Git; their exact URL, filename, size, retrieval time, and SHA-256 are
recorded in `manifest.lock.json` files.

A canonical segmentation is not a canonical reconstructed text. If a future
editorial decision emends or resolves a reading, the record must preserve the
witness identity, exact evidence, source location, and resolution rationale.

## Processing layers

The intended data flow is:

```text
raw witnesses
    ↓
witness normalization
    ↓
alignment
    ↓
discrepancy audit
    ↓
structural resolution
    ↓
canonical segmentation
    ↓
mentions / people / relations
```

The current Shishuo normalization and segmentation outputs retain their
existing provenance strings. The new registries and configuration provide
future source lookup without rewriting those historical outputs.

The local Shishuo structural-reference witness is stored at
`sources/local/shishuo/reference-txt/shishuo.txt`. Its edition, publisher,
transcription source, and date are unresolved; the metadata records only
verified byte-level facts and its migration history. It has high structural
authority for entry-count comparison, entry-boundary comparison, missing-entry
detection, and structural anomaly detection, but low text authority. It must
not silently replace the primary Kanripo/SBCK diplomatic witness. Historical
reports generated before migration may still refer to the former
`content/shishuo.txt` path.

## Shishuo witness hierarchy

For Shishuo Xinyu, the active hierarchy is:

1. Kanripo/SBCK — primary machine witness;
2. Wikisource 四部叢刊本 — same-edition machine reference;
3. 1615 凌氏刻本 — secondary OCR plus visual witness;
4. 四庫全書本 — independent secondary witness;
5. local `shishuo.txt` — structural reference; and
6. 余嘉錫《世說新語箋疏》 — a named scholarly-reference family. The
   user-provided local EPUB is the machine-readable working reference and the
   local PDF is its visual/page fallback; both remain separate from the
   primary witness and share one source family.
7. Chinese Text Project's external Jianshu registration — retained as an
   external reference and not required for local S1 processing.

The Wikisource 四部叢刊 section declarations and their referenced
Page-namespace wikitext are retrieved through the MediaWiki API as-is for
alignment and search; revision IDs and hashes are locked. The 1615 凌氏
files are discovered through Internet Archive metadata/search. Its OCR is a
convenience derivative only; its PDF/page image is the verification
authority, and JP2 archives are not downloaded by default. The 四庫本 remains
a separate textual/version comparison. The local structural reference
assists entry-count and boundary comparison. The local 余嘉錫《世說新語箋疏》
EPUB/PDF pair is a scholarly working reference: the EPUB supplies deterministic
machine structure and the PDF supplies selective page verification. It is not
a textual witness and must not replace the primary text. The external CTP
registration remains separately recorded for future reference, but S1 does
not depend on CText authentication or scrape its HTML/API output. No
secondary witness authorizes overwriting the primary Kanripo/SBCK text.

## Jinshu source coverage and migration

The active Jinshu primary is `jinshu-wikisource-siku`, the complete
`晉書 (四庫全書本)` machine witness retrieved through the Wikisource
MediaWiki API. It covers 卷一至卷一百三十. Exact API JSON batches, returned
UTF-8 source text, page IDs, revision IDs, retrieval dates, byte sizes, and
SHA-256 values are recorded under
`sources/downloads/jinshu/wikisource-siku/`. The normalization and structural
unit stages use this witness only; no secondary reading is merged into it.

The former local Kanripo `KR2a0015` witness is retained in the registry as an
inactive historical primary with verified main-text coverage of 卷一至卷三十三.
Its upstream repository has the same 34 text containers and does not contain
卷三十四至卷一百三十; the catalogue's statement that the work has 130卷 is
not treated as surviving machine-text coverage. Its previous repository
identity, commit, byte size, and SHA-256 inventory are recorded in
`content/curated/jinshu/source-migration-report.md`. Historical reports that
mention `shishuoSources/jinshu` are left unchanged.

The critical 《晉書斠注》 witness and the externally hosted 武英殿 witness
remain reference material. They are not merged into the primary text.

The next collation stage will use, without resolving them here, the known
anomaly set:

- 05-fangzheng #14;
- 08-shangyu #84 and #85;
- 18-qiyi #2 and #11;
- 19-xianyuan #5;
- 18-qiyi-010 and 18-qiyi-015; and
- 25-paidiao-019.

## Download policy

`scripts/download_witnesses.py` uses Internet Archive metadata rather than
HTML scraping. It verifies item titles, chooses files deterministically,
streams to temporary files, calculates SHA-256, and refuses to overwrite an
existing file with a different digest. The Chinese Text Project 武英殿
witnesses are registered as externally hosted visual references only; they
are not bulk-scraped by this repository.
