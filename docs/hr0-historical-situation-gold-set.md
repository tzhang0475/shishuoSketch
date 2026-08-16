# HR0 — HistoricalSituation Gold Set

HR0 defines the first reviewed `HistoricalSituation v0` set for the existing
ShishuoSketch corpus. It is a data/specification milestone, not an inference
or historical-fact materialization milestone.

## Scope and selection

The pilot contains 19 existing evidence-rich Stories. Selection is frozen in
[`hr0-selection-manifest.json`](../data/derived/hr0-selection-manifest.json)
and the reviewed annotation input is tracked at
[`hr0-gold-spec.json`](../data/annotation/hr0-gold-spec.json).

Selected Stories:

```text
02-yanyu-035  02-yanyu-036  02-yanyu-069  02-yanyu-079  02-yanyu-083
04-wenxue-036 04-wenxue-094 05-fangzheng-023 05-fangzheng-028
05-fangzheng-031 05-fangzheng-032 05-fangzheng-055
06-yaliang-017 06-yaliang-027 06-yaliang-029 08-shangyu-077
09-pinzao-017 19-xianyuan-026 27-jiajue-008
```

The selection covers simple and multi-episode Stories, reported and
retrospective layers, presence versus reference, ambiguous titles, Liu
Xiaobiao-dependent interpretation, unresolved identity surfaces, family
context, event context, and comparative/evaluative speech. The selection is a
representative specification pilot, not a fame, centrality, or historical
importance ranking.

## HistoricalSituation v0

The formal schema is
[`historical-situation.schema.json`](../schema/historical-situation.schema.json).
Each reviewed record contains:

| Field | Purpose |
| --- | --- |
| `episodes` | Story-local episodes or reported/contextual layers, with kind, presence scope, assertion status, and evidence IDs. |
| `participant_states` | Person surfaces and situation-local roles such as `speaker`, `actor`, `referenced`, `annotation_only`, or `uncertain`. Unresolved surfaces remain visible with a null endpoint. |
| `temporal_relations` | Relative/order/event-anchor relations with `exact`, `bounded`, `broad_period`, `relative`, or `unknown` precision. HR0 intentionally has no date-answer fields. |
| `person_states` | Situation-local office, action, family, evaluation, identity, or reported-outcome states. These are not canonical fact writes. |
| `title_mentions` | Title, courtesy-name, office-title, and ruler surfaces with explicit endpoint and ambiguity state. |
| `evidence_refs` | Deduplicated evidence references enriched from the current SC1 evidence registry, including source layer, quote fingerprint, locator, witness, and source hash. |
| `uncertainties` | Explicit open or bounded uncertainty about time, identity, participant scope, title semantics, episode boundaries, and comparisons. |

`review_status = reviewed_gold` describes the review of the situation
annotation. It does not upgrade the underlying source record or turn a Liu
annotation into an independently verified primary source.

## Evidence and uncertainty policy

HR0 reuses existing SC1 IDs and provenance. `primary_text` is represented as
`base_text`; `annotation` as `liu_annotation`; existing editorial and
secondary evidence layers remain distinct. Every episode, participant state,
person state, title mention, temporal relation, and uncertainty has at least
one evidence ID. The validator checks that every reference resolves to the
current evidence object and that its locator and source provenance are copied
without alteration.

The pilot deliberately preserves cases such as `許玄度`, `謝公`, `王右軍`,
`桓子野`, and `王坦之` as unresolved or ambiguous where the existing
canonical endpoint is not safe. A reference in Liu annotation is not promoted
to a hard participant. A comparative statement is retained as a comparative
situation state, not as a global person ranking or a new relation.

Temporal annotation uses only text-supported sequence, relative, event, or
unknown states. Existing derived Story dates and temporal projections are not
copied into the Gold set as answers.

## Counts

The deterministic build produces:

```text
Stories:             19
episodes:            27
participant_states:  54
person_states:       25
temporal_relations:  22
title_mentions:      31
unique evidence IDs: 34
evidence references: 34
uncertainties:        37
```

The largest review surfaces are `presence_reference` (13 Stories),
`liu_dependent_interpretation` (10), `simple_single_episode` (10),
`ambiguous_title` (9), and `multi_episode` (8). There are 39 resolved and 15
unresolved/ambiguous participant states, and 24 resolved and 7
unresolved/ambiguous title mentions. These are coverage diagnostics, not
confidence scores.

## Artifacts and validation

The derived Gold set is
[`hr0-historical-situations.json`](../data/derived/hr0-historical-situations.json).
The builder is [`build_hr0_historical_situations.py`](../scripts/build_hr0_historical_situations.py),
and the validator is [`validate_hr0.py`](../scripts/validate_hr0.py).
Supporting deterministic artifacts are the selection manifest, metrics, and
read-only protection manifest in `data/derived/hr0-*.json`.

The validator checks JSON Schema validity, frozen Story scope, Story/Person/
ruler/evidence endpoints, episode references, evidence provenance and quote
fingerprints, enum values, source hashes, unresolved endpoint behavior, the
absence of derived date answer fields, and two in-memory builds for
determinism. The builder has no write path to canonical Stories, Persons,
Mentions, Relations, H0C facts, HG0, or ML0.

## Unresolved schema issues

The v0 schema intentionally leaves several questions for HR1:

* whether `person_states` should be split into a more formal assertion/event
  model when repeated across more Stories;
* how to represent a safe identity endpoint for a title that is locally
  resolved to a ruler but not a Person;
* whether relative temporal relations need a shared event-anchor vocabulary;
* how to represent annotation claims whose quoted historical source is not
  independently available;
* how much participant-state granularity is needed for dialogue turns and
  reported speech.

These are specification questions. HR0 does not add ontology types, Persons,
Facts, Relations, dates, or inferred edges to resolve them.

## HR1 recommendation

Use this Gold set as the reviewed specification, few-shot example pool, and
benchmark input for HR1. HR1 should first test schema-constrained extraction
and evidence-link completeness against these records, with explicit negative
cases for unresolved identity, annotation-only people, comparative language,
and unknown time. It should not assume that the 19 records define a complete
historical universe, and it should preserve the same fact/graph/read-only
boundary.

## Explicit stop boundary

HR0 performs no LLM inference, API calls, RAG retrieval, vector indexing,
temporal solving, or canonical fact materialization. Existing canonical
historical data remains read-only. HG1.1, ML1.1, X1.2B, and ER2 are outside
this milestone.
