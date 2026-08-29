# SFH2 / HIR1 — Collective Identity Consolidation

SFH2 is an additive, candidate-only projection over the frozen SFH1 reading
universe. Its purpose is to measure the difference between a mention, a
candidate observation, a candidate entity hypothesis, and a historical Person.
The 542 SFH1 candidate Person IDs are therefore treated as observation-level
labels to audit, not as a count of 542 new people.

## Frozen boundary

The input manifest freezes the 188 SFH1 Stories, validated mentions,
reference semantics, candidate sets, identity judgments, constrained/final
decisions, semantic relations, temporal semantics, Person catalogue, aliases,
HDB2-F profile integrity projection, HDA2 repair overlay, and the SFH1
recalibrated growth series. Its hash is checked before each run. SFH2 does
not add Stories, rewrite SFH1, or write `data/people.json` or canonical facts.

Every output is marked `candidate_only=true` and
`canonical_write_back=false`.

## Pipeline

1. Build one `CandidateObservation` per SFH1 mention that carries a prior
   candidate ID, retaining the source span, Story/Liu evidence, previous
   decision, temporal context, and relation context.
2. Retrieve possible existing Persons from canonical names, valid aliases,
   provenance-backed HDB2 profile forms, HDA2 filtering, and local context.
   Candidate keys—not production IDs—are exposed to the link judge.
3. Use the frozen SFH1 stable occurrence decisions and bounded, grounded
   existing-Person judgments before making candidate clusters.
4. Generate a sparse comparison graph with deterministic blocking. Shared
   surfaces, prior candidate IDs, Story, neighbors, and temporal forms are
   retrieval keys only. They never merge identities by themselves.
5. Reuse validated SFH1 coreference/distinctness edges and use the configured
   model only for the remaining pair judgments. DSU clustering is permitted
   only after explicit-distinct vetoes and cluster consistency checks.
6. Reproject relation endpoints and construct separate candidate-only graph,
   Person knowledge, family, marriage, office, failure, and audit views.

This preserves the SFH1 authority boundary: LLM judgments interpret supplied
historical evidence; Python validates evidence, owns IDs, applies hard vetoes,
maintains provenance, and controls storage.

## Observed run

The run retained 188 Stories and 2,867 person mentions. It contains 597
candidate observations (594 eligible for candidate-entity clustering) derived
from 542 prior candidate IDs. A bounded live attempt produced 128 raw
existing-Person responses; 25 remain replayable under the final prompt. The
remaining calls and candidate-pair judgments were kept fail-closed when no
cached response was available. No provider
failure is converted into an identity assertion.

The resulting decomposition is:

| projection | count |
| --- | ---: |
| candidate observations | 597 |
| candidate observations absorbed into existing Persons | 5 |
| candidate observations merged into candidate entities | 238 observation units |
| unique candidate entity clusters | 356 |
| anonymous/structural references | 834 |
| unresolved entity references | 1,479 |

The 5 absorbed observations map to 5 existing Persons; the complete SFH1
universe reaches 56 of the 75 production Persons. These counts are not a
canonical identity promotion and retain occurrence provenance.

For the relation projection, 574 SFH1 rows had previously been marked
complete. SFH2 classifies 542 rows as candidate-aware endpoint-complete:
153 both-existing, 209 existing-plus-candidate, and 180 both-candidate.
The stricter endpoint typing also leaves 637 single-endpoint rows, 150 both
unresolved rows, and 880 structural-reference rows. This is a change in
classification, not a new relation assertion.

The SFH2 projection contains 1,582 nodes and 3,410 candidate relation/Story
edges, with 50 components and a largest component of 1,336 nodes. The prior
SFH1 Wave B reference was 468 nodes, 1,105 edges, 45 components, and a
largest component of 345. Because the SFH2 graph includes the complete
188-Story observation projection and explicitly typed candidate/structural
nodes, these totals are diagnostic projections rather than a replacement for
the canonical HG0 graph.

The recalibrated SFH2 growth series preserves the SFH1 series separately.
After consolidation, candidate-entity novelty is 2.1 per Story in Wave A and
0.916667 per Story in Wave B; candidate-observation novelty is 3.45 and
1.458333. Candidate-aware existing-Person densification is not demonstrated
by the current cached run (0 new both-existing edges in either added wave).
The fall in entity novelty is consistent with duplicate consolidation, but
two waves are not enough to claim saturation.

## Cost and replay

`cost-metrics.json` separates provider attempts from replayed cache work. The
current replay used 25 cached responses (36,621 prompt and 8,403 completion
tokens; 45,024 replayed tokens) and made zero new live calls. There were 2,805
offline cache misses, recorded as unresolved/fail-closed work. Raw provider
responses remain under the versioned SFH2 live directory; no new responses are
fabricated during offline replay.

The next implementation should add cached pair/cluster judgments or a
cluster-level verification pass only where blocking and evidence justify it.
It should not turn same-surface equality into a merge rule, and should keep
the human audit focused on high-degree candidate clusters, existing-Person
links, explicit distinctness, and unresolved family/office references.

## Limitations and migration decision

The current provider attempt stopped during a bounded run after the initial
link batch; pair judgments without cached responses remain fail-closed. This
means the measured 356 clusters are a conservative experimental projection,
not a complete historical consolidation. The graph comparison also combines
different projection scopes and must not be read as canonical network growth.

SFH2 is not ready to replace SFH1/HDB2 in production. The appropriate next
phase is **SFH2.1 — targeted human identity audit**, beginning with the
candidate-to-existing links and high-degree candidate clusters. No canonical
materialization or new Story wave is authorized by this artifact.
