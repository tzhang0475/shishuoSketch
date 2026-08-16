# D1.0 — Runtime Bundle Size & Dependency Audit

## Baseline

This audit measures the frozen X1.2P state at commit
`7b1c4ab361a8db097607b5fc9f0931302a529345` on `main`. It is read-only with
respect to canonical text, punctuation, identity, PersonStory, Relations,
historical facts, Evidence, publication state, H0C, HG0, and ML0 data.

The research-side and Vite-side SC1 files are byte-identical:

| view | bytes | MiB | SHA-256 |
| --- | ---: | ---: | --- |
| `data/derived/sc1-site.json` | 80,421,489 | 76.695909 | `3b1a1fd0bfbd8bc7c4c4d53bcde4060943d2e8c49da77db87a5bee5cd34a2d2a` |
| `site/src/generated/sc1-site.json` | 80,421,489 | 76.695909 | same |

For field percentages below, “serialized bytes” means compact UTF-8 JSON
serialization of the parsed value. The raw file is pretty-printed, so compact
bytes are used to make field measurements additive; the raw file size remains
the deployment/Git measurement.

## Composition

### Top-level fields

| field | records | compact bytes | share |
| --- | ---: | ---: | ---: |
| `stories` | 143 | 62,004,500 | 95.489650% |
| `evidence` | 1,513 | 1,534,100 | 2.362581% |
| `mentions` | 557 | 661,544 | 1.018807% |
| `person_sketches` | 75 | 182,683 | 0.281340% |
| `era_cards` | 11 | 127,236 | 0.195949% |
| `story_era_orientations` | 143 | 97,125 | 0.149577% |
| `people` | 75 | 95,756 | 0.147468% |
| `story_chain` | 1 | 50,321 | 0.077497% |
| `ruler_mentions` | 13 | 10,599 | 0.016323% |
| `relations` | 12 | 8,080 | 0.012444% |
| other required fields | — | 131,271 | 0.202765% |

The three largest Story records are `36-chouxi-003` (545,624 compact bytes),
`35-huoni-003` (529,019), and `27-jiajue-008` (527,477). The largest
`evidence` records are still only about 1.5 KB each; Evidence is not large
because of a few abnormal records.

The largest measured leaf/projection contributors are:

| path | compact bytes | share |
| --- | ---: | ---: |
| `stories[].reading.evidence_display` | 56,413,044 | 86.878563% |
| `stories[].reading.person_display` | 3,389,100 | 5.219363% |
| `evidence` | 1,534,100 | 2.362581% |
| `evidence[].locator` | 850,544 | 1.309875% |
| `mentions` | 661,544 | 1.018807% |
| `stories[].reading.annotations` | 517,687 | 0.797261% |
| `stories[].reading.relation_display` | 344,773 | 0.530966% |
| `stories[].reading.main_text` | 343,604 | 0.529165% |
| `evidence[].locator.source_provenance` | 266,575 | 0.410537% |
| `stories[].reading.mention_display` | 265,600 | 0.409036% |

### Story reading projections

`stories[].reading` accounts for 61,631,295 compact bytes, or 94.914898% of
the compact bundle. Its largest contributors are:

| nested path | compact bytes across 143 Stories | share of compact bundle |
| --- | ---: | ---: |
| `stories[].reading.evidence_display` | 56,413,044 | 86.878563% |
| `stories[].reading.person_display` | 3,389,100 | 5.219362% |
| `stories[].reading.annotations` | 517,687 | 0.797261% |
| `stories[].reading.relation_display` | 344,773 | 0.530966% |
| `stories[].reading.main_text` | 343,604 | 0.529165% |
| `stories[].reading.mention_display` | 265,600 | 0.409036% |
| `stories[].reading.labels` | 241,670 | 0.372182% |
| `stories[].reading.source_display` | 46,475 | 0.071573% |

The current builder passes the complete global Evidence list to
`build_display_reading()`. Consequently, every Story contains an
`evidence_display` object even when most of its entries are unrelated to that
Story:

* 167,109 evidence-display entry occurrences;
* 1,513 unique Evidence IDs;
* 56,413,044 serialized bytes in the current per-Story maps;
* one shared map containing one display value per Evidence ID would be about
  493,699 compact bytes.

This is a display projection duplication, not 167,109 independent Evidence
assertions. The top-level `evidence` array remains the canonical runtime
Evidence projection and is only 1,534,100 compact bytes.

`person_display` is also a complete repeated map: 143 identical copies total
3,389,100 bytes, versus one copy of 23,700 bytes. `labels`, `source_display`,
and `relation_display` are likewise identical across all 143 Story readings.

The measured upper-bound opportunity from turning those repeated maps into
shared/indexed runtime data is 59,913,237 compact bytes, or 92.269014% of the
compact payload. This is an audit estimate, not a deletion or an instruction
to remove source-of-truth data.

### Evidence and provenance

The top-level Evidence array contributes 2.362581% by itself. If the repeated
Story-local Evidence display projection is included, Evidence-related runtime
surfaces are:

```text
1,534,100 + 56,413,044 = 57,947,144 compact bytes
57,947,144 / 64,933,215 = 89.241144%
```

Evidence locators are also structured rather than anomalous: 1,513 Evidence
records contain 45 repeated `source_provenance` objects, with 257,692 compact
bytes above one-copy-per-object. This provenance is semantically meaningful,
but a later runtime representation could reference stable source metadata
indirectly while retaining the full Evidence records in the research layer.

The following are intentionally not counted as accidental duplication:

* `reading.main_text.original/simplified` is a reader punctuation/conversion
  projection and is not interchangeable with physical-line canonical text;
* `reading.main_text.segments` carries Story-local inline interaction spans;
* ID arrays such as `evidence_ids`, `person_ids`, and `mention_ids` are small
  traversal indexes, not copied payloads;
* Evidence quotes and locators remain provenance-bearing records even when a
  display projection repeats them.

## Runtime necessity

The browser currently imports the complete JSON module and calls
`loadSiteBundle()`, which calls `parseSiteBundle()` over the complete object.
There is no runtime JSON fetch or lazy boundary.

| component | current classification | evidence from current reader |
| --- | --- | --- |
| `stories` | startup-required | initial Story, random Story, navigation and Story-local rendering |
| `people` | startup-required | Person lookup, Person panel, random Person, relation traversal |
| `mentions` | story-required | inline resolution and route context |
| `relations` | relation-required | relation rows, ego map and relation-context navigation |
| `evidence` | evidence-on-demand | collapsed Story/Person/Relation/Scene evidence panels; nevertheless parsed at startup |
| `eras` | validation-only | shape-validated, not directly read by current reader components |
| `sources` | validation-only | current reader uses `reading.source_display`, not `data.sources` |
| `ruler_identities` | validation-only | used by bundle integrity checks, not directly queried by the reader |
| `era_cards` | era-required | Story orientation and Era navigation |
| `ruler_mentions` | validation-only | validates projected ruler segments |
| `historical_events` | era-required | Era/event panels resolve event IDs |
| `story_era_orientations` | validation-only | Story-local `era_orientation` is rendered instead |
| `person_sketches` | person-required | focused Person panel and Person Explorer |
| `scene_contexts` | story-required | Story-local Scene Card, only when a record exists |
| `story_chain` | person-required | Person→Story lists; can be deferred until Person navigation |
| `ui` | startup-required | reader labels used throughout the UI |

Fields shipped today that are parser/build/provenance-only for the current
reader include `generated_from`, top-level `eras`, `sources`,
`ruler_identities`, `ruler_mentions`, `story_era_orientations`,
`stories[].text`, `stories[].annotations`, `stories[].source_ids`, and
`stories[].reading.mention_projection`. They should not be removed in D1.0;
they are candidates for a later compatibility-aware runtime/research split.

## Monolith dependency inventory

The deterministic dependency audit scans repository text consumers while
excluding the two payload files, build output, and D1.0's own artifacts.

| category | files |
| --- | ---: |
| builder | 11 |
| frontend runtime | 4 |
| validator | 13 |
| test | 21 |
| research/audit script | 28 |
| documentation | 4 |
| other/migration | 1 |
| total | 82 |

There are 78 files containing a literal SC1 bundle path and 5 files using the
`SiteBundle`/`loadSiteBundle`/`parseSiteBundle` API (with overlap). All literal
JSON consumers currently physically parse or import the monolith; many use
only a semantic subset after loading it.

High-risk migration dependencies are:

* `site/src/data.ts`: static JSON import, complete parser contract, and
  `SiteBundle` return API;
* `site/src/App.tsx`: cross-domain application state currently receives one
  complete bundle;
* `site/src/relationExplorer.ts`: relation/story/person navigation assumes
  synchronous fields on `SiteBundle`;
* `scripts/build_sc1_frontend_data.py`: produces both byte-identical views and
  currently constructs the repeated display projections;
* `scripts/migrate_person_ids.py`: writes both generated views and must be
  audited before any shard migration.

`scripts/validate_sc1_frontend_data.py` and
`scripts/validate_frontend_artifact.py` are medium/high migration surfaces
because they enforce generated-view identity and production markers. The
complete path-by-path inventory, semantic scope, and migration risk is in
`data/derived/d1-0-dependency-audit.json`.

## Git and browser/runtime risks

The raw file is 76.695909 MiB. It is above GitHub's 50 MiB large-file warning
threshold and below the 100 MiB single-file hard limit. A generated change
creates a very large diff/object update. Identical files can share one Git
blob object, but both copies remain in checkouts and generated deployment
inputs.

The current Vite build statically imports the JSON. The current production
JavaScript asset is 65,940,650 bytes and contains SC1 data markers. Therefore:

1. the complete payload enters the initial JavaScript asset;
2. the browser pays the full JSON-module parse/object memory cost before the
   reader can use a Story;
3. `parseSiteBundle()` validates the full object at startup;
4. there is no lazy Story, Person, Relation, Evidence, or provenance fetch.

## Candidate D1.1 boundaries

These are options, not implementation decisions.

### A. Shared projection normalization first

Move repeated Story-reading maps to shared tables and retain Story-local IDs;
make Evidence display data shared or on-demand while keeping an adapter that
reconstructs the current `SiteBundle` shape.

* Expected reduction: up to the measured 59.9 MB compact projection
  duplication, subject to preserving all current fallbacks and validation.
* Complexity: low to medium.
* Migration risk: low to medium; the reader can keep its synchronous API first.
* GitHub Pages: fully compatible with a static generated asset.
* Navigation: no semantic change if the adapter resolves the same IDs.
* Reconstruction: exact, provided the adapter retains current display and
  evidence lookup behavior.

This is the safest first D1.1 boundary because it addresses the dominant
measured waste before changing loading semantics.

### B. Startup index plus Story-chapter and entity shards

Keep a small startup index containing Story metadata/IDs, publication state,
Era links, and Person/Relation indexes. Load a Story chapter shard on Story
selection and entity/relation data when a Person panel opens.

* Expected initial-payload reduction: likely over 90%; exact size requires a
  shard prototype.
* Complexity: medium to high.
* Migration risk: medium; async loading and failure states enter navigation.
* GitHub Pages: compatible with hashed static JSON paths and a generated
  manifest, but deployment must remain atomic.
* Navigation: Story→Person→Relation→Story needs a cache/loader boundary.
* Reconstruction: possible through a compatibility adapter and an offline
  aggregate validator.

### C. Domain shards with on-demand Evidence/provenance

Separate startup index, Story payloads, Person Sketches, Relations, Era/Event
data, and Evidence/source payloads. Load only the domains needed by the
current surface; retain a research-side complete archive for validators.

* Expected initial-payload reduction: potentially 95% or more; first-Story
  and evidence payloads become the relevant measurements.
* Complexity: high.
* Migration risk: high; it changes the synchronous data contract and cache
  behavior across every navigation route.
* GitHub Pages: compatible, but requires robust relative paths, manifest
  versioning, and atomic shard publication.
* Navigation: greatest effect on Relation-context traversal and Back-state
  restoration.
* Reconstruction: possible, but must be tested as a separate deterministic
  aggregate projection rather than assumed from browser loads.

## Recommended next action

Begin D1.1 with **A**, then measure a prototype shared Evidence/display table
before committing to asynchronous sharding. Preserve the current
`SiteBundle`-compatible aggregate view for validators and regression tests.
If the prototype confirms the measured reduction without semantic drift,
introduce **B** as the first lazy boundary: startup index plus Story/entity
payloads. Do not remove canonical Evidence or provenance; only defer or
normalize its runtime projection.

The current 76+ MB size is therefore caused primarily by **repeated
Evidence/display projection data embedded in each Story reading**, with a
secondary contribution from repeated Person and common UI maps. It is not
primarily necessary reader prose, top-level Evidence records, or the small
Relation/Era/entity registries. The audit does not change any of those data
layers.

## Artifacts and validation

* `data/derived/d1-0-bundle-size-audit.json` — composition, nested sizes,
  duplication, runtime classification, Git/runtime observations, and
  protected-data hashes;
* `data/derived/d1-0-dependency-audit.json` — deterministic repository
  consumer inventory;
* `scripts/validate_d1_0.py` — recomputes the audit, hashes both SC1 views,
  checks byte totals and duplicate dependency paths, and checks protected
  hashes.

D1.0 does not split `sc1-site.json`, change frontend loading, alter protected
data, or begin D1.1.
