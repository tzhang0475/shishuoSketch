# SFH2.2-A1R — Strict Review Transport and Cached Adjudication

SFH2.2-A1R repairs the review-stage transport contract without changing the
historical reasoning architecture.  The Primary Historian remains the source
of historical semantics; Python validates structure, routes review, applies
typed patches, and controls candidate-only storage.

## Root cause

The previous Critical Reviewer and Adjudicator tools exposed a partially
optional `patch` object (`required: []`) alongside `reviewed_fields`.  DeepSeek
strict function calling rejects that shape: every property of every object must
be required and every object must set `additionalProperties: false`.  The
result was HTTP 400 at both review stages, with no inference tokens.  A 400 is
now recorded with a bounded sanitized response body and is never retried.

## Contract repair

Review output now has four required top-level fields and carries a typed
`patch_ops` array.  Each operation is a closed two-property object (`path`,
`value`) selected from type-specific strict-schema branches.  Python derives
`reviewed_fields` from operation paths for audit compatibility; it is not sent
to the provider.  Confirm/selection/abstention requires an empty operation
array.  Revision requires a non-empty operation array and a valid base record.

The selector reuses an exact deep copy of Pass 1 or the effective Pass 2
record.  A revision is applied only to declared paths and is revalidated
against the semantic record schema.  No provider is asked to regenerate a
selected record, so selection copy drift cannot occur.

The occurrence-role ontology also accepts the generic dialogue roles
`speaker_reference` and `addressee_reference`.  This is an ontology contract
correction, not a rule for any particular Chinese surface.

## Cached-primary run

All 40 A1 Primary responses were reused from the immutable A1R-L host run; no
new Primary calls were made.  The previous local contract-valid count was
36/40.  After the generic dialogue-role correction, 39/40 validate.  The
three recovered records are `吾`, `卿`, and `明府`, whose provider records use
the generic dialogue-role values.

One pre-existing cached record remains auditable but invalid: `阮光禄` has
`scene_participant` in a `relations` row, although that value belongs to the
occurrence-role vocabulary rather than the relation vocabulary.  The raw
response is preserved unchanged and no Python coercion is applied.  This is a
residual cached contract mismatch, not a new historical identity judgment.

## Strict probes and review

One no-retry probe for each tool passed: Primary, Critical Reviewer, and
Adjudicator each returned HTTP 200 with a tool call.  The repaired live review
run reused 40 cached Primaries, made 13 new Critical Reviewer calls, and made
no Adjudicator calls because no post-review condition required escalation.
All 13 Reviewer responses parsed successfully: 0 HTTP 400s, 0 provider
failures, 0 retries, 47,192 prompt tokens, 3,970 completion tokens, and
51,162 total tokens.  The original cached A1 Primary run remains the only
source of Primary usage (40 calls; 128,055 tokens).

The regression cohort retains 15/18 reviewed historical identities (83.33%).
The effective final identity result is unchanged from Pass 1: no reviewer
damage and no recovered semantic errors.  Two cases remain semantic errors;
one is the residual `阮光禄` contract mismatch.  Strict full-record accuracy is
reported separately at 7/20 (35.00%) and is not conflated with identity
accuracy.  The challenge cohort has 20/20 valid Primary records, 9 cached/live
review-routed cases, and historical correctness remains pending external
review.

## Replay and safety

Two offline replays using the cached review responses produced byte-identical
derived artifacts across 17 files and made zero provider calls.  The run is
candidate-only and has `canonical_write_back: false`.  Production Person
creation, canonical writes, alias/profile mutations, substring identity
creation, and unsafe relation-role promotions are all zero.

The generated audit files under `data/generated/sfh2-a1r/` retain raw paths,
hashes, strict probe results, residual contract mismatch details, review
transport accounting, and the challenge review bundle.  The A1 and A0R-L
artifacts are not overwritten.

## Limitation and recommendation

Transport is repaired and cached review outputs are structurally valid, but
the controlled regression identity result is below the 95% scale-readiness
threshold.  The remaining `阮光禄` record also requires a future generic
relation-contract decision rather than a case-specific repair.  Accordingly
this stage recommends `sfh2_review_contract_fixed_but_model_quality_insufficient`.

No full 188-Story live rerun, Wave C, canonical promotion, or production graph
write-back was performed.
