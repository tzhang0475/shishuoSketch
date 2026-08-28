# HGE1-WB — Adaptive Wave B network growth

HGE1-WB is the second candidate-only Story expansion wave.  It reads the
frozen HGE1-WA channel yields, then selects 24 research-only Stories with a
deterministic adaptive mixture:

| selection channel | Stories |
| --- | ---: |
| exploitation: relation-rich | 6 |
| exploitation: underrepresented | 6 |
| coverage: peripheral | 4 |
| coverage: underrepresented | 3 |
| deterministic random control | 5 |

The selection is frozen before semantic calls and is disjoint from the
production Story set, the previous HNG/HDB/PSL exclusion snapshot, and HGE1-WA.
Each Story receives one deterministic Person target.  Wave B uses the same
HNG2-C.3/HDB2-P2T READ/FILL implementation as Wave A; it does not consume Wave
A candidate state as a semantic input and does not allocate production Person
IDs.

## Run result

The run scheduled 96 semantic calls (24 Person READ/FILL pairs and 24 Temporal
READ/FILL pairs).  All 48 Person calls parsed.  The provider became unavailable
after 63 total semantic responses, leaving 33 Temporal requests explicitly
listed as pending in `production-summary.json`; no fallback result is presented
as a completed live Temporal read.  The raw run remains immutable and the
candidate projections can be rebuilt offline.

Wave B produced 24 candidate Person observations, 24 provisional candidate
Persons, 34 validated relation observations, and eight temporal assertions from
the completed Temporal portion.  No existing Person was resolved by this
wave.  The projection is candidate-only.

| metric | baseline | after Wave A | after Wave B |
| --- | ---: | ---: | ---: |
| Stories | 143 | 163 | 187 |
| existing Persons | 75 | 75 | 75 |
| candidate Persons | 13 | 33 | 57 |
| PersonStory links | 330 | 350 | 374 |
| graph nodes | 347 | 387 | 435 |
| graph edges | 996 | 1,016 | 1,040 |
| connected components | 6 | 26 | 50 |
| largest component | 342 | 342 | 342 |
| unresolved identity count | 42 | 42 | 42 |

The graph edge count deliberately counts safe candidate Person–Story links;
candidate relation observations are reported separately.  Wave B’s node
novelty rate is `1.0` candidate node per Story, its candidate node novelty rate
is `1.0`, its safe graph-edge novelty rate is `1.0`, and its existing-node
densification rate is `0.0`.  It added nine kinship candidates, one marriage
candidate, one office/institutional candidate, and 34 relation observations.

The five-channel marginal result is:

| channel | Stories | new candidates | relation observations | review items |
| --- | ---: | ---: | ---: | ---: |
| exploitation / relation-rich | 6 | 6 | 8 | 6 |
| exploitation / underrepresented | 6 | 6 | 9 | 6 |
| coverage / peripheral | 4 | 4 | 8 | 4 |
| coverage / underrepresented | 3 | 3 | 2 | 3 |
| random control | 5 | 5 | 7 | 5 |

Because the provider interruption affected only the latter Temporal calls,
Temporal yield is a partial-live diagnostic, not evidence of a complete
Temporal-wave comparison.  With two waves, the provisional coverage diagnosis
is **continuing_node_expansion**, with no measured transition to graph
densification: every newly selected target formed a candidate Person–Story
component and no existing Person–Person edge was completed.  This is not a
saturation claim.  A later wave should preserve coverage and random controls
until complete temporal measurements are available; HDA2 identity review is a
higher-priority prerequisite for interpreting network links.
