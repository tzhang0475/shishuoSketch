# WP1 data conventions

## Stable IDs

IDs are opaque, assigned identifiers. They are never generated from a
person's name, a title, a URL, or generated text. Story IDs such as
`06-yaliang-019` remain independently assigned and are not affected by Person
ID allocation.

Production Person IDs use the current format `person-NNN`. They are allocated
once and then frozen: canonical names, aliases, URLs, and Simplified or
Traditional display changes never change a `person_id`. Identity merges and
splits require an explicit migration; an old ID is never silently reused for
a different identity. P-ID1 freezes `person-001` through `person-017`; M2A
allocates the frozen Wave-2 range `person-018` through `person-035`, and the
next available production sequence is `person-036`. The one-time migration
manifest preserves former name-slug IDs only as historical traceability; they
are not alternative production IDs and must not occur in active Person foreign
keys.

IDs are unique within an object type and should also be globally unique in a
published data bundle. Human-readable labels belong in separate fields.

## Aliases

`Person.canonical_name` is the identity label. `Person.aliases` stores observed
surface forms separately, with an alias type, resolution mode, and evidence
references. Orthographic variants remain distinct strings; the source text is
never rewritten to match a canonical name.

## Dates and periods

Dates use a small explicit status: `exact`, `range`, `approximate`, or
`unknown`. Missing dates are represented by `null` values and `unknown`, not by
invented years. A period label may be supplied when the source or reviewed
scope supports it.

## Locations

Locations are source-backed labels with evidence references. A location name
does not imply a modern geocoding or a precise historical boundary. Unknown
locations are omitted or represented with an explicit unresolved status.

## Evidence references

Evidence is a separate object. Claims refer to Evidence IDs rather than
embedding untraceable quotations. Evidence locators have two explicit layers:

* `artifact_path` and `artifact_sha256` identify the exact derived entry or
  Jinshu unit containing the quoted text;
* `source_provenance.source_path` and `source_provenance.source_sha256`
  identify the upstream witness artifact, together with its `witness_id`.

The path and hash within each layer must identify the same file. A Shishuo
locator uses `entry_id` and a Jinshu locator uses `unit_id`; the validator
checks these IDs, paths, metadata, hashes, and exact quote containment against
the canonical indexes and files. Derived text may be copied into a static
bundle only by a reproducible builder and must retain this full provenance
chain.

Provenance validation has two explicit modes:

* `python3 scripts/validate_wp1.py --mode full` is the default local-research
  mode. It requires every upstream source payload and recomputes its hash.
* `python3 scripts/validate_wp1.py --mode portable` is for clean CI checkouts.
  A missing upstream payload is accepted only when its exact path, witness, and
  SHA-256 occur in committed trusted metadata (the relevant lock manifest or
  source provenance lock) and that metadata explicitly identifies an ignored or
  external payload. Canonical derived artifacts are still required physically
  and are always hashed from disk in both modes.

The portable mode verifies identity; it does not treat a missing payload as
validated text and never copies or substitutes source content.

## Relations

Relations are one semantic edge, using the existing `subject_id` and
`object_id` fields rather than duplicated forward/reverse records. Hard
relations may declare a `relation_subtype`, `role_a`, and `role_b`; source
entry/unit IDs identify the canonical anchors in addition to the resolving
Evidence IDs. Reviewed R1 relations are limited to directly supported kinship
and marriage edges. `relation_basis: direct` identifies a directly attested
edge and requires direct Evidence; `relation_basis: derived` identifies a
deterministic path over reviewed direct relations and uses
`derived_from_relation_ids` instead of an additional quotation. Symmetric
spouse edges use one canonical endpoint order.
Co-occurrence, shared surnames or titles, and graph transitivity never create a
reviewed relation by themselves.

The unified `data/people.json` registry is the Person identity source of truth.
Its `scope_role` is `primary` for materialized production Persons (including
the six-person bootstrap and later P3B waves) or `supporting` for a minimal
evidence-backed bridge Person. WP1 annotation records are generated
projections of this registry; scope does not change identity or evidence
semantics.

## Person Sketch v1

`Person` and `Person Sketch` are separate layers. `data/people.json` remains
the canonical identity registry. `data/annotation/person-sketches.json` owns
only a small evidence-backed reader-facing identity capsule for the current
scope; aliases are projected from `data/aliases.json` and Shishuo Mentions,
Stories from the PersonStory index, and relations from the canonical Relation
layer. The sketch layer must not copy relation facts or redefine PersonStory
links.

Each scoped Person has exactly one sketch. Structured identity fields and any
non-empty `brief_intro` require resolving Evidence IDs; the capsule is bounded
and contains no personality interpretation or encyclopedia biography. Alias
rows retain exact/contextual/ambiguous resolution semantics and distinguish
main-text from Liu-annotation observations. Newly assembled capsules remain
`candidate` unless an existing editorial review record explicitly supports
`reviewed`. OpenCC creates only the derived Simplified display form.

## P3B materialized Person expansion

The six-person pilot is a legacy/bootstrap builder, not the production
registry writer after a materialization wave exists. P3B freezes a deterministic
P3A ranking in a reviewed wave manifest, then projects approved candidate
identity evidence and occurrence records into the unified Person, Alias,
Mention, Evidence, PersonStory, and Person Sketch layers. New records retain
`candidate` review status and candidate provenance; materialization is not
human review. Exact and contextual surface associations remain distinct, and
contextual or unsafe occurrences are retained as withheld review data.

P3B does not create Relations from co-occurrence, does not publish additional
Stories, and does not modify canonical text, punctuation, or raw witnesses.
Future waves reuse the materialization path with a new frozen manifest; Wave 1
selection is never recomputed from the post-materialization ranking. M2A uses
a separate experience ranking and Story expansion manifest: the original SC0
Gold Set remains immutable, while the frontend publication set is the
deterministic union of SC0 and the selected expansion Stories. Wave-2 Person
selection and Story selection are allocation decisions, not historical review;
newly materialized records remain candidate unless a later explicit review
changes that state. The allocation state artifact records the next sequence
and every assigned Person ID so later waves cannot derive IDs from names or
incidental ordering.

## S1 Story Scene Context layer

`data/annotation/story-scene-contexts.json` is a Story-owned candidate
context layer. It describes a specific scene's supported date/place/person
roles/status/background and does not redefine Person identity, PersonStory,
Mention, or Relation. `scene_role: present` requires scene-specific Evidence;
co-occurrence and PersonStory presence are not enough. Contextual position is
not a historical Relation. Dates and ages use explicit exact/range/approximate/
unknown states; age derivation never invents a single year. The deterministic
SC1 projection is `scene_contexts`, keyed by existing Story IDs, and is shown
by the central Story Scene Card only for the pilot Stories. New claims begin as
`candidate` and retain Evidence IDs; the current SC1 pilot covers only a
reviewed selection of the published Stories. The separate
The S1.1 expansion currently covers a bounded 20-Story selection inside the
published experience set; it does not imply that every published Story has a
Scene Card. The separate `data/annotation/person-relation-candidates-r3.json`
layer is an R3A review
artifact only: its source-backed proposals are not production Relations and
are not shown in the reader-facing Relation card until a later explicit review.

The Person-first “随便认识一个人” entry uses only materialized Persons with a
Person Sketch and a connection to a published Story in the generated SC1
bundle. It uses the shared exploration stack and an injected random function in
the pure helper for deterministic tests; it does not create a Person directory
or a second focus state.

## Assertion status

Every historical or interpretive assertion uses exactly one of:

* `attested` — directly present in the cited source;
* `reported` — reported by a cited source rather than directly witnessed by
  the project;
* `inferred` — a reasoned interpretation from cited evidence;
* `unknown` — not established in the current data.

Assertion status is not a confidence score.

An `attested` record with an `evidence_ids` field must have at least one
resolving Evidence ID. The validator enforces this invariant; it does not
permit an empty evidence list merely because a record is still a candidate for
review.

## Review status

Review status describes the data workflow:

* `candidate` — generated or proposed, awaiting human review;
* `reviewed` — checked for the current scope;
* `rejected` — explicitly excluded;
* `todo` — known work not yet started.

AI- or script-generated records begin as `candidate`; they do not become
historical facts merely because they validate against JSON Schema.

## Unresolved ambiguity

When a mention cannot be safely resolved, `person_id` is `null`, candidates
remain in `candidate_person_ids`, and `assertion_status` is `unknown`.
Contextual titles such as `太傅`, `丞相`, and `王公` must not be resolved by
string matching alone.

## Generated versus reviewed data

Raw and canonical source files are immutable inputs. `data/annotation/` holds
reviewable annotations and candidates. `data/derived/` is the reproducible
research-side build output, while `site/src/generated/` is the Vite build
input generated from that same bundle. They are synchronized by the builder
and exact-identity validation; the frontend does not publish a separate
runtime JSON copy. The WP1 sample builder records its input entry path and
source hashes; it does not edit the source entry.

## CRL1 corpus reading layer

`data/annotation/wp1-punctuation.json` is the single punctuation-record
architecture for both the reviewed WP1 sample and the corpus-wide CRL1
assessment. The existing `06-yaliang-019` record is preserved as a human
reviewed override. CRL1.1 keeps `review_status` (`reviewed` or `unreviewed`)
separate from `punctuation_basis` (`human_reviewed`,
`trusted_reference_exact`, `reference_candidate`, or `disputed`). The legacy
`status` field remains for compatibility; it is not a substitute for the
orthogonal review/basis fields.

The CRL1 build is:

```text
canonical entry Markdown
    ↓
local structural TXT punctuation guidance
    ↓
character-alignment assessment
    ↓
data/annotation/wp1-punctuation.json
    ↓
data/derived/shishuo-reading-layer.json
    ↓
OpenCC t2s display form
```

The local structural TXT is not textual authority. Character alignment may
use a comparison-only Traditional-to-Simplified key, but derived punctuation
is inserted at canonical offsets and must round-trip to the canonical
sequence. The Wikisource SBCK comparison view is a same-edition alignment
reference; because it currently contains no sentence punctuation, it does not
count as a second punctuation reference.

`exact_transfer: true` means that the transferred reference punctuation strips
to exactly the canonical character sequence. It is a technical alignment fact,
not editorial approval. `data/reading-source-qualification.json` records the
source qualification. The local TXT is currently
`provisionally_qualified` for transfer analysis only, so its exact transfers
remain `reference_candidate` until the source is editorially qualified. A
candidate is never reader-ready merely because OpenCC output exists.

`story_reader_ready` means only that main-text punctuation has
`review_status: reviewed` with `punctuation_basis: human_reviewed`, or an
explicitly qualified `trusted_reference_exact` basis, the canonical round-trip
passes, and OpenCC simplification succeeds. Liu Xiaobiao annotation coverage is tracked separately by
`annotation_reader_ready` and does not block CRL1 main-text readiness.

Run the deterministic build and derived-layer validation with:

```bash
npm run build:reading-layer
WP1_PROVENANCE_MODE=full npm run validate:reading-layer
WP1_PROVENANCE_MODE=portable npm run validate:reading-layer
```

The generated human-review queue is
`content/curated/shishuo/reading-layer/review-queue.yaml`, with a Markdown
view beside it. Entries with `candidate` or `disputed` status remain queued;
the builder never guesses punctuation to increase reader-ready coverage.

## Person ↔ Story indexing

`data/derived/person-story-links.json` is deterministic navigation data derived
from resolved Shishuo Mentions. It does not replace the Story or Person model
and does not make a historical participation assertion. `main_text` and
`liu_annotation` are retained as separate source layers; this pilot uses
`presence_kind: mentioned` for both. `participant` requires a later explicit
review decision and must be supported by a main-text Mention.

`data/derived/person-story-index.json` projects reviewed links into ordered
Person → Story references. Contextual or ambiguous Mentions remain candidate
evidence and are never promoted by co-occurrence, Relation edges, Jinshu
biographies, or semantic similarity. A linked Story is `reader_ready` only
when its canonical entry, reviewed punctuation, original/simplified reading
layer, and reviewed resolved Person link all exist.

## SC0 Story Chain Gold Set

`data/story-chain-gold-set.json` is a small editorial selection over existing
reviewed PersonStoryLinks. It contains no story text and creates no historical
assertion. The selection prefers deterministic main-text Person presence and
connected multi-person coverage; Liu Xiaobiao annotation-only Persons remain
separately identified as context. New records are `candidate_for_review` until
the existing punctuation review workflow approves them.

`data/derived/story-chain-gold-index.json` projects the selected Stories to
their existing Person IDs for a future reading surface, while
`data/derived/story-chain-connectivity.json` is the reproducible selection
audit. Neither artifact creates relation edges or participation claims.

## P3A Person expansion candidates

`data/derived/person-expansion-candidates.json` is a deterministic analysis
artifact for deciding which non-scoped historical identities might be useful
to materialize in a later expansion phase. It reads existing resolved
Mention, Alias, Relation, PersonStory/SC1, and source-evidence data; it does
not create Person records, Relations, PersonStory links, or publication
records.

Only an existing non-scoped `person_id` supported by structured project data
can enter the ranked identity universe. Unresolved surfaces such as generic
titles remain in the separate
`data/derived/person-expansion-unresolved-surfaces.json` audit and are never
ranked as Persons by frequency or co-occurrence.

The ranking stores raw metrics and normalized components. Current Story
coverage and Story-unlock potential use resolved Shishuo mentions; main-text
presence has greater weight than Liu-annotation-only presence. Shared Story
appearance is a navigation opportunity, not a historical Relation. Direct
connectivity counts only reviewed direct Relation records; derived Relations
and co-occurrence are kept separate.

The score uses explicit bounded linear normalization and fixed weights in the
generated artifact. Candidate keys have the form `candidate:<existing-id>` so
they remain analysis keys rather than prematurely becoming canonical Person
IDs. P3A does not expand the frontend or mutate canonical/research data.

## P3A.1 Open-world Person identity discovery

`data/derived/person-identity-candidates.json` is the reviewable discovery
artifact that precedes P3A. It starts from processed Jinshu biography-unit
subjects and explicit local identity cues, then attaches conservative Shishuo
main-text and Liu Xiaobiao annotation surface evidence. A surface is not an
identity: generic forms such as `太傅`, `王公`, and `丞相` remain unresolved
surface clusters unless an explicit local identity bridge supports a
contextual association.

`data/derived/person-candidate-occurrences.json` contains exploratory
occurrences for new candidates only. It is deliberately separate from
`data/mentions/*.json`: P3A.1 never writes canonical Person IDs, Mention
resolutions, Relations, PersonStory links, Person Sketch records, or
publication state. Existing registry matches are retained in the discovery
artifact as `already_materialized` rediscovery controls.

Only `strong_candidate` records are eligible for the existing P3A ranking by
default. P3A adapts their deterministic candidate keys for ranking without
turning them into production Persons; human review and a later P3B
materialization step remain required. Rebuilds sort candidate IDs, surfaces,
evidence, Story IDs, and source layers explicitly so the JSON and review report
are byte-deterministic.
