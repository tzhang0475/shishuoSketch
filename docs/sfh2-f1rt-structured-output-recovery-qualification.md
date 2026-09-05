# SFH2.2-F1RT — Structured Output Recovery Qualification

This bounded experiment tests transport recovery for the immutable F1
failure inventory. It does not change semantic-v1, F1RP human authority,
Gold, canonical data, or any historical experiment output. The authorized
live run used `deepseek-v4-flash` at temperature `0` with thinking disabled;
raw provider witnesses remain in the external archive and are not committed.

## Result

The prospective recovery policy is **promising but incomplete**. All three
terminal identity occurrences became valid, reviewable candidate results, but
the semantic-body-v2 contract still had two invalid body responses among the
14 invalid identity-stage units. The next bounded stage is
`SFH2.2-F1RTR`; F2 is not started.

Recommendation:

```json
{
  "recommendation": "sfh2_transport_recovery_promising_but_incomplete",
  "next_stage": "SFH2.2-F1RTR"
}
```

## Failure inventory

The F1R compact evidence yields 15 invalid stage units, not five:

| measure | count |
| --- | ---: |
| historical response-level invalid payloads | 5 |
| parsed contract diagnostics | 10 |
| identity-stage units | 14 |
| boundary-stage units | 1 |
| distinct terminal identity occurrences | 3 |
| terminal identity stage units | 6 |

The normalized failure classes are:

| class | units |
| --- | ---: |
| `invalid_json` | 4 |
| `truncated_output` | 1 |
| `record_shape_invalid` | 6 |
| `immutable_id_mismatch` | 4 |

The boundary failure for `剌史` is classified as `truncated_output` even though
the provider also reported invalid JSON. The length termination is the more
specific transport diagnosis. Eight units are classified as recovered
intermediate failures, six as terminal identity stage units representing
three cases, and one as a terminal boundary failure.

## Arm A — exact same-contract replay

Arm A replayed all 15 invalid stage units exactly once with the original
semantic packet, prompt, model, and full-record contract. It produced 8 valid
contract recoveries (`8/15`, `53.33%`). Recovery by class:

| class | valid / units | rate |
| --- | ---: | ---: |
| `invalid_json` | 4 / 4 | 100% |
| `truncated_output` | 1 / 1 | 100% |
| `record_shape_invalid` | 2 / 6 | 33.33% |
| `immutable_id_mismatch` | 1 / 4 | 25% |

A valid replay is transport evidence only; it does not promote semantic truth
or bypass human review.

## Arm B — semantic-body transport v2

Arm B removed immutable routing/envelope fields from provider responsibility.
The provider returned only the existing qualified semantic body. Python
attached the exact execution envelope only after body validation. The body
schema contains no provider-owned `mention_id`, `case_id`, occurrence ID, or
source-offset fields.

Results:

- invalid identity units tested: `14`;
- valid semantic bodies: `12/14` (`85.71%`);
- invalid body responses: `殷公` independent and `王蒙` independent, both
  `record_not_object`;
- deterministic six-occurrence control cohort: `12/12` valid bodies.

The control comparison is against the matching historical primary or
independent result, not against a selected result from another stage. It
ignores free-text explanations and treats target-surface/discourse rendering
differences as compatible when the semantic identity core is unchanged:

| comparison | count |
| --- | ---: |
| exact semantic match | 3 |
| compatible semantic match | 8 |
| core semantic disagreement | 1 |

The one core disagreement is an isolated `referent_canonical_hint` difference
for the primary `卿` control. No core difference family repeats in the control
cohort, so this is an audit item rather than systematic semantic drift. It is
not silently resolved by Python.

## Terminal recovery

Arm-B primary/independent semantic bodies were passed through the existing
qualified A2R comparison/adjudication logic. All three historical terminal
identity blocks became `resolved_candidate`:

| occurrence | result |
| --- | --- |
| 殷公 | resolved candidate; adjudicator selected the valid primary hypothesis |
| 王文度 | resolved candidate; adjudicator selected the valid independent hypothesis |
| 兒 | resolved candidate; adjudicator selected the valid independent hypothesis |

These are candidate-only results. No canonical Person was created or written.

The `剌史` boundary failure was replayed once under the original boundary
contract and returned a valid structured result. It is transport evidence only;
the F1RP human decision (`identity_not_applicable`, `person_attribute`) remains
the semantic authority.

## Accounting and safety

The authorized live run made 47 provider calls:

- 3 contract probes;
- 15 Arm-A exact replays;
- 26 Arm-B semantic-body/control calls;
- 3 terminal adjudicator calls.

There were 47 provider attempts, zero network retries, zero provider failures,
168,993 prompt tokens, 21,094 completion tokens, and 190,087 total tokens.
Median latency was 3.067 seconds and maximum latency was 3.914 seconds.

The offline replay was run twice with zero provider calls and produced
byte-identical stable artifacts. Protected snapshot mutation count was zero.
Canonical writes, canonical Person creation, semantic coercion, regex/prose
extraction, and human-authority violations were all zero. F1RP authority and
`康`'s upstream-target block remain unchanged.

The recorded policy remains bounded:

```text
valid normal call -> use candidate result
invalid semantic body -> one recovery replay
invalid again -> explicit terminal review block
```

Network retry accounting remains separate, and malformed output is never
repaired or coerced into a semantic answer. The next stage must address the
two remaining semantic-body contract failures before a larger production
wave.
