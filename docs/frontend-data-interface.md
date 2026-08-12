# Static frontend data interface

The frontend is static-first. It fetches one generated JSON bundle from the
Vite base-aware asset path:

```text
${BASE_URL}data/wp1-site.json
```

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

The bundle is generated from the canonical Shishuo entry and the existing
six-person pilot by `scripts/build_wp1_sample.py`. It is not a second source
text authority.

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

The page loads the JSON, performs a small runtime shape/reference check, and
renders the first validated Story. It does not call a backend, database,
online LLM, or runtime API.

The reading page displays the generated exact main text and Liu Xiaobiao
annotation text, resolved person cards, and collapsible evidence/provenance.
The text is generated from
`content/processed/shishuo/entries/06-yaliang/entry-019.md`; it is not
manually retyped in the frontend.
