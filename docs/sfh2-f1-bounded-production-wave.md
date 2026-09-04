# SFH2.2-F1 — Bounded Production Wave

F1 is the first bounded live candidate wave for the frozen `SFH2.2 semantic-v1`
architecture. It executes the pre-frozen 30-occurrence, 25-Story selection
from `data/generated/sfh2-f-prep/f1-selection.json`; it does not expand the
corpus and makes no accuracy claim for unseen production data.

The execution DAG is fixed:

```text
exact occurrence
  -> structural provenance
  -> qualified identity pipeline (when required)
  -> A2OR occurrence historian
  -> A2OVB blind participant/reference validator (when routed)
  -> generic legacy-role projection
  -> candidate semantic record
  -> structural review queue
```

The A2OV primary-aware reviewer is intentionally excluded. The boundary
validator receives no primary hypothesis, confidence, reason, Gold, or prior
error label. All outputs remain `candidate_only=true` and
`canonical_write_back=false`; no Person, alias, profile, or canonical fact is
created by this wave.

## Execution and resume

Run the required five-occurrence smoke phase first:

```bash
python3 scripts/run_sfh2_f1.py --live --phase-a-limit 5
```

Restart the same run over the original selection and continue the remaining
25 occurrences:

```bash
python3 scripts/run_sfh2_f1.py --live --resume
```

Provider envelopes are stored outside the repository under the configured
`SFH2_F1_RAW_DIR`. Git receives only compact accounting, checkpoints,
candidate records, distributions, and review flags. Matching request hashes
are required for checkpoint/cache reuse; a changed request hash fails closed.

The generated `data/generated/sfh2-f1/resume-validation.json` and
`data/generated/sfh2-f1/review-queue.json` are the operational handoff for
F1R. `docs/sfh2-f1-semantic-audit-bundle.md`, when the wave completes, is the
compact human inspection bundle. F1 must be reviewed before any larger wave.

## Recorded bounded wave

The run is pinned to baseline `b30c380095772f61dcf3109b75535a70007c47ab` and
selection hash
`100fe51cce719c84bb7d538373cabecc5641a60419e03e21a7f73b1a1040dffe`:
30 occurrences from 25 Stories. Phase A processed the first five occurrences;
the restart over all 30 reused the completed checkpoints, made zero new calls
for those five, and then processed the remaining 25. The final resume audit
records 114 checkpoint reuses, zero duplicate semantic writes, and zero
provider calls during offline replay.

The live transport accounting records 117 provider attempts, comprising 113
semantic calls and four probe attempts (three successful probes plus one
initial local sandbox socket-denial attempt). There were no transport retries;
five semantic responses were contract-invalid and remain explicit review
items. One occurrence-primary result was reused from the exact A2OR cache.
The semantic call breakdown is: identity primary 25, identity independent 25,
identity adjudication 23, occurrence primary 26, and boundary validation 14.
The occurrence boundary routed 14 cases and produced two primary/boundary
overrides.

All 30 outputs are candidate-only. The wave created zero canonical Persons,
zero aliases/profiles/facts, and zero canonical writes. There are 25 mandatory
review records: 12 new historical-Person proposals, 20 identity-stage
disagreement flags, 12 invalid-provider-contract flags, five provider-failure
flags, and three unresolved identity-stage records (counts overlap by record).
There are four audit-only flags, consisting of the two boundary overrides
recorded on two dimensions each. The final recommendation is
`sfh2_f1_human_semantic_review_required`; F1 makes no accuracy claim about the
unseen corpus and should proceed to F1R before any expansion.
