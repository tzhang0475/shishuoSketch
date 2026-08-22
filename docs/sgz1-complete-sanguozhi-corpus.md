# SGZ1：完整《三國志》结构化语料

SGZ1 completes the repository's machine-readable 《三國志》 evidence layer
without promoting any source passage into a Person, Relation, Event, or
canonical historical fact.

## Why SGZ0 had 30 juan

SGZ0 processes `sanguozhi-kanripo-wyg`, whose local `KR2a0012_001`–`030`
payloads are the WYG/文淵閣《魏書》三十卷 portion. They are not a 65-juan
witness with missing files. SGZ0 now declares its coverage explicitly as:

```text
三國志 / 魏書 / global juan 1–30 / section juan 1–30
```

SGZ1 supplies the remaining sections through a separate complete machine
witness.

## Witness architecture

| Section | Global juan | Machine witness | Visual/reference witness |
| --- | --- | --- | --- |
| 魏書 | 1–30 | Kanripo/WYG and Wikisource | 南宋刊本（宋內府書陵部本） |
| 蜀書 | 31–45 | Wikisource | 南宋刊本（宋內府書陵部本） |
| 吳書 | 46–65 | Wikisource | 南宋刊本（宋內府書陵部本） |

The Wikisource source uses the observed pages `三國志/卷01` through
`三國志/卷65`. The downloader records each page id, revision id, revision
timestamp, API URL, source URL, raw-source path, and SHA-256 in
`sources/downloads/sanguozhi/wikisource/manifest.lock.json`.

Raw API JSON and wikitext remain outside Git. The tracked lock and metadata
files make the local payload reproducible when it is available.

## Author layers

The Wikisource pages use an explicit `{{*|...}}` template for Pei Songzhi
notes. Substantive text outside that marker can be assigned to Chen Shou;
the observed Wikisource page/editorial markup is retained separately without
an author layer:

```text
{{*|...}} → layer = pei_annotation, author_layer = 裴松之
substantive text outside the marker → layer = main_text, author_layer = 陳壽
page/editorial markup → layer = metadata, author_layer = null
```

This includes the recognized page headers, magic words, section headings,
include wrappers, footer/page templates, and category links. The markup is
not deleted or normalized: assigning it to `metadata` is structural and
provenance handling, not source-text editing. If a future source has no safe
structural annotation marker, SGZ1 keeps the body as `unparsed` and assigns no
author layer; it never invents a boundary from punctuation or parentheses.

Raw source text, source spans, page coordinates, revision provenance, and the
processed projection are all retained. The source is not simplified or
silently corrected. The South-Song OCR remains a non-authoritative search and
alignment derivative; page images are its visual verification authority.

## Build and validation

```bash
python3 scripts/download_witnesses.py --sanguozhi-wikisource
python3 scripts/build_sgz1_corpus.py
python3 scripts/validate_sgz1.py --mode portable
python3 scripts/validate_sgz1.py --mode full
```

The derived corpus is `data/derived/sgz1-sanguozhi-complete-corpus.json`,
with one deterministic Markdown projection per juan under
`content/processed/sanguozhi/sgz1/`. SGZ1 validates exactly 65 records:

```text
魏書 30/30
蜀書 15/15
吳書 20/20
```

SGZ1 is evidence infrastructure. Completion does not automatically create
historical facts, graph edges, Persons, Relations, Events, PersonStory links,
or Mentions.
