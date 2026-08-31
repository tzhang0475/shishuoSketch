# SFH2.2-A2 — Independent Semantic Audit & Disagreement Adjudication

SFH2.2-A2 is an isolated model-quality pilot. It tests whether a second,
independent historical-semantic reading can expose errors that are internally
consistent and therefore invisible to Python's formal consistency checks.

## Frozen architecture

Historian A is the immutable Primary Historian output from the A1 host run.
No A provider calls are made in A2. Historian B uses the same semantic
ontology and model configuration, but receives only the target and its source
packet: Story text, registered Liu/historical evidence, and validated local
mentions. B does not receive A's output, Python's flags, old retrieval
candidates, or evaluation gold.

The two records are compared structurally. Explanation prose, confidence-only
changes, and evidence ordering are metadata; changes to identity, semantic
kind, reference type, role, discourse, relations, or abstention are
substantive disagreements. Python reports those differences and routes them
to the adjudicator. It never supplies a historical replacement answer.

The adjudicator may select A or B exactly, apply a narrow typed patch, or
abstain. Selecting a record deep-copies that exact prior record. A patch is
accepted only when every changed field is declared and the resulting record
passes schema/evidence/storage validation.

## Why independent review

The preceding A1/A1R reviewer was anchored to the Primary record. A2 instead
measures independent replication: agreement is evidence about model
consistency, not historical verification; disagreement is a review signal,
not a Python answer. The regression cohort is evaluated only after all model
outputs are frozen. The challenge cohort remains pending external historical
review.

## Cohorts and safety

The frozen A0 regression cohort contains 20 cases and the frozen A0R-L
challenge cohort contains 20 occurrences from five Stories. The A1 cache is
the only A input. A2 does not run the 188-Story corpus live, add production
Persons, write canonical facts, mutate aliases/profiles, or perform graph
promotion. All realized entities are candidate-only and
`canonical_write_back=false`.

## Measurements

The regression report separates historical identity from representation
fields. It records A and B identity accuracy, final adjudicated accuracy,
semantic-kind/role/canonicalization dimensions, A-error disagreement recall,
common-mode errors, adjudicator damage, and exact-copy/patch invariants.
Policy P0/P1/P2/P3 are retrospective abstract routing simulations; they do
not change production routing and do not use Chinese surface rules.

## Limitations

Same-model independent readings can share a common error. A/B agreement is
not proof, and challenge historical correctness is deliberately
`pending_external_review`. The pilot therefore informs whether independent
same-model auditing is sufficient; it does not establish historical
completeness or authorize full consolidation.

Historical semantic authority remains:

```text
reviewed human semantics > LLM semantics > soft consistency > retrieval hints
```

## Authoritative live run

Run `sfh2-a2-live-v1` reused 40 cached Historian A records and made no A
provider calls.  Historian B was invoked for all 40 frozen cases.  Thirty-six
responses produced valid structured records; four provider tool-argument
responses were malformed and are retained as contract-invalid raw witnesses,
not interpreted as semantic failures.

Thirty-five A/B disagreements required adjudication.  Thirty adjudicator raw
responses were valid JSON but used a non-empty `base_record` while selecting A
or B, violating the frozen conditional selector contract; five further
adjudications reached the hard 70-provider-attempt cap.  Consequently no
adjudicator result was accepted and the final results for those cases remain
review-required.  This is recorded as a semantic-contract/transport outcome,
not reviewer damage.  The run therefore recommends
`sfh2_semantic_contract_revision_required` and is not evidence that the dual
architecture is ready to scale.

The regression cohort measured Historian A at 15/18 historical-identity cases
(83.33%) and Historian B at 13/18 (72.22%).  A's three identity errors all
produced an A/B substantive disagreement (`a_error_disagreement_recall=1.0`);
no common-mode errors were observed.  Because the review contract was not
accepted, the final materialized identity count is 2/18 and the number of
reviewer-damage cases is zero: unresolved contract failures are not counted
as semantic damage or newly introduced identity errors.

The live transport accounted for 70 durable provider attempts and 274,538
tokens (244,097 prompt and 30,441 completion), with no retries or
request-level provider failures.  The totals are derived from the durable raw
provider witnesses because the interrupted first process did not flush all of
its per-request usage rows; 66 raw responses had parseable tool arguments and
four were malformed.  A resumed process recovered the durable raw witnesses
without duplicating provider attempts.  Two offline replays completed with no
new provider calls and byte-identical deterministic outputs.  The complete
raw witnesses are under
`data/generated/sfh2-a2/live/sfh2-a2-live-v1/raw-api/`; the challenge review
bundle remains `pending_external_review`.

The isolated A2 implementation does not add production identities, mutate
aliases/profiles, write canonical facts, or run the 188-Story corpus.  The
failure indicates that the adjudicator's conditional selector instruction
needs a future contract/prompt revision before another live semantic round;
this closeout does not silently reinterpret the invalid provider payloads.
