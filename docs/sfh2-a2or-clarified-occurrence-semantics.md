# SFH2.2-A2OR — Clarified Occurrence Semantics Rerun

## Scope

A2OR is a controlled live rerun of the immutable 26-case A2O occurrence
cohort. It promotes one human-reviewed A2OT Gold boundary decision and changes
only the occurrence-function historian prompt. The model, endpoint, sampling
configuration, identity input, evidence packets, provenance derivation, and
generic legacy-role projection remain fixed.

The historical A2O and A2OT artifacts are retained as immutable experiment
evidence. No 188-Story run is part of this stage.

## Reviewed Gold promotion

The single promoted case is `02-yanyu-060`, first `宣武` at zero-based
half-open offsets `8:10`. Human review changes its narrative function from
`addressee` to `participant`, and its compatibility role from
`addressee_reference` to `scene_participant`: the occurrence is the object of
the summoning event, not itself a direct-address/vocative occurrence.

The active Gold hash and provenance are recorded in
`data/annotation/sfh2-a2or-human-semantic-authority.json`. No other Gold
record is changed, and canonical write-back remains false.

## Paired experiment

The v2 prompt defines the target-occurrence taxonomy explicitly. It states
that provenance is structural metadata and identity is frozen, and clarifies
the boundaries between participant, direct addressee, citation source,
historical exemplum, and person attribute. It contains no evaluation Gold.

Python only validates the compact output and projects
`(provenance_layer, narrative_function)` to the legacy role. It does not infer
historical identity or apply surface-specific semantic rules.

## Live result

The run used one schema probe plus 26 case calls. All 26 records parsed
successfully with no provider failures or retries. The provenance and identity
preservation checks are structural 26/26 results.

Against the promoted Gold, A2O's frozen output is 22/26 (the original A2O
score remains 21/26 against its predecessor Gold), while A2OR is 22/26. The
clarified prompt fixed two cases but regressed two previously correct reference
cases, so the net improvement is zero. The six reviewed role cases are 5/6;
the historical-exemplum boundary remains wrong. The recommendation is
`sfh2_occurrence_model_quality_insufficient`, not a Python semantic repair.

The known-error audit recovered the annotation `帝` and `顗` cases, but did not
recover `齊桓公` or `顧`. The prompt eliminated annotation-to-main-text role
collapse in this cohort, but did not meet the 24/26 qualification gate.

## Safety and replay

Results are candidate-only, canonical write-back is false, and no production
Person, alias, profile, or canonical mutation is performed. Provider raw
responses are kept outside the repository; committed transport data contains
only bounded accounting and response witnesses. Two offline replays are
derived from the cached A2OR result and must be byte-identical.

The next decision should be based on the A2OR error taxonomy. Do not begin the
full 188-Story resolution from this stage.
