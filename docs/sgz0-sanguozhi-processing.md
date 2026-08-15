# SGZ0：三国志 / 裴松之注处理层

SGZ0 adds a deterministic, provenance-preserving processed layer for the
locally registered `sanguozhi-kanripo-wyg` witness. It is evidence
infrastructure for W3; it does not create production Persons, Relations, or a
chronological graph.

## Observed local grammar

The local files under `shishuoSources/sanguozhi/` are Kanripo/Mandoku text,
not the Shishuo Markdown grammar:

- `#+PROPERTY: JUAN ...` declares the juan; `KR2a0012_000.txt` is front matter.
- `<pb:...>` is a physical page marker and is retained in source coordinates.
- `¶` is the witness physical-line marker. It is removed only from the
  convenience `text` projection; `raw_text`, character offsets, line numbers,
  and source hashes remain intact.
- Balanced parenthesized spans are the observed Pei Songzhi annotation layer.
  The local files have one-level balanced spans; malformed balance is a hard
  parser error.
- No `FILE` directives were present in the inspected local files. File
  identity is therefore carried by the registered filename and provenance
  record rather than inferred from a guessed directive.
- Text outside parenthesized spans is assigned to 陈寿正文; parenthesized
  spans are assigned to 裴松之注. This is a structural layer split, not a
  claim that every internal cited work has been parsed.

## Artifacts

- `scripts/build_sgz0_corpus.py` — deterministic parser and renderer.
- `data/derived/sgz0-processed-corpus.json` — source-linked units and hashes.
- `content/processed/sanguozhi/` — one front-matter file plus the locally
  available volume projections.
- `sources/registry/sanguozhi-provenance.lock.json` — exact source witnesses
  and SHA-256 locks.
- `scripts/validate_sgz0.py` — full/portable validation.

The current checkout contains the registered local files for volumes 1–30
plus front matter. Volumes 31–65 are recorded as unavailable; no ignored
payload was downloaded or fabricated. Full validation verifies every present
payload. Portable validation verifies the lock and processed artifact when an
external upstream payload is absent.

Current processed counts:

- 30 volume files
- 1,308 陈寿正文 units
- 6,526 裴松之注 units

Each unit retains `source_file`, source SHA, character span, source line
range, page markers, `raw_text`, normalized `text`, `layer`, and
`author_layer`. `cited_work` is conservatively `unparsed` unless a future
reviewed parser can distinguish it without flattening Pei's own connective
text and quoted material.

## Use in W3

W3 uses the processed corpus as a registered evidence surface and preserves
the distinction when documenting identity/period limitations. The reader
still starts from a 世说故事; long Sanguozhi passages are not inserted into
the Story reader. A future chronology stage may use these units, but SGZ0 does
not implement H0, P4, ES0, Clan, Circle, or HistoricalEvent data.
