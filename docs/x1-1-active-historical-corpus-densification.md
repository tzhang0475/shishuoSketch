# X1.1 — Active Historical Corpus Densification

X1.1 is the first controlled expansion epoch after ML0. It uses the wider
global PersonStory boundary to decide where historical review should happen;
it does not treat model output as historical truth and it does not rebuild
HG1.1 or ML1.1.

## Scope and freeze

The candidate universe is the 417 Story IDs outside the current 143-Story
published scope. They have 545 global PersonStory links. Every candidate is
audited against the canonical entry index, the punctuation record, resolved
production-Person routes, and local Evidence. In this epoch 388 candidates are
qualified and 29 are rejected: 28 have disputed punctuation records and one
(`02-yanyu-070`) has no local Evidence reference. A rejected candidate is not
a negative historical fact.

The default X1.1 batch is 20 Stories. Allocation is frozen before enrichment:

```text
graph_guided       8 (40%)
coverage_guided    6 (30%)
stratified_random  3 (15%)
counter_model      3 (15%)
```

The selection manifest records the HG0/ML0 input hashes, candidate-pool hash,
seed, channel, rank, score components, and a selection snapshot hash. The
selection is an experiment boundary: enrichment cannot rescore or replace an
item after the freeze.

## Four selection channels

Graph-guided selection exposes bridge value, missing external Person pairs,
external-layer value, temporal value, and coverage value. It is a graph
navigation signal, not a ranking of historical importance.

Coverage-guided selection uses documented gaps in family, office, event,
temporal, clan, geographic, and service/political dimensions. Its score does
not reuse the graph-guided score as its selection rule.

Stratified-random selection is an independent control channel. It samples
stable chapter/participant-count strata with a fixed seed and hash order. No
model or graph score is an input to the choice.

Counter-model selection first requires a qualified candidate and independent
value signals such as source quality, an underrepresented chapter, an office
or event surface, a family surface, a location surface, or a possible
ontology gap. It then chooses from the lower half of the model-proxy order;
it is not the global bottom-score set. Disagreement with the current graph is
a reason to inspect the Story, not a reason to reject it.

ML0 did not publish a Story-level neural ranking. The X1.1
`model_proxy_score` is therefore only a transparent diagnostic based on
current published PersonStory and HG0 Person incidence. It is recorded as a
proxy, never as a model discovery or historical-importance estimate.

## Review boundary and actions

Each reviewed overlay record can carry explicit actions:

```text
ADD_FACT
ADD_STORY
ADD_PERSON
```

X1.1 accepts all 20 selected Stories into a research review overlay because
their canonical source, stable identity, and local evidence route pass the
screening gate. This is not production publication: reader punctuation,
scene participation, and fact-level semantic review are deferred to HG1.1.

The epoch therefore canonicalizes zero new facts, zero new Persons, and zero
production Stories. It records 88 source-backed coverage targets as candidate
`ADD_FACT` review actions and eight unresolved identity surfaces as
`ADD_PERSON` identity-review actions. A PersonStory link remains an identity
route only; it does not imply Story participation.

Each record keeps `selection_status`, `review_status`, and
`acceptance_status` separate. A candidate review action is never silently
promoted to canonical truth.

The preferred review order remains `ADD_FACT` before `ADD_STORY` before
`ADD_PERSON`. No Person ID is allocated by X1.1, and no model output creates a
fact, participant, alias, Relation, or Person.

## Counter-model and ontology review

The first counter-model batch contains three qualified Stories. Their
independent signals include source/evidence quality, chapter coverage, and
reviewable office, event, family, location, or unresolved-identity surfaces.
The batch surfaces seven recurrent semantic candidates, including literary
association, teacher–student context, reputation/evaluation, marriage
mediation, office sponsorship, and retreat/reclusion. These are ontology-gap
candidates only. X1.1 does not add HG0 edge types or turn lexical surfaces
into Relations.

## Information gain and bias audit

Information gain is reported separately for each channel as accepted review
overlay Stories, candidate fact targets by layer, external-layer potential,
bridge Stories, evidence coverage, identity-review candidates, and ontology
surfaces. Values are normalized per selected Story only for comparison within
this small pilot; they are not historical importance scores or causal results.

The bias audit compares chapter, participant-count band, missing-layer
coverage, current Person-degree proxy, and top-Person concentration. A high
degree means representation in the current corpus, not historical importance.
The published corpus and surviving local sources are selection biases that
must remain visible.

## X1.2 recommendation

This epoch recommends a 30/40/15/15 graph/coverage/random/counter balance for
X1.2 because coverage review produced more observed review-queue and
structural units per selected Story. The recommendation is not executed by
X1.1. Office, event, temporal, and family targets should receive source-level
review before broad Story materialization. Story expansion should remain
selective and source-gated; Person expansion should wait for a secure
non-production identity bridge. Stratified-random and counter-model channels
retain long-term floors of 10% each.

## Epistemic contract and stop condition

```text
model recommendation != historical fact
model rejection != historical irrelevance
counter-model candidate != anomalous historical data
random sample != low-quality sample
expansion utility != historical importance
missing edge != negative relation
unknown > false precision
```

All X1.1 artifacts are deterministic, research-only JSON projections. H0C
participant freeze, H0C facts, HG0 graph/ontology, ML0 outputs, production
Persons, production Stories, and existing Relations remain protected. X1.1
stops after candidate qualification, frozen selection, review screening,
comparative audit, ontology-gap reporting, and the next-epoch recommendation.
HG1.1, ML1.1, ER2, new GNN training, embedding updates, UI expansion, and
historical-importance or faction inference are out of scope.
