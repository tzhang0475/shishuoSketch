# UX1 — Historical Depth Projection

UX1 is a frontend projection milestone. It exposes reviewed historical depth
already present in H0C and the X1/S1 extension layers without changing any
canonical text, identities, facts, graph artifacts, or publication state.

The design principle is:

```text
initial SC1 reader bundle
        ↓ explicit panel/section interaction
small static historical projection
        ↓ optional “查看依据”
evidence detail
```

The initial reader remains the fast path. UX1 does not load HG0/HG1 graph
data, the full Jianshu corpus, unresolved candidates, or research audit
records in the browser.

## Projection layers

`scripts/build_ux1_historical_projection.py` consumes existing reviewed
downstream artifacts and writes static JSON under:

```text
site/public/generated/history/
├── person/<person_id>.json
├── story/<story_id>.json
├── era/<era_card_id>.json
├── relation/<relation_id>.json
├── evidence/<evidence_id>.json
└── manifest.json
```

The output is a display projection, not a replacement historical database.
Factual sections contain only rows with `review_status = reviewed`. The
current projection includes:

* 75 Person summaries;
* 143 Story summaries;
* 11 Era summaries;
* 12 reviewed Relation summaries;
* 108 compact evidence-detail records.

Reviewed family/marriage relations and the three accepted X1.2R-F extension
facts are eligible for factual display. Candidate H0C office, event,
location, activity, and temporal records remain excluded. A field being
absent means that the reviewed projection has no displayable fact; it does
not mean that the historical relation is false.

Jianshu `scholarly_assertion_only` and citation-only records are kept under
`进一步读`, with source layer, attribution, modality, and quoted-source
metadata retained. They are never inserted into factual profile sections.

## Frontend behavior

`site/src/historical.ts` provides `loadHistoricalProjection(kind, id)` and a
small in-memory promise cache. Requests use the Vite base path and ordinary
static `fetch()` calls, so the site remains compatible with GitHub Pages and
other static hosts.

Historical data is requested only after an explicit interaction or detail
surface becomes active:

* opening a Person panel loads one Person summary shard;
* opening an Era panel loads one Era summary shard;
* expanding Story `进一步读` loads one Story shard;
* expanding Relation `历史语境` loads one Relation shard;
* clicking `查看依据` loads only the referenced evidence shards.

There is no startup preload, hover prefetch, global graph request, dynamic
import, or full-corpus browser state. Concurrent requests for the same shard
share one promise; failed requests are removed from the cache so a later
explicit action can retry. Optional historical failures do not interrupt the
Story reader or the existing Person/Relation navigation.

The UI hierarchy remains restrained:

```text
Person identity → existing Story/relation exploration → 历史 → 进一步读
Story text → existing Scene/annotation tools → 进一步读
Era identity → existing Story links → 历史
```

The original Story text remains primary. Historical rows use short templates
and preserve uncertainty/precision labels rather than generating narrative
interpretation. No AI, ML, embeddings, model rankings, or inferred relations
are projected.

## Evidence hierarchy

UX1 keeps three visible levels separate:

1. factual profile/context rows from reviewed structured facts;
2. `进一步读` scholarly material from Liu annotation and Jianshu notes;
3. `查看依据` source locator and short excerpt.

An explicit scholarly assertion can be useful reading material without being
a canonical fact. A citation lead is shown as a lead, not as proof from the
cited work. The display does not turn annotation-only mentions into hard
participants and does not create relations from co-occurrence, office,
location, graph similarity, or model output.

Full source passages are not copied into Person, Story, or Era shards.
Shared evidence IDs point to compact evidence-detail records, whose excerpts
are deliberately short. The existing SC1 evidence projection remains the
protected initial-bundle contract; UX1 does not add another copy of it to
`sc1-site.json`.

## Initial-load budget

The pre-UX1 measurements are committed in
`data/derived/ux1-frontend-size-baseline.json`. The current audit is in
`data/derived/ux1-frontend-size-audit.json`, produced by
`scripts/audit_ux1_frontend_size.py`.

Measured at this milestone:

| Initial asset | Before | After | Change |
| --- | ---: | ---: | ---: |
| `sc1-site.json` | 6,868,623 B | 6,868,623 B | 0.00% |
| entry JS | 5,235,913 B | 5,246,495 B | +0.20% |
| entry JS gzip | 760,683 B | 763,094 B | +0.32% |
| CSS gzip | 5,644 B | 5,872 B | +4.04% |
| initial static assets | 5,262,288 B | 5,274,134 B | +0.23% |
| initial static assets gzip | 766,651 B | 769,288 B | +0.34% |

The lazy historical payload is approximately 263 KB raw, plus a 76 KB
deterministic manifest containing source/shard hashes. The current maximum
entity summary shard is 3.5 KB and the maximum evidence-detail shard is 2.2
KB; no summary shard approaches the one-megabyte accidental-payload guard.
These optional assets are intentionally excluded from the initial budget.

`validate_ux1.py` verifies the initial SC1 SHA-256 and byte size against the
baseline, confirms that no per-Story global display maps or UX1 projection
fields were added, checks shard hashes and review states, and enforces the
initial size limits.

## Compatibility and limits

UX1 reads canonical/reviewed fact extensions directly rather than graph edge
IDs. This leaves the future canonical-facts → HG1.1 projection path intact.
It does not rebuild HG1.1, modify HG0/ML0, or expose a graph visualization.

The current reviewed historical layers are uneven. Family/relation context
and a small number of accepted Jianshu-backed office/location facts are
visible; many H0C office, event, location, and broad temporal records remain
candidate-only and are intentionally absent. Era cards therefore show a
reviewed ruler identity where available, while candidate event lists are not
duplicated into UX1 factual history. This is a data-status limitation, not a
frontend omission to be filled with inference.

UX1 does not implement chapter sharding, lazy source-corpus loading, service
workers, route-level code splitting, a database/API, HG1.1, ML1.1, X1.2B, or
ER2.
