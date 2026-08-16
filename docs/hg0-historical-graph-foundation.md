# HG0 — Historical Graph Foundation

HG0 is the deterministic graph layer after H0C. It answers two questions:

1. What is the Historical Graph represented by the current ShishuoSketch
   evidence layer?
2. Which graph-learning questions are structurally supportable without
   turning missing historical evidence into false negatives or fabricated
   facts?

HG0 is a graph-modeling and sufficiency milestone. It does not enrich the
historical corpus, train a model, generate embeddings, or interpret social
groups.

## Immutable hierarchy

The data flow is:

```text
local qualified sources
        ↓
H0A / H0B / H0C canonical facts
        ↓
HG0 deterministic graph projection
        ↓
future framework-neutral ML0 projection
```

Facts remain canonical. Graph nodes and edges are disposable projections. An
edge is valid only when it can point back to an H0C fact and its Evidence or
source provenance. HG0 never repairs H0C identity, participation, chronology,
or source text.

## Graph universe and scope

The default graph is `hg0-published-story-scope`:

- 75 protected production Persons;
- 143 published Story nodes;
- H0C-normalized Location, Event, Office, Clan, and Regime entities referenced
  by the protected fact layer;
- the 330 PersonStory links whose `entry_id` is one of those 143 Stories.

The global PersonStory index contains 875 links. A further 545 links point to
417 Story IDs outside the published Story scope. HG0 records that population
in `hg0-graph-universe.json` as
`global_person_story_index_boundary`, but does not create dangling Story
nodes. A wider research graph requires an explicit future Story-scope
manifest; the excluded links are not negative evidence.

Context entities may exist without a published Story node when an H0C fact
requires them. This is historical context, not an implicit Story expansion.

## Node ontology

Canonical entity nodes are:

```text
Person, Story, Location, Event, Office, Clan, Regime
```

HG0 also materializes four reified fact nodes where a direct binary edge would
lose important context:

```text
OfficeTenure
PersonActivity
EventParticipation
ServicePoliticalFact
```

Reified node IDs are deterministic projections of existing H0C fact IDs. They
do not create new historical facts or new Persons. Each reified node carries
its source fact, Evidence IDs, review/assertion state, and temporal metadata.

## Edge ontology and multiplex layers

The graph is a multiplex network. The same endpoints may have several typed
edges, but those edges are not interchangeable. HG0 exposes layer views such
as:

```text
G_all
G_story
G_family
G_clan
G_office
G_event
G_geographic
G_service_political
G_social_context
G_temporal
```

Important distinctions include:

- `person_story_link` is the PersonStory index and does not mean scene
  presence;
- `story_participant_present`, `story_participant_actor`, and speaker roles
  are hard participation, while referenced/off-frame/annotation-only edges
  are contextual;
- `parent_of`, `spouse_union`, and `member_of_clan` retain separate family and
  clan semantics;
- office, activity, event participation, and service/political facts use
  reified paths so that time, Story, Event, Location, role, and applicability
  are not discarded;
- an existing Relation edge remains a Relation projection and is not silently
  promoted into a new atomic historical fact.

Independent edge types between the same Persons are allowed. Duplicate edges
with the same type, endpoints, and supporting fact set are invalid.

## Reification policy

The policy is information-preserving rather than graph-size-driven.

`OfficeTenure` is `Person × Office × Time × Location × Regime`; therefore HG0
projects it through an OfficeTenure node. `PersonActivity` and
`EventParticipation` similarly preserve Story/Event/role/interval context.
Service and political context is reified so an event-scoped or Story-scoped
context cannot become an unbounded Person-to-Person tie.

Current binary MarriageUnion, atomic KinshipFact, and ClanMembership facts are
represented as typed edges with their canonical fact IDs and evidence. The
ontology records these choices in `hg0-ontology.json`; later graph adapters can
choose a different ML representation without changing canonical facts.

## Temporal graph semantics

Every HG0 edge carries:

```text
start_year_ce
end_year_ce
precision
basis
temporal_state
```

`temporal_state` distinguishes bounded, one-sided, relative-only, and
unknown. `hg0-temporal-projection.json` provides one deterministic temporal
index row per edge and a potential-overlap interval contract:

```text
edges_for_interval(start_year_ce, end_year_ce, include_unknown=False)
```

Bounded and one-sided intervals may be returned when they potentially overlap
the requested slice. Unknown and relative-only facts are excluded from a
strict slice and remain visible in an uncertainty bucket. Overlap never turns
phase-only, event-bounded, approximate, or unknown evidence into an exact
date.

The temporal leakage rule is explicit: a pre-cutoff projection may use only
facts whose known end is at or before the cutoff, plus a separately marked
uncertain bucket. HG0 does not create train/test splits.

## Spatial semantics

H0C Locations remain historical entities, not modern geocodes. Typed edges
retain roles such as Story presence, office location, activity location, and
jurisdiction. Missing coordinates and unknown modern mappings are preserved as
unknown. The spatial sufficiency audit reports historical entity and typed
fact coverage without treating low coordinate coverage as a validation error.

## Provenance and uncertainty

Every edge has source fact references and Evidence IDs or source provenance.
Candidate, reviewed, derived, uncertain, and conflicted states remain
machine-readable. HG0 does not collapse these into one confidence number.

The invariant is:

```text
missing edge != negative edge
unknown != false
candidate != reviewed
approximate != exact
```

No artificial negative edges or negative samples are generated. Alias
collisions such as generic `太傅` and `王公` remain unresolved; graph topology
cannot become circular identity evidence.

## Sufficiency and bias

`hg0-sufficiency-audit.json` reports node coverage, typed edge counts,
components, degree summaries, temporal coverage, review distribution, and
layer classification (`strong`, `usable`, `pilot_only`, or `insufficient`).
The current combined graph is usable for constrained heterogeneous pilots;
family, clan, office, event, geographic, temporal, and service layers remain
pilot-only or insufficient at the layer-specific level.

`hg0-bias-audit.json` records that Story-related structure dominates the H0C
edge population, that 545 of 875 global PersonStory links are outside the
published scope, and that Liu annotation contributes contextual connectivity
that is not hard scene presence. Person degree is reported as coverage data,
not historical importance.

The five protected isolated nodes remain isolated in HG0. They are reported as
scope, missing-data, or sparse-evidence states rather than connected for graph
cosmetics.

## ML0 readiness contract

`hg0-ml0-readiness.json` is framework-neutral. It defines node and edge fields,
typed layer views, traceability requirements, reviewed-only and
reviewed-plus-candidate projections, strict interval projections, feature
availability masks, and the missingness contract. It does not depend on
NetworkX, PyTorch Geometric, DGL, Neo4j, or another library.

The current data is suitable for carefully constrained heterogeneous structure
and temporal representation pilots. Constrained link prediction is only a
pilot question because family/service layers are sparse and missing links are
unknown. Political-faction discovery, event prediction, and historical
importance ranking are premature or unsupported by the present evidence and
scope.

HG0 does not generate embeddings, model checkpoints, train/test splits,
negative samples, learned clusters, centrality-as-truth, GNN datasets, or
models.

## Artifacts and validation

The builder and validator are:

```text
scripts/build_hg0_historical_graph.py
scripts/validate_hg0.py
tests/test_hg0.py
```

The derived artifacts are the ontology, graph universe, graph projection,
temporal projection, graph integrity audit, sufficiency audit, bias audit,
graph gap audit, ML0 contract, protection manifest, and metrics under
`data/derived/hg0-*.json`.

HG0 records hashes of the H0C graph, participant freeze, facts, entity
manifest, and H0C protection manifest. Rebuilding with unchanged H0C inputs
must produce byte-identical outputs.

## Boundary

HG0 is not HG0 enrichment, ML0, GNN training, ER2, historical interpretation,
or graph UI. The next milestone must decide whether to enrich sparse graph
layers or begin a constrained ML0 experiment. It must respect the scope,
uncertainty, collision, temporal, and missingness boundaries recorded here.
