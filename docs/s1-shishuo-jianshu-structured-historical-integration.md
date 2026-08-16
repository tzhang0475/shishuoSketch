# S1 — Shishuo Jianshu Structured Historical Integration

S1 adds the locally supplied 《世说新语笺疏》 EPUB/PDF pair as a named
scholarly working-reference family. It is a source-integration milestone, not
an edition-authentication or textual-criticism project.

The existing Kanripo/SBCK witness remains the primary Shishuo machine text.
The local EPUB is the machine-readable reference; the local PDF is the
selective page/glyph fallback for the same work. The existing external CText
registration remains present, but S1 does not depend on CText authentication
or HTML retrieval.

## Source registration and cache boundary

The two ignored binary payloads are registered with stable local paths, byte
sizes, SHA-256 values, and source-family IDs. The EPUB lock records its OPF
metadata and ordered spine. The PDF lock records page count and the result of
the text-layer probe. The existing Kanripo primary payload is also checked
against its committed provenance lock before S1 registration. No publication
or digital-edition authenticity claim is made from these metadata fields.

The deterministic cache lives under:

```text
.cache/shishuo-reference/jianshu/
```

It contains the full parsed Story records, chapter index, citation blocks,
alias-appendix detection, parse metadata, and a compact PDF page index. Full
Jianshu text is not copied into tracked repository data. Tracked artifacts
contain hashes, locators, short evidence spans, structural statistics, and
candidate assertions only.

## Structured ingestion

The EPUB is parsed in OPF spine order, never arbitrary filesystem order. XHTML
blocks retain their source locator and are classified as:

```text
base_text
liu_annotation
collation_note
jianshu_note
appendix
unknown
```

The inline Liu layer is represented conservatively as marker-delimited
structural segments; it is not presented as an emended or canonical
re-segmentation. Explicit attributions such as 程炎震、李慈銘、李詳、嘉錫案
remain attached to their blocks. Unattributed notes are not assigned an author
by inference.

S1 detects all 36 Shishuo categories and the complete 1,130-entry structural
coverage of the local EPUB. It also audits replacement symbols, `●`
placeholders, Private Use Area characters, and control characters. These are
reported, not automatically repaired. The PDF is consulted selectively when a
glyph affects a high-value Story, identity, meaning, or boundary.

## Story alignment and editorial policy

Alignment is keyed by canonical chapter and entry ordinal. Text comparison is
secondary verification, not a fuzzy replacement for Story identity. The
alignment output covers all current production Stories and exactly the frozen
20-Story X1.1 review batch; no new Story selection occurs.

S1 introduces this prospective editorial policy:

> A reliably aligned Jianshu Story with usable editorial segmentation is
> sufficient scholarly punctuation/segmentation evidence unless a difference
> changes identity, meaning, or Story boundary.

The policy does not change canonical Shishuo characters. Known minor variants
remain visible as source differences. Meaningful variants and structural
ambiguity remain review-required. X1.2P remains a frozen record of the earlier
two-tier policy and is not rewritten.

## Alias and historical candidates

S1 extracts alias candidates from explicit `字`, `小字`, `別名`, and `一名`
surfaces, including the detected common-name appendix. Each candidate is
compared with the existing `data/people.json` and `data/aliases.json` layer
and receives an explicit `existing_mapping`, `ambiguous`, `conflict`, or
`new_candidate` state. Extraction never creates a Person or edits the global
alias index; all candidates remain review-required.

Historical assertions preserve:

```text
Story
source layer
explicit attribution when present
source locator
evidence excerpt and hash
candidate fact domain
modality
candidate status
```

Quoted historical sources, a Liu annotation, a scholarly assertion such as
嘉錫案, and a canonical ShishuoSketch fact remain distinct. Modality such as
疑、或、未詳、當作 and probable/disputed readings is retained. The extracted
citation artifact is a future source-expansion map; S1 does not ingest the
cited 晋书、晋阳秋、中兴书、谱 or other works.

## Backlog re-resolution

The frozen X1.1 set is re-opened without re-ranking. In the current local
payload:

* all 20 selected Stories have aligned Jianshu editorial segmentation and
  therefore clear the former punctuation-reference bottleneck;
* none is released into canonical production in S1 because the existing
  participant-review gate was explicitly deferred in X1.2A;
* all 58 punctuation-blocked facts remain unresolved because their candidate
  records do not specify a complete, safe historical endpoint/semantic claim;
* all 3 unresolved identity candidates remain unresolved because generic
  title occurrences still lack occurrence-level identity evidence;
* the protected X1.2A extension remains unchanged: 9 accepted extension facts
  and 3 entities.

This is intentional. Jianshu resolves the source-policy bottleneck; it does
not lower participant, identity, or historical-fact standards. Two selected
Stories with relevant EPUB glyph anomalies received selective PDF page
lookups. No canonical text was changed.

## Materialization boundary

The S1 flow is:

```text
local Jianshu payloads
    ↓
registration and deterministic cache
    ↓
Story alignment / candidate extraction
    ↓
review state: accepted / unresolved / rejected
    ↓
accepted-only canonical extension
```

The current run materializes no new Story, Person, fact, or entity. This is
safer than treating a Jianshu note or a model-era candidate as a canonical
assertion. The release manifest is explicit and empty; it is not an implicit
drop of unresolved records.

## Remaining blockers and future implications

The immediate remaining Story blocker is reviewed participant semantics for
the out-of-scope batch. The historical backlog additionally needs endpoint-
level review for family, office, event, geographic, temporal, and
service/political candidates. Generic titles such as 王丞相 and 王公 remain
collision surfaces. PUA glyphs remain an audit queue rather than a silent
repair queue.

Future X1 candidate metadata now distinguishes Jianshu reference availability
from the other production gates. An aligned Story may be punctuation-ready
without being publication-ready. S1 does not select X1.2B Stories and does
not introduce new ontology relations.

S1 explicitly does not implement X1.2B, HG1.1, ML1.1, ER2, UX1, bulk cited-
source ingestion, political-faction inference, or any graph/ML work.
