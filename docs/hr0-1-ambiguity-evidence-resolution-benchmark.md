# HR0.1 — Ambiguity & Evidence Resolution Benchmark

HR0.1 is a downstream benchmark projection over the 19 reviewed HR0
`HistoricalSituation` records. It does not change the HR0 Gold Set, canonical
Stories, Persons, facts, Relations, or source witnesses.

## Two-pass structure

Each Story has two views:

```text
Pass A: shishuo_only_gold
    only evidence whose source layer is base_text is available

Pass B: evidence_resolved_gold
    the reviewed HR0 situation plus explicit evidence-backed refinements
```

The Story surface, episode identifiers, participant roles, and observed title
surfaces remain stable across views. The Shishuo-only view removes endpoint
resolution that depends on annotation or other non-base evidence, marks the
item's availability, and keeps the ambiguity visible. The evidence-resolved
view restores only reviewed endpoints already supported by the HR0 record or
the explicit HR0.1 resolution specification.

The benchmark is emitted by:

```text
scripts/build_hr0_1_resolution_benchmark.py
```

and stored in:

```text
data/derived/hr0-1-ambiguity-benchmark.json
```

## Evidence Resolution Cases

The benchmark contains 46 cases:

| Dimension | Cases |
| --- | ---: |
| temporal relation | 16 |
| identity | 12 |
| title identity | 6 |
| comparative evaluation | 5 |
| participant presence/reference | 7 |

Thirty-seven cases are derived one-for-one from the reviewed HR0 uncertainty
records. Nine additional cases make already reviewed local identity/title
resolutions explicit for the two-pass benchmark, including `明帝 →
ruler-jin-mingdi` and `温太真 → person-013` in `05-fangzheng-032`.

Every case carries:

```text
uncertainty_id
dimension
shishuo_status
resolved_status
resolved_value
requires
evidence_refs
```

It also records separate Shishuo-only and resolution evidence references and
the affected situation items. A resolved/refined case must have an explicit
evidence reference; unresolved cases retain a null resolved value. The
`unresolved_even_with_available_evidence` state is used when the available
annotation evidence does not safely close the ambiguity.

## Dependency distribution

The current 19-Story HR0 evidence universe yields these explicit dependency
counts:

| Dependency | Cases |
| --- | ---: |
| `liu_annotation` | 17 |
| `canonical_fact` | 9 |
| `jianshu` | 0 |
| `external_source` | 0 |

The zero counts for Jianshu and external source dependencies are a statement
about the current HR0 input references, not a restriction of the schema. The
benchmark accepts those dependency types for future evidence-augmented
examples, while this snapshot uses only the evidence already attached to HR0.

Overall, 28 cases are resolved or refined and 18 remain unresolved (11
`unresolved` and 7 `unresolved_even_with_available_evidence`). Unresolved
identity, title, participant-scope, and temporal cases are not converted into
negative assertions or guessed endpoints.

## Validation and provenance

`scripts/validate_hr0_1.py` checks:

- the exact 19-Story HR0 universe;
- all 37 HR0 uncertainties plus all explicit HR0.1 cases;
- Story, Person, ruler, and evidence references;
- dependency evidence unions and source-layer requirements;
- resolved values and unresolved-state consistency;
- preservation of observable surfaces and episode/role semantics;
- absence of date-answer fields;
- HR0/H0C/HG0/ML0 protection hashes and no-write-back flags;
- deterministic rebuild equality.

The generated benchmark and metrics use sorted collections, repository-
relative input paths, stable JSON serialization, and no wall-clock fields.

## Schema issues surfaced

HR0 already preserved evidence IDs and source layers, but it represented a
single reviewed situation view. HR0.1 therefore adds a benchmark-level view
wrapper, per-item availability, and assertion-level resolution dependencies
without modifying the HR0 schema. The existing source vocabulary currently
distinguishes `base_text` and `liu_annotation`; the benchmark maps future
secondary-reference evidence to `external_source` and leaves `jianshu` as an
available explicit dependency type rather than inventing new evidence records.

## HR1 readiness

The dataset is ready to serve as deterministic specification, few-shot
examples, and benchmark input for HR1's two-pass evaluation:

```text
Pass A: Shishuo-only interpretation
Pass B: evidence-augmented interpretation
```

It is not an LLM evaluation run. HR0.1 performs no LLM/API calls, retrieval,
RAG, temporal solving, or canonical fact materialization. A resolved benchmark
value means that ShishuoSketch has a reviewed evidence dependency for that
projection; it does not claim unquestionable historical truth.
