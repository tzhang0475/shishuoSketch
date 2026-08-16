# HG1.1 — Historical Relationship Densification & Temporal Graph Rebuild

HG1.1 is a downstream rebuild from the protected H0C/HG0 snapshot.  It does
not rewrite canonical Shishuo text, identities, participant freeze, H0C facts,
HG0 graph truth, or ML0 artifacts.  Its outputs are the reviewed historical
extension and derived graph projection that a later HG1.1 consumer may use.

## Scope and source discipline

The graph universe remains the published 75-Person/143-Story scope.  The
frozen X1 selection remains 20 Stories; it is used only to audit the existing
Jianshu relation surface, not to select a new batch.

HG1.1 consumes:

- the 12 already-reviewed SC1/H0C Person relations;
- the R3B review decision and its five approved relation records;
- the five existing R3C/Jinshu relation candidates, retained unresolved
  because no HG1.1 approval exists;
- the structured S1 assertion surface for a bounded lexical audit;
- the three accepted X1.2R-F extension facts;
- reviewed H0A/H0B1/E0 temporal anchors and reviewed service/event context.

The Jinshu unit index and R3C candidate artifact are hashed inputs.  Their
candidate surfaces are not treated as evidence sufficient for acceptance by
themselves.  A lexical marker or source citation without safely resolved
endpoints remains unresolved.

## Relation review and representation

Every relation candidate is represented with an explicit review state.  The
HG1.1 candidate artifact contains 73 records: 19 existing relation/candidate
records (R3A, R3C, and reviewed H0C relations) plus 54 unresolved Jianshu
language-scan records.  The review artifact contains:

- 12 accepted reviewed relation records, all inherited from the protected
  H0C/Relation contract;
- 61 unresolved records, including two R3B deferred candidates, five R3C
  Jinshu candidates, and 54 endpoint-unsafe Jianshu scan surfaces;
- no rejected relation in this bounded input surface.

No new canonical Person–Person fact was created.  Three explicit reviewed R3B
relations receive a direct graph projection in addition to their existing
contextual/reified paths:

| relation | direct edge | scope |
| --- | --- | --- |
| `relation-r3b-003` | `relation_institutional` | reviewed service-under assertion |
| `relation-r3b-004` | `relation_political` | 苏峻之乱, event-bounded |
| `relation-r3b-005` | `relation_political` | 苏峻之乱, event-bounded |

The two graph edge types are the only HG1.1 ontology additions.  They are
explicitly scoped, not permanent allegiance or faction claims.  Existing
Story/Event/Office/Location/Clan/service context remains separate.  A shared
Story, Event, office, location, or model/graph proximity never creates a
direct social relation.

## Reviewed extension facts

The three accepted X1.2R-F extension facts are consumed downstream:

- two reviewed OfficeTenure facts, represented with reified `OfficeTenure`
  nodes and typed edges;
- one reviewed location fact, represented as the existing typed
  `held_office_at` projection.

They are marked as inherited reviewed extensions in HG1.1.  HG1.1 creates no
new canonical fact and does not modify the X1.2R-F artifact.

## Temporal backfill

All 143 production Stories receive a temporal-resolution row.  A row is
resolved only from a reviewed direct Story anchor with an explicit interval or
from a reviewed service/event context that explicitly lists the Story.  A
Person's OfficeTenure is never used alone to date a Story.

Current result:

| state | count |
| --- | ---: |
| exact | 1 |
| bounded | 10 |
| broad-period | 0 |
| unknown | 132 |

The 22 candidate broad/phase constraints remain visible as audit metadata but
are not promoted into the reviewed temporal projection.  Unknown is an
explicit historical state, not a negative date assertion.

## Graph delta and coverage

HG0 contains 347 nodes and 996 edges.  HG1.1 contains 349 nodes and 1,004
edges.  The delta is:

- 2 reviewed extension `OfficeTenure` nodes;
- 4 OfficeTenure edges;
- 1 reviewed typed location edge;
- 3 direct institutional/political Person–Person edges.

Direct Person relation edges rise from 10 to 13, and Persons with direct
relation context rise from 11 to 14.  This is structural availability, not a
ranking of historical importance.  The graph remains derived from reviewed
facts and keeps inherited contextual paths intact.

## UX1 refresh

The existing lazy UX1 architecture was refreshed; it was not redesigned.
`sc1-site.json` remains the initial reader bundle.  The historical shards now
consume HG1.1 reviewed relation and Story-temporal projections:

| UX coverage | before | after |
| --- | ---: | ---: |
| relation shards with evidence | 6 | 12 |
| Stories with reviewed temporal context | 6 | 11 |
| Era cards with people | 0 | 3 |
| Era cards with any historical depth | 3 | 6 |
| Era Story links | 7 | 12 |
| evidence shards | 108 | 117 |

Unresolved facts and candidate temporal rows are not emitted into factual UX
sections.  Relation evidence remains tied to its evidence IDs and source
locators; the browser still loads optional detail only after a user opens the
relevant panel.

## Readiness and stop boundary

The rebuilt graph is deterministic and suitable for a reviewed, diagnostic
historical graph snapshot.  Family/marriage, office/service, direct relations,
and temporal layers remain pilot-level because endpoint and interval coverage
is sparse.  The combined graph remains suitable for controlled follow-up
review, not for political-faction discovery or historical-importance ranking.

HG1.1 explicitly stops before:

- ML1.1 training, embeddings, or new GNN experiments;
- X1.2B Story selection;
- ER2 or graph UI redesign.

The next safe step is a review of this snapshot and its deltas before deciding
whether ML1.1 is justified.
