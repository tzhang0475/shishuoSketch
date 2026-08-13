# Static frontend data interface

The frontend is static-first. The deterministic WP1/SC1 builders generate
frontend bundles under `site/src/generated/`, and the Vite application imports
the active SC1 bundle at build time. The browser does not fetch a separately
cached JSON URL. Code and frontend data therefore enter the same hashed
production assets and are deployed atomically; users do not need a hard
refresh or cache-busting query parameter after deployment.

`data/derived/wp1-site.json` is the research-side derived archive of the same
builder output. It is not an independently maintained frontend source: the
builder writes both files from one bundle and validation requires exact JSON
identity. Canonical and research/source data remain outside the frontend
artifact.

The bundle contains these arrays:

```ts
{
  schema: 1,
  generated_from: string,
  stories: Story[],
  people: Person[],
  mentions: Mention[],
  relations: Relation[],
  eras: Era[],
  evidence: Evidence[],
  sources: Source[],
  story_chain?: {
    story_ids: string[],
    person_story_refs: Array<{
      person_id: string,
      story_ids: string[],
      main_text_story_ids: string[],
      liu_annotation_only_story_ids: string[]
    }>,
    story_person_refs: Array<{
      entry_id: string,
      linked_person_ids: string[],
      main_text_person_ids: string[],
      liu_annotation_only_person_ids: string[],
      publication_state: "production_ready" | "preview_ready" | "blocked"
    }>
  }
}
```

The bundle is generated from the canonical Shishuo entry, the six primary
people, and any explicitly marked supporting R1 bridge records by
`scripts/build_wp1_sample.py`. It is not a second source text authority.

Evidence records expose an exact derived-artifact locator (`artifact_path`,
`artifact_sha256`, and either `entry_id` or `unit_id`) plus separate
`source_provenance` for the upstream witness path, witness ID, and source hash.
The frontend treats both as metadata; it does not resolve or parse raw source
files at runtime.

The current prototype is served under the configured `/shishuoSketch/` base
path in local preview and on GitHub Pages. It intentionally does not introduce
client-side routing yet. The object IDs and cross-object references remain
available in the bundle for later reading surfaces.

## SC1 Story Chain projection

The deployed reader imports `site/src/generated/sc1-site.json` at Vite build
time. `scripts/build_sc1_frontend_data.py` generates that file and the
research-side `data/derived/sc1-site.json` together from the SC0 Gold Set,
canonical entry artifacts, existing reading-layer records, and existing
PersonStoryLinks. They must remain byte-identical. The earlier
`wp1-site.json` artifact remains the WP1 sample/research validation fixture;
it is not a second runtime data source.

SC1 adds an orthogonal `story.publication_state`:

* `production_ready` — reviewed reading layer;
* `preview_ready` — valid deterministic candidate reading published for this
  experimental prototype without changing its CRL1/CRL1.1 review status;
* `blocked` — never published to the Story Chain.

The `story_chain` object projects the existing SC0 Story IDs and the existing
PersonStory links into `person_story_refs` and `story_person_refs`. It creates
no Person, Mention, Relation, or textual assertion. Main-text links are shown
as the primary Person → Story list; Liu-annotation-only links remain a
separate `史料提及` projection.

Relation records distinguish directly attested edges from deterministic paths
with `relation_basis: "direct" | "derived"`. Derived records expose
`derived_from_relation_ids` and do not carry an additional direct quotation;
the current bundle contains only the reviewed R1 atomic edges plus the legacy
`relation-001` derived path.

The page receives the imported bundle, performs a small runtime shape/reference
check, and renders the first validated Story. It does not call a backend,
database, online LLM, or runtime API.

Each Story in the generated bundle carries a `reading` object. Its status
remains the CRL1 editorial status (`reviewed`, `aligned`, `candidate`, or
`disputed`) and is separate from the SC1 `publication_state`:

```ts
story.publication_state: "production_ready" | "preview_ready" | "blocked"
```

`preview_ready` is an experimental publication state for a valid candidate;
it never changes the underlying punctuation record's `review_status`.

The reading object is:

```ts
type Segment = {
  type: "text" | "person_mention",
  display: { original: string, simplified: string },
  mention_id?: string,
  person_id?: string,
  annotation_id?: string
}

{
  entry_id: string,
  status: "reviewed" | "aligned" | "candidate" | "disputed",
  punctuation_record_id: string,
  base_canonical_entry_sha256: string,
  conversion: { library: string, config: string },
  main_text: {
    original: string,
    simplified: string,
    segments: Array<{
      type: "text" | "person_mention",
      display: { original: string, simplified: string },
      mention_id?: string,
      person_id?: string,
      annotation_id?: string
    }>
  },
  annotations: Array<{
    id: string,
    original: string,
    simplified: string,
    segments: Array<Segment>,
    display_source: "punctuation_record" | "canonical_source",
    punctuation_status: "available" | "unavailable"
  }>,
  mention_projection: {
    suppressed: Array<{
      mention_id: string,
      reason: "unsafe_anchor" | "overlapping_anchor" | "display_conversion_context_mismatch",
      section: "main_text" | "liu_annotation",
      annotation_id?: string
    }>
  },
  labels: Record<string, { original: string, simplified: string }>,
  person_display: Record<string, {
    name: { original: string, simplified: string },
    aliases: Array<{ surface: { original: string, simplified: string }, alias_type: string }>
  }>,
  mention_display: Record<string, { surface: { original: string, simplified: string } }>,
  source_display: Record<string, {
    work: { original: string, simplified: string },
    edition: { original: string, simplified: string }
  }>,
  display_overrides: string[]
}
```

The build chain is canonical entry → curated punctuation record → derived
reading object → static bundle. The same OpenCC conversion creates both story
text and ID-keyed person, mention, label, and source-title display maps. The
current page defaults to `simplified`, offers `original`, and stores only that
display preference in localStorage. The original fields in these maps are
copied from canonical WP1 records; they do not normalize orthographic variants
or change IDs and provenance.

For SC1.1.1, `main_text.segments` and each annotation's `segments` are the
build-time Mention projection. Concatenating `display.original` segments
reconstructs the existing punctuated/original reading exactly; concatenating
`display.simplified` segments reconstructs the existing OpenCC reading exactly.
Only resolved Mentions become `person_mention` segments. Their `mention_id`,
`person_id`, and optional annotation block ID are validated against the bundle
before the browser renders them. Unresolved Mentions remain ordinary text.
When resolved anchors overlap incompatibly (for example, an explicit name
nested inside a broader kinship surface), the deterministic projection keeps
the shorter safe anchor interactive and records the other in
`mention_projection.suppressed`; the secondary Story-person list still shows
both source-level resolutions. An annotation without a punctuation record is
marked `canonical_source`/`unavailable` and is displayed without invented
punctuation.
The frontend never parses raw, normalized, research, or witness files. The
reading strings are generated from
`content/processed/shishuo/entries/06-yaliang/entry-019.md` and
`data/annotation/wp1-punctuation.json`; they are not manually retyped in
React.

## R2 local relation explorer

The same static bundle carries the minimum reviewed relation display contract:

* `relations` retains the unified Person endpoint IDs, endpoint roles,
  `relation_basis`, review status, source IDs, evidence IDs, and
  `derived_from_relation_ids`.
* `story.reading.relation_display` contains OpenCC-derived original and
  simplified labels and endpoint roles keyed by relation ID.
* `story.reading.evidence_display` contains display-only quotations keyed by
  evidence ID. Canonical evidence quotations and provenance records remain
  unchanged.

The reader derives a local ego view from reviewed `direct` relations only.
Reviewed `derived` relations are excluded from the primary map and appear in a
separate expandable path that resolves `derived_from_relation_ids`. Neighbor
navigation updates the focused Person in place and keeps a small panel history.
The explorer reads no source corpus, research Markdown, or runtime API.

## CRL1 corpus reading layer

CRL1 is corpus infrastructure and is not bundled into the current small
frontend prototype. Its deterministic product is
`data/derived/shishuo-reading-layer.json`, generated from the expanded
`data/annotation/wp1-punctuation.json` by
`scripts/build_shishuo_reading_layer.py`. Each of the 1,130 canonical main
text entries has a punctuation status, alignment assessment, and a derived
OpenCC `t2s` display form when a safe punctuation candidate exists.

`story_reader_ready` depends only on main-text punctuation status, canonical
round-trip validation, and successful simplified derivation. Liu Xiaobiao
annotation readiness is reported separately. Candidate and disputed records
remain in the generated review queue and are not silently presented as
reviewed reading content. The canonical entries and all registered witness
payloads remain outside the frontend data contract.
