# Static frontend data interface

The frontend is static-first. The deterministic WP1 builder generates one
frontend bundle at `site/src/generated/wp1-site.json`, and the Vite
application imports it at build time. The browser does not fetch a separately
cached `wp1-site.json` URL. Code and frontend data therefore enter the same
hashed production assets and are deployed atomically; users do not need a
hard refresh or cache-busting query parameter after deployment.

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
  sources: Source[]
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

The current WP1 prototype is a single reading page served under the configured
`/shishuoSketch/` base path in local preview and on GitHub Pages. It
intentionally does not introduce client-side routing yet. The object IDs and
cross-object references remain available in the bundle for later reading
surfaces.

Relation records distinguish directly attested edges from deterministic paths
with `relation_basis: "direct" | "derived"`. Derived records expose
`derived_from_relation_ids` and do not carry an additional direct quotation;
the current bundle contains only the reviewed R1 atomic edges plus the legacy
`relation-001` derived path.

The page receives the imported bundle, performs a small runtime shape/reference
check, and renders the first validated Story. It does not call a backend,
database, online LLM, or runtime API.

Each Story in the generated bundle also carries a reviewed `reading` object:

```ts
{
  entry_id: string,
  status: "reviewed",
  punctuation_record_id: string,
  base_canonical_entry_sha256: string,
  conversion: { library: string, config: string },
  main_text: { original: string, simplified: string },
  annotations: Array<{ id: string, original: string, simplified: string }>,
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
