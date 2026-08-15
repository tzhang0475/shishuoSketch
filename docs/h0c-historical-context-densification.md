# H0C — Historical Context Densification & Graph-Learning Readiness

H0C is the historical-data infrastructure milestone after H0B-1. It makes the
current 75-Person / 143-Story corpus more reusable as an evidence-grounded,
temporally aware historical context layer. It is deliberately not HG0, ML0,
ER2, or a reader-facing graph product.

## Scope and boundary

The protected production corpus remains:

- 75 Persons
- 143 Stories
- 875 PersonStory links, including 870 reviewed links
- 12 reviewed Relations
- 44 Scene Contexts
- 0 orphan Mentions
- 143/143 primary Era orientations

H0B-0 and H0B-1 inputs are read-only. H0C never allocates a Person or Story,
rewrites a Mention, changes canonical text, or turns an unresolved endpoint
into a negative historical fact. The H0C protection manifest records the
input hashes and frozen H0B-0 hashes.

## Participant freeze

`data/derived/h0c-participant-freeze.json` freezes the existing H0B-1 semantic
projection for every production Story. A row is a Story × Person × role
assertion with stable participant ID, source section, mention provenance,
Evidence IDs, and review metadata.

The roles remain distinct:

- `present`, `speaker`, and `actor` are hard participation and may be used by
  later temporal reasoning;
- `referenced`, `off_frame`, and `annotation_only` are contextual and cannot
  date a Story;
- `uncertain` is allowed only as an explicitly reviewed uncertainty.

PersonStory and Mention are not participation. A Liu Xiaobiao biographical
mention is not a scene participant. The freeze is a gate: later H0C entity or
fact enrichment may record an anomaly, but may not silently change Story
participation.

## Historical entities

H0C normalizes reusable entities without replacing the existing canonical
layers:

- `Location` records historical labels, typed place usage, evidence, and
  explicit modern-mapping/coordinate uncertainty. An ancient place is not
  silently equated with a modern administrative unit.
- `Office` is reusable institutional identity; `OfficeTenure` remains the
  Person-specific historical fact. Unknown tenure dates remain unknown.
- `Event` reuses the five locally evidenced H0A historical events and retains
  their source claims and date precision.
- `Regime` is a minimal reusable political-context label derived only where
  existing OfficeTenure evidence requires it.
- H0B Clan, ClanMembership, KinshipFact, and MarriageUnion IDs are reused;
  surname, co-occurrence, office, and locality do not create family facts.

New H0C Location, Office, and Regime IDs are assigned in the frozen
`data/annotation/h0c-entity-id-manifest.json`. Labels are semantic lookup
keys only; later spelling or display changes cannot renumber an entity.

H0C reuses H0A PersonActivityAnchor IDs as candidate activity facts. It does
not promote them to biography and does not rewrite H0A StoryTemporalAnchor.
Contextual event references are kept separate from hard EventParticipation.

## Fact and provenance layer

`h0c-historical-facts.json` is an index of canonical H0A/H0B/Relation facts
and H0C projections. It does not duplicate or renumber the underlying facts.
Each index row records its fact type, stable fact ID, subject IDs, source path,
Evidence IDs or source-mention provenance, review/assertion status, temporal
precision, locations, and derivation IDs.

The source policy is repository-local only: Shishuo main text, Liu Xiaobiao,
Jinshu, existing evidence, H0A, H0B, and reviewed Relation annotations. Source
layers are not collapsed into one undifferentiated quotation pool.

## Graph reconstruction

`h0c-graph-projection.json` is a deterministic heterogeneous projection over
canonical facts. It currently supports Person, Story, Location, Event, Office,
Clan, and Regime nodes, with typed edges such as:

- Person → Story PersonStory and participation edges;
- Person → Clan, Person → Person kinship/marriage/service edges;
- Person → Office and Office → Location/Regime;
- Person → Event, Story → Location, and Event → Story context edges.

Facts remain canonical; the graph is disposable and derived. Every graph edge
points to one or more fact IDs and carries Evidence IDs or stable source
provenance references. `h0c-graph-audit.json` reports dangling endpoints,
unsupported evidence, duplicate semantic edges, family cycles, temporal
conflicts, and alias collision surfaces. Missing edges are unknown, not
negative relations.

The current production graph projection intersects 330 PersonStory links with
the 143 published Stories. The protected global PersonStory index still has
545 additional links outside that published Story scope; H0C reports this
scope boundary instead of creating dangling Story nodes.

## Temporal and spatial semantics

Temporal precision remains explicit on OfficeTenure, Event, PersonActivity,
location facts, and graph edges. An office constrains a Story only when the
Story activates that office; an annotation-only or off-frame Person cannot
provide a hard Story-time constraint. H0A remains the conservative historical
assertion layer. H0C never mass-rewrites unknown H0A anchors.

The reader Era layer and historical assertion layer are therefore allowed to
disagree in precision:

```text
H0A StoryTemporalAnchor = unknown
H0C social/activity context = candidate or broad interval
E0 reader orientation = a useful broad Era
```

This is intentional. H0C stores context without converting orientation into a
fabricated date.

## Readiness contract

`h0c-ml-readiness.json` reports raw per-Person dimension coverage for Story
participation, temporal footprint, geography, family, Clan, office, event,
service/political context, relation neighborhood, and evidence traceability.
States include `available`, `partial`, `unknown`, `candidate_only`, and
`conflicted`; they are not an importance score.

The graph contract is framework-neutral. It records node and edge fields,
fact/evidence traceability, temporal precision, uncertainty states, and the
rule that missing edge ≠ negative edge. H0C does not generate embeddings,
negative samples, train/test splits, centrality rankings, clusters, learned
signatures, or models.

## Remaining gaps

The gap audit preserves, among others:

- five isolated protected nodes (four Persons and one Story) in the current
  published projection;
- office records with no local place assertion;
- events whose local evidence does not identify an event location;
- unresolved family/marriage endpoints and one unresolved Clan branch;
- relation temporal scope that is not safely bounded;
- generic alias collision surfaces such as `太傅` and `王公`.

These are research states, not failures to be hidden by inferred edges.

## Validation and stop condition

The permanent H0C gate is `scripts/validate_h0c.py` and
`tests/test_h0c.py`. The builder is deterministic and emits hashes in the
metrics artifact. H0C is complete at the graph reconstruction and readiness
audit boundary. HG0, graph-learning experiments, ML/GNN training, embeddings,
ER2, historical interpretation, and graph UI are explicitly deferred.
