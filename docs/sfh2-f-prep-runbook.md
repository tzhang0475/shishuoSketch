# SFH2.2-F-prep runbook

F-prep is an offline preflight. Run it from a clean `main` checkout at the
declared baseline (or a descendant that preserves the baseline):

```bash
python3 scripts/run_sfh2_f_prep.py
python3 scripts/validate_sfh2_f_prep.py
```

The first command reads current SFH1/UX2 authority, frozen identity and
qualified pilot witnesses, and writes only the F-prep planning namespace plus
the new `data/frozen/sfh2/semantic-v1/` architecture manifests. It contains
no provider transport and must report `provider calls=0`. The validator is
read-only and also runs the prospective C3 growth check against the F-prep
baseline.

Do not run a builder that writes the full semantic corpus as part of F-prep.
Do not run a provider, create a Person, write canonical data, modify Gold, or
overwrite a frozen pilot result. Raw provider envelopes belong in external
archive storage by default and are not part of the F-prep Git contract.

## Before F1

Review these artifacts together:

* `production-scope.json` and `occurrence-manifest.json` for authority and
  exact target integrity;
* `identity-readiness.json` for reusable contexts and pipeline units;
* `production-dag.json` and `production-schema.json` for candidate-only
  semantics;
* `review-routing-policy.json`, `cache-reuse-plan.json`, and
  `checkpoint-policy.json` for safe resume behavior;
* `call-budget.json` and `token-storage-estimate.json` for an approved bound;
* `f1-selection.json`, `f1-stop-conditions.json`, and `f1-success-gate.json`
  for the bounded first wave.

The exact occurrence key is mandatory everywhere:

```text
occurrence_id / case_id
mention_id
story_id
source_evidence_id
source_start
source_end
surface
```

If a future packet cannot reproduce the exact key or its request hash, it is a
new unit and must not silently reuse an old checkpoint. The boundary validator
is routed from the primary's structured function, but its provider packet
must omit the primary label, confidence, and reason. Non-boundary functions do
not receive a boundary call.

## F1 operational shape

F1 should execute the recorded 30-occurrence selection as a bounded,
resumable wave. Persist one compact checkpoint per stable unit, keep raw
provider witnesses out of Git, and inspect the candidate review queue before
any later promotion. F1 output is candidate-only. A successful F1 is an
operational/semantic audit of the run, not evidence that every unseen
occurrence is correct.

The fixed abort conditions include canonical writes, production Person
creation, protected hash mutation, Gold or residual-label leakage, invalid
exact occurrence identity, provenance failure, identity replacement outside
the qualified identity stage, boundary primary leakage, copy drift, and
undeclared mutation. Contract-invalid or failed units remain visible and
review-blocked; they are never hidden to improve metrics.

After F1, use the recorded success gate and review-routing policy to decide
whether to continue. Do not expand to the full corpus from an unreviewed or
unbounded command.
