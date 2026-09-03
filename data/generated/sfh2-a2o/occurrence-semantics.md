# SFH2.2-A2O — Occurrence Semantics Decomposition Pilot

Identity is frozen from SFH2.2-A2GR. `provenance_layer` is copied from the target evidence metadata; only `narrative_function` is supplied by the occurrence historian. Legacy `occurrence_role` is a compatibility projection.

Pilot cases: 26; reviewed Gold cases: 26; provider calls are recorded separately.

## Boundary

Python does not inspect Chinese surfaces or choose identities. It derives source provenance from `source_evidence_id`, validates the compact provider contract, and applies the generic compatibility projection.

## Results

- Provenance accuracy: `{'correct': 26, 'evaluable': 26, 'accuracy': 1.0}`
- Narrative-function accuracy: `{'correct': 21, 'evaluable': 26, 'accuracy': 0.8077}`
- Projected legacy-role accuracy: `{'correct': 21, 'evaluable': 26, 'accuracy': 0.8077}`
- Identity preservation: `{'correct': 26, 'evaluable': 26, 'accuracy': 1.0}`
- A2R six-case baseline: `{'case_count': 6, 'correct': 3, 'accuracy': 0.5, 'source': 'data/generated/sfh2-a2g/occurrence-role-audit.json'}`
- Recommendation: `sfh2_occurrence_model_quality_insufficient`

## Cohort

The cohort contains the six frozen A2G role cases and all 20 frozen A0R-L challenge mentions. Selection is deterministic, does not use Gold or model results, and retains the repeated occurrences as separate mention records.

## Interpretation

The decomposition preserves the distinction between participation in Liu's annotation narrative and participation in the Shishuo main-text scene. Any remaining function mismatch is a semantic historian limitation, not a Python historical replacement. This pilot does not start the 188-Story run.
