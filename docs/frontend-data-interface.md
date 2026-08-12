# Static frontend data interface

The frontend is static-first. It fetches one generated JSON bundle:

```text
/data/wp1-site.json
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

Supported routes in the WP1 placeholder frontend:

```text
/stories/:id
/people/:id
/relations/:id
/eras/:id
```

The page loads the JSON, performs a small runtime shape/reference check, and
renders a placeholder reader. It does not call a backend, database, online
LLM, or runtime API. Unknown IDs render a local not-found message.

The Story page displays the generated exact main text and Liu Xiaobiao
annotation text with links to resolved people, the sample relation, and the
candidate Era. The text is generated from
`content/processed/shishuo/entries/06-yaliang/entry-019.md`; it is not
manually retyped in the frontend.
