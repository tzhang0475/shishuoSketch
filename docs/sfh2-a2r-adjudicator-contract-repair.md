# SFH2.2-A2R — Adjudicator Contract Repair

SFH2.2-A2R is an isolated repair/replay of the SFH2.2-A2 dual-semantic
pilot. The immutable A2 evidence remains under `data/generated/sfh2-a2/`.
A2R reads that evidence and writes only to `data/generated/sfh2-a2r/`.

## What failed in A2

The A2 adjudicator returned a decision together with a redundant
`base_record`. DeepSeek's strict function contract accepted the JSON shape,
but the local semantic contract rejected selections whose redundant base was
non-empty. Thirty otherwise parseable selection responses consequently became
contract-invalid. This was a transport/contract failure, not a historical
semantic judgment.

The four malformed Historian B responses were also retained as immutable A2
witnesses. A2R allowed exactly one identical replacement attempt for each of
those four cases. Valid A and B records were never rerun.

## Repaired contract

The provider now returns the decision-encoded contract:

```json
{
  "decision": "select_a | select_b | revise_a | revise_b | abstain",
  "patch_ops": [],
  "reason_summary": "...",
  "supporting_evidence_ids": []
}
```

Every object is closed and every property is required for DeepSeek strict
mode. `select_a`, `select_b`, and `abstain` require an empty `patch_ops`;
`revise_a` and `revise_b` require a nonempty typed operation list. There is no
`base_record` property in the live A2R schema. Python derives reviewed fields
from the operation paths and performs only schema validation and deterministic
selection/patching.

Selection is exact copying:

```text
select_a  -> deepcopy(Historian A)
select_b  -> deepcopy(Historian B)
revise_a  -> typed patch over Historian A
revise_b  -> typed patch over Historian B
abstain   -> no semantic record
```

No Python code supplies a historical replacement identity. A failed review is
kept as unresolved rather than scored as a semantic false answer.

## Live run

The run used `deepseek-v4-flash`, temperature `0`, thinking disabled, and the
existing strict endpoint. It made one schema smoke call, four permitted B
recovery calls, and 33 adjudicator calls: 38 durable provider attempts in
total. There were no HTTP 400 responses, provider failures, or retries. Two
of the four replacement B payloads remained malformed; their original A2
witnesses remain preserved and are explicitly represented as contract-invalid.

The 36 valid B records and all 40 A records were reused from A2. No valid
Historian A or B call was repeated.

For the 18 regression identity cases, the result was:

| measure | result |
| --- | ---: |
| Historian A | 15/18 (83.33%) |
| Historian B after allowed recovery | 15/18 (83.33%) |
| final adjudicated identity | 17/18 (94.44%) |
| final resolution coverage | 18/18 (100%) |
| A-error recoveries | 1/2 |
| common-mode errors | 0 |
| adjudicator damage | 0 |

The final result is below the requested 95% scale-readiness threshold. This
is therefore reported as adjudicator/model-quality insufficiency, not hidden
by counting unresolved cases as wrong. The adjudicator contract itself was
fully valid: all 33 responses parsed and were materialized as exact A/B
selections.

The selection matrix was:

```text
A correct / B correct       13
A correct / B unresolved     2
A unresolved / B correct     1
A wrong / B correct          1
A wrong / B wrong            1
```

## Cost and routing implications

The durable live accounting was 153,693 prompt tokens and 13,540 completion
tokens, 167,233 total tokens. Median request latency was 3.018 seconds and
maximum latency was 4.338 seconds. The two B recovery payload failures are
transport/contract outcomes, not extra semantic labels.

On this 40-occurrence observation set, an all-semantic-disagreement dual pass
would use an estimated 113 calls (projected 531.1 calls at the same rate for
188 Stories). Restricting adjudication to identity/semantic-kind disagreement
would estimate 96 calls (451.2 projected), while the identity/semantic-kind/
discourse-critical view estimates 109 calls (512.3 projected). These are
rough rate extrapolations, not a full-run performance claim. The detailed
abstract P0/P1/P2/P3 simulation is in `policy-simulation.json`.

## Safety and determinism

Both offline replays used zero provider calls and matched all deterministic
semantic/audit artifacts byte-for-byte. Copy drift and undeclared patch
mutation were zero. Production Person creation, canonical writes,
alias/profile mutation, substring candidate generation, and unsafe relation
promotion were all zero. `candidate_only=true` and
`canonical_write_back=false` remained enforced.

Challenge correctness remains `pending_external_review`; the regenerated
bundle is deliberately not self-graded. The bundle records A, B,
adjudicator, and final outputs for external review.

## Limitation and recommendation

The contract repair solved the A2 failure mode and recovered one of two
remaining A identity errors without introducing adjudicator damage. One
shared semantic error remained, so the pilot does not justify scaling to the
188-Story consolidation yet. The appropriate next experiment is to improve or
change adjudicator semantic quality while retaining the decision-encoded
contract and the Python/LLM authority boundary.

Recommendation: `sfh2_adjudicator_quality_insufficient`.
