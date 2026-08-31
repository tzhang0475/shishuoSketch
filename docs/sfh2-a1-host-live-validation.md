# SFH2.2-A1 — Host Live Validation and Challenge Adjudication

SFH2.2-A1 executed the frozen SFH2.2/A0R-L architecture on the required host
network. It did not change prompts, schemas, selection files, review routing,
historical data, or production graph state.

## Frozen execution

The required baseline was `7f9e9431314f54848883390bc990fec1018f2aaa` on
`main`. The challenge selection remained the five frozen Stories
`09-pinzao-063`, `25-paidiao-015`, `21-qiaoyi-011`, `10-guizhen-011`, and
`02-yanyu-060`, with four occurrence IDs per Story and selection hash
`f3f4a93de3db1f333c3a750555f36f329464707bf8a1fbbcc5a00f7377505e9a`.

The earlier sandbox failure is preserved in
`data/generated/sfh2-a0r-l/provider-preflight.json`. The host run made one
fresh `deepseek-v4-flash` probe at temperature 0 with thinking disabled and
received a successful response using 9 tokens. The result is recorded in
`data/generated/sfh2-a0r-l/host-live/provider-preflight.json`.

## Live results

All 40 Primary Historian calls parsed successfully: 20 regression cases and
20 challenge mentions. Four regression cases and six challenge cases were
routed to Pass 2. Each routed review request received one retry and then an
HTTP 400; the same ten cases were consequently routed to Pass 3, whose
requests also failed after one retry. No live Pass 2 or Pass 3 semantic result
was accepted. The total authoritative transport budget was 80 attempts.

The regression evaluation therefore records the actual frozen evaluator output,
but it is not evidence of successful review recovery:

| metric | Pass 1 | final projection |
| --- | ---: | ---: |
| historical identity accuracy | 15/18 (83.33%) | 11/18 (61.11%) |
| semantic-kind accuracy | 18/20 | 14/20 |
| canonicalization accuracy | 15/18 | 11/18 |
| occurrence-role accuracy | 4/7 | 4/11 |
| strict full-record accuracy | 7/20 (35%) | 6/20 (30%) |

The final projection includes five `review_required` regression outcomes and
one recorded reviewer-damage case in the frozen evaluator. Selector copy drift
and undeclared patch mutation both remained zero. Because the review provider
calls failed, the result cannot establish that selective review improves the
Primary Historian.

The challenge cohort produced 17 valid Primary Historian records and three
schema-invalid records. Its final state distribution was 5 stable existing
entity resolutions, 6 local candidate resolutions, and 9 review-required
records. Six formal conflicts were recorded and no low-confidence cases were
reported. Historical correctness is intentionally pending external review.

## Highlighted challenge observations

The detailed source packets and records are in
`data/generated/sfh2-a0r-l/challenge-human-review.json` and `.md`.

- `09-pinzao-063 / 文度`: Pass 1 proposed `王坦之`, high confidence, as a
  scene reference and created a candidate-only registry-miss entity. No old
  retrieval candidate was made mandatory by the A0R-L packet. It was not
  routed to review, so this is a Primary Historian observation, not external
  adjudication.
- `25-paidiao-015 / 卿`: the provider response failed schema validation
  (`invalid_occurrence_role`); no semantic referent, speaker, or addressee was
  accepted and the final state is `review_required`.
- `21-qiaoyi-011 / 明府`: likewise had no accepted Pass 1 semantic record
  because of `invalid_occurrence_role`; no Python replacement identity was
  supplied.
- `10-guizhen-011 / 帝` occurrence A: Pass 1 independently proposed `元帝`
  with a review flag; the occurrence remained separate from occurrence B.
- `10-guizhen-011 / 帝` occurrence B: Pass 1 independently proposed `元帝`
  without a formal flag; the identical surface was not merged by Python.
- `02-yanyu-060 / 某`: Pass 1 proposed `簡文帝` and recorded a formal
  multi-target relation ambiguity; no final identity was materialized after
  the failed review/adjudication transport.
- `02-yanyu-060 / 上`: Pass 1 proposed `簡文帝` with `宣武` as speaker and
  `簡文` as antecedent/addressee context; it remained a candidate-only local
  resolution.

## Safety and artifacts

The A1 audit is materialized under `data/generated/sfh2-a1/`. The external
challenge adjudication file is
`data/annotation/sfh2-a1-challenge-external-review.json`; all 20 cases are
explicitly `pending_external_review` and contain no fabricated gold.

The run recorded zero production Person creations, canonical writes,
alias/profile mutations, substring-derived candidates, unsafe role promotions,
selector copy drift, and undeclared patch mutations. Every output remains
`candidate_only=true` with `canonical_write_back=false`. The original failed
preflight hash is preserved as a witness, and no full 188-Story run, Wave C,
or production migration was performed.

The dedicated A1, A0R-L, A0, P2, P1, SFH2, and SFH1 validators passed. The
pre-existing A0R validator still reports `architecture_freeze_drift`: its
stored A0R freeze records an older hash for
`scripts/sfh2_a0r/consistency.py`, while the committed source has the current
hash. No A1 code or artifact changed that source, and the protected A0R freeze
was not rewritten merely to suppress the upstream discrepancy.

## Recommendation

The host successfully confirmed network access and completed the Primary
Historian pass, but the review stages failed at the provider and the frozen
regression identity result is below the required threshold. A1 therefore
returns `sfh2_external_review_required`. The challenge bundle should be
externally adjudicated, and the HTTP 400 review-transport contract should be
diagnosed before treating the architecture as ready for full SFH2.2.
