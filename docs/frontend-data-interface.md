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
  display_overrides: string[]
}
```

The build chain is canonical entry → curated punctuation record → derived
reading object → static bundle. The current page defaults to `simplified`,
offers `original`, and stores only that display preference in localStorage.
The frontend never parses raw, normalized, research, or witness files. The
reading strings are generated from
`content/processed/shishuo/entries/06-yaliang/entry-019.md` and
`data/annotation/wp1-punctuation.json`; they are not manually retyped in
React.
