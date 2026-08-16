# X1.2P — Story Punctuation Gate Resolution

X1.2P is a narrow text-integrity gate between the frozen X1.1 selection and
any future Story release. It does not select replacement Stories, repair
the corpus broadly, or accept historical facts. Its question is why the 20
X1.1 Stories entered the research candidate pool but all stopped at the
X1.2A production punctuation gate.

## Gate finding

The mismatch is intentional two-tier policy, not stale metadata, a validator
bug, or an implementation error.

X1.1 candidate qualification requires a canonical source, a stable source
hash, local evidence, a PersonStory identity route, and a punctuation record
that is present and not explicitly disputed. This permits `candidate` /
`reference_candidate` records into a research-only selection batch.

X1.2A production Story admissibility requires explicit reviewed punctuation:

```text
status = reviewed
review_status = reviewed
punctuation_basis = human_reviewed
```

The local punctuation-bearing witness is recorded as
`provisionally_qualified`. It is suitable for structural and exact-character
transfer analysis, but its tracked qualification explicitly does not permit
trusted-reference or reader-ready promotion. Exact transfer therefore
remains an alignment fact, not editorial approval.

All 20 selected Stories pass source identity and evidence traceability. Their
punctuation records are `candidate` / `unreviewed` /
`reference_candidate`, so none passes the production punctuation gate. The
gate contract, implementation locations, reject conditions, and per-Story
gate results are recorded in
`data/derived/x1-2p-punctuation-gate-audit.json`.

## Story-level review

The frozen X1.1 set is the complete X1.2P review universe:

| punctuation surface | count | outcome |
| --- | ---: | --- |
| exact character transfer from the local witness | 3 | unresolved: insufficient independent local editorial evidence |
| character variant around punctuation | 17 | unresolved: source-witness conflict |

The three exact-transfer Stories are `02-yanyu-102`, `23-rendan-032`, and
`26-qingdi-004`. The 17 variant Stories cannot safely use the reference
punctuation without importing a character variant or making a textual
emendation. The exact-transfer Stories have no tracked independent
punctuation-bearing editorial source, so X1.2P does not promote them merely
because the stripped characters match.

No punctuation record is modified. Every review record carries the old and
new values (which are equal), source-reference hashes, X1.2A evidence links,
selection provenance, and the reason no change was applied. Selection mode
does not affect textual judgment:

```text
graph-guided       0/8 resolved
coverage-guided    0/6 resolved
stratified-random  0/3 resolved
counter-model      0/3 resolved
```

This is a textual-admissibility result, not a model-quality comparison.

Story identity and punctuation confidence remain separate. The participant
gate from X1.2A is still `not_evaluated`; passing punctuation in a future
review would not automatically promote PersonStory or Mention rows to hard
participation.

## Dependency audit

All 58 unresolved X1.2A fact candidates occur in Stories whose punctuation
remains unresolved. They are therefore blocked by the Story gate, but
punctuation passage alone would not accept them:

* 40 also retain semantic uncertainty (family, geography, or
  service/political semantics); and
* 18 also retain insufficient evidence (office or event semantics).

All three unresolved identity candidates are blocked by the Story gate and
retain independent identity ambiguity. The two title surfaces in
`05-fangzheng-039` and the `王丞相` surface in `04-wenxue-021` are not
resolved by punctuation. No new Person is created.

The dependency artifact explicitly prevents “punctuation-only” acceptance.
The nine reviewed X1.2A extension facts and three entities are protected and
unchanged.

## Future candidate readiness

The frozen X1.1 candidate pool is not rewritten because doing so would change
its selection hash. Instead,
`data/derived/x1-2p-candidate-punctuation-readiness.json` provides a bound
derived overlay for all 417 out-of-scope candidates. It distinguishes:

```text
candidate_reviewable
production_punctuation_ready
punctuation_review_required
punctuation_disputed
punctuation_review_cost
```

The current out-of-scope pool contains 116 review-required candidates and
301 disputed/variant candidates. This metadata is planning information, not
historical importance and not a reason to remove random or counter-model
sampling.

## Rematerialization

No X1.2A-R release is performed. The result is:

```text
Stories released: 0
Facts released:   0
Persons released: 0
Stories still unresolved: 20
```

Even if a future punctuation review passes, participant semantics and the
normal Story publication gates must still be evaluated. No canonical source
characters, punctuation records, PersonStory links, participant freeze
records, H0C facts, HG0 graph artifacts, or ML0 artifacts are changed here.

## Implication for X1.2B

X1.2B may proceed only with the punctuation-readiness overlay and an explicit
production gate. Candidate-reviewable is not production-ready. Stories with
exact transfer should remain substantive review work until the source is
editorially qualified or independently corroborated; character-variant
Stories should remain unresolved unless a future review can separate
punctuation from textual emendation.

X1.2P stops here. X1.2B, HG1.1, ML1.1, new GNN training, embeddings,
ontology expansion, political-faction inference, importance ranking, and
ER2 are not implemented.

The governing rule is:

> If the model wants a Story but the text is not ready, the text wins.
