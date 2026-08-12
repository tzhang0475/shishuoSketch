# Jinshu source migration report

Date of migration: 2026-08-12.

This report records the replacement of the incomplete Kanripo machine source
with the complete Wikisource 四庫本. It is a provenance record, not a textual
correction or collation report.

## Former source

- witness: `jinshu-kanripo-wyg`
- former role: `primary-machine-partial`
- repository: `shishuoSources/jinshu/`
- provider: Kanripo
- remote repository: `https://github.com/kanripo/KR2a0015.git`
- commit: `82291520954e5af1fdade894971a2f5810fd4e31`
- verified main-text coverage: 卷1–卷33
- local files: 35 (`KR2a0015_000.txt`–`KR2a0015_033.txt` and `Readme.org`)
- aggregate byte size of all former files: 1,201,562
- SHA-256 inventory: `2d338d1bd66ec4ea99d9aa5b8917b88f4dc5cbfff5a860a8e91a9ef1e17aaf13`

The inventory hash is the SHA-256 of the UTF-8 byte sequence formed by sorted
lines of `sha256(file)`, two spaces, `filename`, and a newline for every file.
The former TXT-only inventory was also checked independently; its aggregate
byte size was 1,198,492 bytes. The source-coverage audit records the explicit
卷32/卷33 duplicate-block anomaly in `KR2a0015_033.txt`; it is not carried
forward as a primary canonical volume.

Before retirement, the former derived corpus contained 34 normalized Markdown
files, 117 structural units, and index SHA-256
`661253480df603582090adb80470762c431d774532d5d27827ee5816c677b103`.
Those derived files are rebuilt below from the new primary; historical reports
that mention their former source path remain unchanged.

## Active source

- witness: `jinshu-wikisource-siku`
- role: `primary-machine`
- edition: 欽定四庫全書本
- provider: Wikisource
- source record: `https://zh.wikisource.org/wiki/晉書_(四庫全書本)`
- local source root: `sources/downloads/jinshu/wikisource-siku/`
- canonical coverage: 卷1–卷130, exactly once
- locked text files: 130
- raw MediaWiki API batches: 14
- locked source byte size: 3,758,164
- concatenated sorted-volume text SHA-256: `b6535a249579f9fa1ec5f2285655b39c19ad28622c757994bc0767123fe06a33`
- `manifest.lock.json` SHA-256: `caa6e48c79af35cfd75fdbcaebc38397d88e404be29f4d35b5aae85ff5f23663`

The lock manifest was verified before processing with zero hash or size
errors. Raw Wikisource files were not edited. Page titles, page IDs, revision
IDs, raw source hashes, and retrieval metadata remain in the lock manifest and
are copied into each normalized-volume record.

## Processing result

The Wikisource pages are normalized by
`scripts/normalize_jinshu_wikisource.py` into 130 UTF-8 Markdown volume files.
Only Wikisource presentation wrappers are removed. Source-visible text,
headings, notes, glyph placeholders, and section information remain either as
text or structured provenance comments. No character, punctuation, or
historical reading was corrected.

The structural parser then uses
`scripts/materialize_jinshu_units.py` to produce volume → category → explicit
textual-unit records. The generated corpus contains 631 units including
catalogue/editorial records; the category counts are recorded in
`content/curated/jinshu/structural-report.md` and the searchable index is
`data/jinshu-unit-index.json`.

The old Kanripo directory was removed from the active repository tree only
after this report and the source audit captured its identity. The critical
《晉書斠注》 and 武英殿 witnesses remain reference-only and were not merged.
