# ML0 — Bias-Controlled Historical Graph Learning Pilot

ML0 is a research projection downstream of the frozen HG0 Historical Graph.
It asks what the current graph can reconstruct, how much of that signal is
textual/Story structure, and which historical layers should receive the next
targeted data work. It does not add historical facts and does not interpret a
model output as historical truth.

The protected hierarchy is:

```text
H0C canonical facts
        ↓
HG0 graph projection
        ↓
ML0 dataset views and experiments
        ↓
X1 recommendation only
```

ML0 never writes to Persons, Stories, Mentions, PersonStory, Relations,
participant freeze, H0C facts, or HG0 graph truth.

## Runtime and deterministic builder

The builder is:

```text
scripts/build_ml0_pilot.py
```

The validator is:

```text
scripts/validate_ml0.py
```

The execution environment for this milestone has NumPy 1.26.4 and SciPy but
does not have PyTorch or PyTorch Geometric. ML0 therefore uses a small custom
NumPy two-layer relation-aware message-passing model (an R-GCN-style pilot).
It has typed forward/reverse relation parameters, degree-normalized messages,
and a typed observed-edge reconstruction objective. This is an isolated pilot,
not a normal application dependency. A future PyTorch implementation can
consume the same dataset contract.

The builder fixes all split and model seeds, sorts node and relation mappings,
uses deterministic hash-based corruptions, fixes the training budget, and
does not persist checkpoints or embeddings. Rebuilding unchanged HG0 inputs
produces byte-identical ML0 JSON artifacts in the repository environment.

## Dataset views

The dataset manifest uses the 347-node, 996-edge published Story-scope HG0
graph. The global PersonStory index remains wider than this graph; out-of-
scope links are not turned into dangling ML nodes.

The views are:

| View | Meaning | Edges in current build |
| --- | --- | ---: |
| `G_story` | HG0 edges carrying the Story layer | 688 |
| `G_external` | Non-textual layers with no Story layer and no Story endpoint | 229 |
| `G_all` | All HG0 edges | 996 |
| `G_reviewed` | Reviewed edges only | 351 |
| `G_reviewed_plus_candidate` | Reviewed and candidate edges | 996 |
| `G_temporal_bounded` | Bounded or one-sided temporal edges only | 290 |

`G_external` intentionally excludes Event→Story, ServiceContext→Story, and
Story→Location bridges. Those edges may be valuable in `G_all`, but they can
leak textual Story context into a PersonStory reconstruction task. No
Person–Person co-occurrence edges are synthesized to make the external view
look denser.

Node indices are sorted by `(node_type, canonical node_id)`. Edge and directed
relation mappings are deterministic. Features are auditable raw structure:
node-type one-hot columns and `log1p` typed layer/edge/review/temporal/scene-
role incidence counts. Names, labels, and canonical IDs are never predictive
feature values.

## Task and missingness

The primary task reconstructs held-out *observed* published-scope
`person_story_link` edges. The deterministic split holds out 66 of 330 links,
and removes every context edge with the same Person→Story endpoint pair from
the context graph. This blocks direct duplicate support such as a participant
edge from trivially exposing the held-out link.

Computational endpoint corruptions are used only for contrastive/ranking
evaluation. They are deterministic, type-constrained, avoid all observed
positive PersonStory pairs, and never enter canonical or HG0 data. The
following distinctions remain explicit:

```text
missing edge != negative historical fact
unknown != false
candidate != reviewed
model similarity != historical similarity
```

MRR and Hits@K describe ranking of observed positives against these temporary
corruptions. They do not estimate the truth of an unobserved relationship.

## Structural baselines

Each main view receives three transparent baselines:

1. typed structural features: degree, typed two-hop overlap, and feature
   cosine;
2. an SVD of the context Person×Story incidence matrix;
3. typed relation-count/neighborhood overlap.

They provide a reference for deciding whether message passing adds signal
beyond simple graph statistics. A constant scorer receives average rank for
ties, not rank one.

## Relation-aware model and ablations

The R-GCN-style pilot has two tanh message-passing layers, separate relation
parameters for every HG0 edge type and its reverse direction, symmetric degree
normalization, a fixed 16-dimensional hidden state, 60 epochs, learning rate
0.01, and a small deterministic corruption set. Five seeds are used for
`G_story`, `G_external`, `G_all`, and `G_reviewed`; three seeds are used for
candidate sensitivity, strict temporal, and layer ablations.

The controlled comparisons are:

```text
G_story
G_external
G_all
G_reviewed
G_reviewed_plus_candidate
G_temporal_bounded
G_all minus family/clan/office/event/geographic/service_political
```

For representations, ML0 reports pairwise-distance correlation, nearest-
neighbor overlap at five, and Procrustes similarity over the 75 Person rows.
These are model-space stability diagnostics only. They are not social
distance or historical similarity measures.

## Current diagnostic result

The current reproducible run is:

```text
GNN runs completed: 44 / 44
G_all MRR:          0.3557 ± 0.0290
G_story MRR:        0.3023 ± 0.0441
G_external MRR:     0.1667 ± 0.0000
```

The strict external view reaches the tie baseline for this Story-link task.
That is expected: its Story nodes are isolated by definition, so it is not a
fair standalone Story-link predictor. It is still useful for measuring the
Person-side representation and for exposing the boundary between external
historical structure and textual context.

The current classification is:

```text
graph_trainability:       stable
Story dominance:          mixed signal
external historical signal: weak for the pure external view
link reconstruction:      pilot_only
temporal ML:              pilot_only
```

`G_all` is not a simple copy of `G_story`: Person representation pairwise
distance correlation is about 0.662, with nearest-neighbor overlap about
0.412. The full graph therefore contains mixed signals, but this must not be
read as proof that external edges encode a complete historical social graph.
The full graph still contains 83.95% Story-related H0C semantic structure and
the published corpus is editorially selected.

Candidate sensitivity is measured by comparing `G_reviewed` and
`G_reviewed_plus_candidate`; a representation shift is epistemic sensitivity,
not evidence that candidate facts are wrong. Layer ablations show that the
current sparse family, clan, office, event, geographic, and service layers
change the representation to different degrees, but their graph readiness
remains constrained by HG0 coverage and review status.

The temporal feasibility artifact constructs deterministic pre-cutoff,
post-cutoff, and potentially-active interval views from bounded HG0 edges. It
keeps 706 unknown/relative edges in a separate bucket and verifies that no
unknown edge enters a pre-cutoff view. This is a leakage-prevention contract,
not a temporal prediction result.

## X1 recommendation boundary

ML0 emits `data/derived/ml0-expansion-recommendation.json`. The current output
recommends targeted X1 planning rather than broad Story or Person expansion:

- enrich office, family, event, and temporal evidence selectively where local
  provenance can close documented gaps;
- use geographic and service/political work as targeted follow-up rather than
  graph-density optimization;
- select future Stories for their ability to activate source-backed external
  historical context, not for raw count;
- promote only secure Person identities that are necessary structural bridges;
- do not rank Persons by model score, centrality, fame, or inferred historical
  importance.

This is a data-priority recommendation only. X1 is not implemented here.

## Explicit non-goals

ML0 does not produce:

```text
political factions
historical importance rankings
personality or archetype clusters
event prediction
learned historical relations
canonical negative facts
production embeddings or Person attributes
```

No model output is historical fact. No embeddings or checkpoints are
persisted. X1 and ER2 are future work.
