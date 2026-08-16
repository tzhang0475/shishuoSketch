# X1.2A — Evidence Review & Controlled Historical Materialization

X1.2A is the review gate between the frozen X1.1 expansion overlay and any
future corpus or graph migration. X1.1 decided where to look; X1.2A decides,
from local historical evidence, what is allowed to become canonical
information.

The pipeline is deliberately one-way:

```text
frozen X1.1 selection
        ↓
Story / identity / fact / ontology review
        ↓
accepted | unresolved | rejected
        ↓
X1.2A canonical extension
```

The X1.1 selection score, model rank, and selection channel are research
provenance. They explain why an item was reviewed, but they are never
evidence for a historical assertion. Unknown remains preferable to false
precision, and a missing relation is not a negative relation.

## Frozen review inputs

The review consumes the frozen X1.1 candidate pool, selection manifest,
review overlay, counter-model set, ontology-gap candidates, information-gain
audit, bias audit, and next-epoch recommendation. The input hashes are
recorded in every X1.2A artifact. No second Story batch is selected and the
X1.1 selection is not rescored after review begins.

The review covers:

* 20 selected Stories;
* 8 identity-review candidates;
* 88 `ADD_FACT` candidate targets; and
* 7 ontology-gap candidates.

Every item receives a terminal top-level review state. Ontology candidates
use the same state vocabulary for review, while an accepted ontology review
is only a recommendation: the HG0 ontology is not changed in this milestone.

## Review order and Story boundary

Review order is Story integrity, identity, fact semantics, cross-fact
consistency, ontology-gap review, and materialization. A selected Story must
have stable local source identity, source/evidence links, a non-duplicate
canonical identity, and an acceptable punctuation gate before it can enter
production Story scope.

All 20 selected Stories have stable local source entries and evidence, but
their punctuation records remain candidate/unreviewed. They therefore remain
research overlays rather than production Stories. This is intentional: X1.2A
does not reopen the prior punctuation exclusion or edit canonical source
text. Independent facts may still be accepted when their local evidence is
clear and does not require publishing the Story.

PersonStory and Mention rows are not hard participation. A future Story
promotion must separately review `present`, `speaker`, `actor`,
`referenced`, `off_frame`, `annotation_only`, and `uncertain` semantics.

## Identity review

Identity decisions are occurrence-local. The accepted decisions resolve
already canonical Persons where the local Liu annotation or a local
antecedent is explicit:

* `郗公` in `01-dexing-024` → `person-002 郗鑒`;
* the relevant `王丞相` / `丞相` surfaces in `02-yanyu-033` →
  `person-003 王導`;
* `王公` in `23-rendan-032` → `person-003 王導`; and
* `王公` in `26-qingdi-004` → `person-003 王導`.

Three title surfaces remain unresolved because a global title mapping would
be unsafe. Accepted identity overlays are deferred while their parent
Stories remain outside production; no new Person is allocated in X1.2A.

## Fact review and materialization

The review accepted seven candidate fact items. They materialize as nine
typed facts and three extension entities, because one office item produces a
reusable Office and typed location fact, one service item represents two
explicit `served_under` endpoints, and event review produces one new Event
plus four Story–Event context facts.

The materialized extension contains:

* one `OfficeTenure` for `person-061 習鑿齒` as `荊州治中`, with unknown
  tenure dates;
* one typed `held_office_at` location fact for historical `荊州`, without
  invented modern coordinates;
* two explicit, non-Relation `served_under` facts for `person-014 王濛` and
  `person-018 謝尚` under `person-003 王導`; and
* one local `齊萬年反` Event plus four context-only Story–Event facts,
  reusing the existing Eight Princes event where appropriate.

Event background is not converted into EventParticipation. The event
context facts are explicitly not hard-temporal eligible and do not rewrite
H0A. No reviewed Relation, StoryParticipant, production Story, or Person is
created by these facts.

The accepted facts live in
`data/derived/x1-2a-canonical-facts.json`, whose scope is
`x1-2a-canonical-extension`. This is a canonical, reviewed X1.2A result, but
it is intentionally not silently merged into the frozen H0C/HG0 production
projections. A later explicit corpus/graph migration must consume it. This
keeps the protected H0C participant freeze, production indexes, and HG0
truth boundary reproducible.

Family, clan, temporal-keyword, unsupported geographic, unresolved event,
and ambiguous service candidates remain unresolved or rejected. In
particular, surname, co-occurrence, model similarity, and candidate volume
cannot establish ClanMembership or kinship, and office wording does not
invent absolute dates.

## Ontology-gap review

All seven X1.1 ontology-gap candidates are reviewed as recommendations. They
are retained as possible future semantic types or covered-by-existing
semantics according to their review record, but `ontology_change_count` is
zero. X1.2A does not add graph edge types. Future promotion requires repeated
independent occurrences, clear source support, semantic distinctness from
the existing ontology, and low interpretive ambiguity.

## Realized yield and channel comparison

The realized canonical yield is measured separately from X1.1 proxy units.
For this small epoch the result is:

| X1.1 channel | Selected Stories | Canonical Stories | Canonical Persons | Canonical extension facts |
| --- | ---: | ---: | ---: | ---: |
| graph-guided | 8 | 0 | 0 | 2 |
| coverage-guided | 6 | 0 | 0 | 5 |
| stratified-random | 3 | 0 | 0 | 2 |
| counter-model | 3 | 0 | 0 | 0 |

The accepted fact count is nine rather than seven candidate items because
accepted semantics can expand into multiple typed records. These figures
are observed information gain, not historical-importance scores and not a
statistical comparison of selection strategies.

The counter-model set produced a possible blind-spot signal through a local
title/identity review in `02-yanyu-033`, but no new canonical Story, Person,
or fact from that channel. The other counter-model items were weak after
strict evidence review. The random control independently yielded reviewed
event-context material, demonstrating why it must remain separate from model
ranking.

Post-review bias and gap artifacts report Person concentration, existing
degree, layer yield, publication gates, endpoint gaps, chronology gaps, and
ontology candidates. They do not treat imbalance as an error or close a gap
for graph utility.

## X1.2B recommendation

The realized result recommends the provisional next-epoch allocation:

```text
graph-guided       30%
coverage-guided    40%
stratified-random  15%
counter-model      15%
```

This is a recommendation only. Coverage produced more accepted extension
facts per selected Story than graph-guided review in this small sample.
Office and explicit event layers are high priority; typed geography is
medium priority; family and service/political review remain conditional;
clan review remains low until explicit branch evidence appears. The random
and counter-model channels retain 15% each, above the long-term 10% floors.
Story expansion remains selective until punctuation and participant gates
are reviewable. Person expansion remains deferred until a secure
non-production identity is independently supported.

## Protection and stop boundary

X1.2A records input/protection hashes, stable IDs, evidence references,
selection-channel provenance, review states, materialization provenance,
conflicts, and unresolved gaps. It never writes ML scores into canonical
facts, turns model output into historical facts, or changes H0C/HG0/ML0
truth. Source text and witnesses remain untouched.

X1.2A stops after evidence review, controlled extension materialization,
realized-yield and bias audits, and the X1.2B recommendation. X1.2B, HG1.1,
ML1.1, new GNN training, embeddings, ontology expansion, political-faction
inference, and ER2 are explicitly out of scope.
