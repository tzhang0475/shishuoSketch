# ShishuoSketch source-processing pipeline

This repository treats `shishuoSources/shishuo` and
`shishuoSources/jinshu` as immutable Kanripo source material.  The first
processing step is deliberately conservative: it makes the files easier to
consume as Markdown without interpreting their historical content.

## What the source inspection found

Both collections contain UTF-8 `.txt` files in Mandoku/Org-style form:

- an Emacs mode line such as `# -*- mode: mandoku-view; -*-`;
- `#+TITLE`, `#+DATE`, and `#+PROPERTY` metadata;
- page markers such as `<pb:KR3l0002_SBCK_002-1a>`;
- source rows ending in `¶`, the Kanripo physical-line terminator.

The source also contains Kanripo character references such as `&KR0680;`.
These references are intentionally kept as literal source text.  They are not
decoded, simplified, or otherwise normalized.

`#+PROPERTY` declarations are not always only a file preamble.  Shishuo has
additional `JUAN`/`FILE` declarations between concatenated source units.  The
normalizer therefore records every declaration in front matter and leaves an
in-band declaration as a Markdown comment at its original source line.

## Shishuo Xinyu structure and limits

The four source TXT files are containers, not a one-file-per-chapter model.
The observed `FILE` values identify the pieces more precisely:

- `KR3l0002_000.txt` contains the preface and the table of contents;
- `KR3l0002_001.txt` begins with `世説新語校語`, then contains the upper
  volume's upper and lower parts;
- `KR3l0002_002.txt` contains the middle volume's upper part and the lower
  volume's upper and lower parts;
- `KR3l0002_003.txt` contains the middle volume's lower part.

The file-level `JUAN` number is therefore a container index, not a complete
chapter identifier.  The repeated `FILE` properties and explicit volume lines
must be retained when a later segmenter assigns source units.

Chapters/categories have visible headings such as:

```text
　　　方正第五¶
　　　　品藻第九¶
```

The ordinal and category name are source text.  A later segmenter may use
these explicit headings as chapter boundaries, but the normalizer does not
rewrite them as synthetic headings.

Individual entries do not have an XML tag, stable entry ID, or delimiter.  An
entry generally begins on a new source row with a name or opening phrase and
continues through subsequent rows.  Those rows are also page-layout rows, so a
row break is not necessarily an entry break.  The source gives no universally
safe machine-readable rule for deciding where every entry ends.

The main-text and annotation relationship is visible but not formally tagged.
The main files introduce the authors as `宋 ... 王義慶 撰` and `梁 劉孝標 注`.
Parenthesized material follows portions of the main text, for example:

```text
陳太丘與友期行...門外戲(並巳見/陳寔及紀)...
```

In the main-text files this parenthesized material is conventionally
annotation-like and is often continued over several rows.  However, there is
no `<note>` or `<liu-commentary>` marker.  The `001` source unit is explicitly
`世説新語校語` and contains editorial comparison material such as
`(宏作閎)`, `(注)`, and correction prose; those parentheses must not be
mistaken for Liu Xiaobiao annotations.  Consequently the normalizer keeps
parentheses, slashes, entity references, and all surrounding text inline.  A
future Shishuo segmenter must record its note-classification rule and its
uncertainty instead of assuming that every parenthesized span has the same
provenance.

## Jinshu boundaries

Jinshu has 34 numbered TXT containers (`KR2a0015_000.txt` through
`KR2a0015_033.txt`).  The file preamble usually has a `JUAN` property, while
the body has explicit headings such as `晉書卷六`.  The repository's
`Readme.org` also provides page anchors, including boundaries such as
`006-30a` for the next juan and anchors for `考證` sections.

A single container can cross a juan boundary.  For example,
`KR2a0015_006.txt` contains the end of 卷六, a 卷六考證 section, and the
beginning of 卷七.  The normalization output remains one Markdown file for
that raw TXT file and retains the headings and page comments in order.  No
relationship extraction, entity linking, or other knowledge inference is done
at this stage.

## Normalizer contract

Run the normalizer from the repository root:

```sh
python3 scripts/normalize_kanripo.py --book shishuo
python3 scripts/normalize_kanripo.py --book jinshu
# or both collections:
python3 scripts/normalize_kanripo.py
```

For every input `X.txt`, the script writes a corresponding
`content/processed/<collection>/X.md`.  Each output has deterministic YAML
front matter containing:

- the repository-relative source path when run from the repository root;
- the source byte length, line count, UTF-8 declaration, and SHA-256 digest;
- all parsed Kanripo properties and all raw source header lines;
- counts of page markers and `¶` terminators;
- explicit text-preservation policy fields.

The body transformation is intentionally small:

1. `<pb:...>` is replaced by an HTML comment containing the exact marker and
   original source line number;
2. a terminal `¶` is removed as a structural line terminator and the source
   row becomes an LF-delimited Markdown line;
3. leading Org metadata is moved into front matter, while metadata encountered
   after source text is retained in a location-preserving comment;
4. all other source characters are copied without Unicode normalization,
   character conversion, punctuation insertion, whitespace trimming, or
   entity decoding.

The source digest makes accidental source changes detectable.  The output is
reversible at the text/provenance level: source rows, headers, page markers,
and their locations are represented, while the file is canonically emitted as
UTF-8 Markdown with LF line endings.  The script refuses an output directory
inside `shishuoSources`.

## Shishuo semantic segmentation

The second stage reads, but never rewrites, the normalized Shishuo Markdown:

```sh
python3 scripts/segment_shishuo.py
```

It inspects every in-band `FILE` directive and the textual headings that
follow it.  The `FILE` value and heading order, rather than the numeric
suffixes of the four container filenames, determine the structural sections.
The stage classifies the preface, catalogue, and `世説新語校語` collation
material as editorial material, and writes them under
`content/processed/shishuo/editorial/`.  The main text is written as
`chapter-01.md` through `chapter-36.md` under
`content/processed/shishuo/chapters/`.

Every generated record carries the normalized filename, source digest,
edition properties, exact `FILE` section, normalized line, inferred source
line, and current Kanripo page marker for its start and end.  Source rows are
copied exactly, including traditional characters and Liu Xiaobiao annotation
text.  Directive lines are represented in provenance metadata and are not
silently treated as chapter content.  The two textual parts of `賞譽第八` are
kept as one canonical chapter with an explicit file-boundary marker.

The segmenter deliberately does not extract people, relationships, or facts,
and does not create individual-entry records.  Since entry delimiters are not
uniformly machine-readable in these files, entry segmentation remains a
future stage for chapters without reviewed anchors.  The generated
`chapters/validation-report.md` lists all 36 canonical headings, their source
positions, missing or duplicate headings, and any structural ambiguities.

## Reviewed entry segmentation: 雅量第六

雅量第六 is the first chapter with a curated entry-boundary manifest:

```text
content/curated/shishuo/boundaries/06-yaliang.yaml
```

The manifest contains 42 human-reviewed, exact opening-text anchors.  An
anchor is searched in the complete chapter body, so it may begin in the
middle of a normalized physical line.  The manifest's source normalized line,
source line, page marker, and confidence are checked against the chapter
before any output is written.

Run the deterministic entry stage with:

```sh
python3 scripts/segment_shishuo_entries.py
```

The output is written only for this chapter under
`content/processed/shishuo/entries/06-yaliang/`.  Each `entry-NNN.md` contains
an exact original-source section, a main-text view, structurally parsed
top-level parenthetical annotation blocks, and traceable Kanripo page-marker
records.  Parentheses are matched with a depth counter; nested parentheses
remain inside their enclosing top-level block.  Physical line breaks and page
markers never create boundaries.

`validation-report.md` records the source and reconstructed body hashes,
balanced-parenthesis counts, page-marker conservation, and manifest-boundary
checks.  The chapter heading is retained verbatim in
`unsegmented-prefix.md`, so concatenating the prefix, all exact entry source
spans, and the suffix reconstructs the complete chapter body.  No people,
relationships, or historical facts are extracted.

## Phase 1 boundary proposals for the other chapters

The remaining 35 chapters have proposal manifests, but they do not yet have
generated entry Markdown.  Regenerate them with:

```sh
python3 scripts/propose_shishuo_boundaries.py
```

The script reads every normalized chapter and resolves the configured
structural-reference witness from `config/sources.yaml`.  The migrated local
witness is `sources/local/shishuo/reference-txt/shishuo.txt`; it is used only
as a read-only structural guide for entry order and approximate alignment.
ICU conversion is used only for that comparison; no converted text is
emitted.  ICU's `uconv` command must be
available on `PATH`, so a missing conversion tool cannot silently change the
result.  Every `opening_text` is an exact
substring of the traditional normalized chapter body, and every proposed
boundary records its normalized filename, `FILE` section, source positions,
page marker, edition metadata, confidence, and `review_status: "auto"`.

The manifests are written to
`content/curated/shishuo/boundaries/01-*.yaml` through
`content/curated/shishuo/boundaries/36-*.yaml`, excluding the existing
reviewed `06-yaliang.yaml`.  The report
`content/curated/shishuo/boundaries/boundary-review-report.md` lists counts,
all medium- and low-confidence anchors with source context, duplicate-anchor
checks, structural exceptions, and chapters requiring manual review.  Known
guide/source omissions are reported rather than silently converted into
boundaries.  The command never writes normalized chapters or any entry
Markdown, and it does not perform entity, relationship, summary,
translation, or historical extraction.

The local structural-reference witness has unresolved edition and
transcription provenance.  Its migration metadata records its byte-level
fingerprint and explicitly keeps its text authority low.  Reports generated
before the migration may continue to refer to the former
`content/shishuo.txt` path; those historical reports are not rewritten.

## Human review queue

Render the review queue without changing any manifest or source chapter:

```sh
python3 scripts/render_shishuo_manual_review.py
```

This writes `content/curated/shishuo/boundaries/manual-review.md`.  It
includes every medium- and low-confidence proposal, followed by deterministic
first/middle/last eligible high-confidence samples from structurally unusual
chapters 05, 08, 18, 19, and 25.  The excerpts are contiguous slices of normalized
chapter bodies and retain parenthetical annotation text, page-marker comments,
traditional characters, punctuation, and whitespace exactly.  If a chapter
does not contain the requested amount of surrounding source text, the
available amount is shown and reported; no text is invented.

## Staged data flow

The intended processing boundary is:

```text
raw source
  shishuoSources/{shishuo,jinshu}/*.txt
        │  normalize_kanripo.py
        ▼
normalized source
  content/processed/{shishuo,jinshu}/*.md
        │  segment_shishuo.py (Shishuo only)
        ▼
segmented source
  content/processed/shishuo/{chapters,editorial}/ records with provenance;
  reviewed entries for 雅量第六 only; curated boundary proposals for the
  other 35 Shishuo chapters; no new entry Markdown yet
        │  future, conservative extraction with evidence pointers
        ▼
extracted knowledge
  future data/extracted/ records; every claim must point back to a
  normalized source file and page marker
```

The segmentation and extraction directories are described here as future
stages; this task does not create inferred historical facts or a web UI.

## Tests and rollout

The tests use only small Shishuo and Jinshu fixtures and check page-marker
conversion, repeated metadata, literal traditional text/entity preservation,
juan retention, and the source-tree write guard:

```sh
python3 -m unittest discover -s tests -v
```

Run those tests before processing the full corpus.  Re-running the normalizer
with the same source bytes produces the same Markdown bytes.
