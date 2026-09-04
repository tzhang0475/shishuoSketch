# SFH2.2-F1R — Production Acceptance Review

This is an offline acceptance review of the frozen SFH2.2-F1 wave at
`2da3e2d7f8470f6d0ca0abf3076b29380c4c54bb`. It made zero provider calls and
did not rewrite F1, F-prep, semantic-v1, Gold, canonical data, or frontend
state. The complete machine-readable review is in
`data/generated/sfh2-f1r/`.

## Result

All 30 exact occurrences were reviewed exactly once. The F1 target keys remain
structurally valid: occurrence/mention ID, Story, source-evidence ID, offsets,
and surface all agree, and every source slice matches its surface. The F1
selection hash remains `100fe51cce719c84bb7d538373cabecc5641a60419e03e21a7f73b1a1040dffe`.

The review classified 22 records as plausible from the stored evidence, three
as semantic-correction candidates, one as an identity-applicability/projection
candidate, one as insufficient evidence because its mention is inside a
source title, and three as transport-blocked. In addition, the identity
applicability audit found two office-title routes that entered the person
identity path even though the stored qualified context resolved them as
office/non-person semantics. Those route discrepancies are human-review
candidates; they do not retroactively alter F1. These are offline acceptance
classes, not production Gold labels or accuracy claims.

The five response-level invalid semantic payloads are accounted for:

- four provider structured-output/invalid-JSON responses: two identity
  primary/independent responses for `34-pilou-006`, and identity-primary
  responses for `05-fangzheng-058` and `06-yaliang-033`;
- one truncated boundary response for `08-shangyu-020`.

Parsed contract diagnostics are reported separately from those five response
failures. Three identity units are terminally blocked because adjudication had
no valid identity hypothesis: `34-pilou-006/殷公`,
`05-fangzheng-058/王文度`, and `01-dexing-028/兒`. Other intermediate identity
contract failures were recovered by a valid downstream identity path.

There were 12 occurrence-level new historical-Person proposals and 11
structured entity review groups. The duplicate group is derived from the
candidate ID and structured evidence, not naive string equality.

## Semantic findings requiring human decisions

- `05-fangzheng-055/子野`: the selected span is the first `子野` nested in
  `桓子野`; the stored primary explanation reasons about the later
  `子野荅曰`. Candidate correction: `addressee`.
- `25-paidiao-028/堯`: the occurrence is temporal/background content inside
  the biography of 巢父. Candidate correction: `reference`, not inherited
  `historical_exemplum`.
- `08-shangyu-020/剌史`: in `年十八剌史周俊命爲主簿`, the office-held reading
  is a candidate `person_attribute` interpretation. Its stored identity
  context is office/non-person, although F-prep routed it through person
  identity. The boundary payload was invalid, so it is not used as authority.
- `01-dexing-023/湘州刺史`: the stored identity context likewise resolves an
  office held by 胡母輔之, while F-prep routed the target through person
  identity. The current `person_attribute` output is plausible, but the
  applicability/routing choice needs human confirmation before F2.
- `14-rongzhi-005/康`: the pinned span is the `康` in the source title
  `康别傳`, while both stored explanations discuss a later person occurrence.
  The mention annotation must be reviewed before a semantic promotion.
- `05-fangzheng-027/江南`: the non-person geographic reference is plausible,
  but the compatibility projection currently emits a person-specific
  `annotation_person` role. This is an applicability/projection candidate.

The applicability audit classifies 23 occurrences as requiring person
identity, six as identity-not-applicable, and one as ambiguous. The two
office-title routing discrepancies are `剌史` and `湘州刺史`; `大將軍` is
different because its stored semantic kind is historical-person and the title
is used to identify 王敦 in the event. This is an occurrence-level audit of
the existing F1 route, not a new lexical rule.

The three reason-target drift records are `子野`, `祥`, and `康`. A correct
final label does not erase explanation drift. The `祥` final interpretation is
plausible because the boundary explanation correctly returns to the pinned
opening occurrence, but the primary explanation still cites the later action.

The 14 A2OVB routes contain two plausible overrides (`孔巖` and `爰`) and one
invalid transport result (`剌史`). No accuracy claim is made without reviewed
F1 labels; the qualified boundary architecture remains frozen pending the
failed-route recovery and human review.

## Review-policy counterfactual

The frozen F1 policy produced 25 mandatory occurrence reviews. An inactive
counterfactual policy produces 22 mandatory occurrences and 21 deduplicated
review units on this pilot. It moves resolved, disagreement-only identity
paths to audit-only while retaining degraded provider paths, unresolved
identity, new entity proposals, target drift, office applicability candidates,
unsupported projections, and other explicit semantic risks. The proposal is
not activated in F1R.

At the 3,303-occurrence F-prep scope, the observed-rate estimates are 2,752.5
current mandatory occurrence reviews versus 2,422.2 under the counterfactual;
these are workload observations, not guarantees about the unseen corpus.

## Decision

The operational F1 findings remain intact: resume/checkpoint behavior passed,
duplicate writes were zero, canonical writes and canonical Person creation were
zero, and protected hashes were unchanged. However, the semantic decision set
and the target/projection findings require explicit human resolution before
F2. Transport causes are understood from retained compact metadata; no replay
was performed or needed to explain them. Recommendation:

`sfh2_f1r_human_decisions_ready` → `SFH2.2-F1RP`.

F1R does not activate review-policy v2, modify semantic-v1, expand Gold, or
start F2.
