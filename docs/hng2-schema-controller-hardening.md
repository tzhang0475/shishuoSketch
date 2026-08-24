# HNG2-SC.1 — Controller Hardening

HNG2-SC.1 hardens the Structured Evidence Card controller without changing
Historical Entity Schema v1 or any historical projection.

## Boundaries

`scripts/run_hng2_schema_controller_hardening.py` defaults to offline replay.
It reads the immutable HNG2-SC-07 response envelopes and a small set of frozen
HNG2-SL envelope samples, then writes only to:

`data/generated/hng2-schema-controller-hardening/`

The optional live mode is limited to five already-open ResearchGap cases,
allows at most two semantic calls and one local retrieval round per case, and
does not expand a frontier. It must be launched with approved network access.

## Controller rules

- `target_entity_key` is required for new live cards and controls identity
  projection. A contextual structural-kinship entity cannot reclassify a
  different named target.
- Prior Python constraints are copied first and merged with card-derived
  constraints. Existing rows, including temporal constraints, remain visible
  and retain their provenance.
- Binary identity assertions can propagate an existing catalogue person to a
  title, alias, courtesy, or equivalent entity. Existing catalogue matching is
  attempted before a local `person_id: null` candidate is created.
- `finish_reason: length` is `response_truncated`; it is not a card semantic
  validation failure and is never semantically repaired.
- Provider failures, parse failures, card failures, and valid cards remain
  separate classifications.
- SearchPlan packets carry an explicit `allowed_sources` list.

## Commands

```bash
python3 scripts/run_hng2_schema_controller_hardening.py --mode replay
python3 scripts/validate_hng2_schema_controller_hardening.py --mode replay
python3 -m unittest tests.test_hng2_schema_controller_hardening
```

Only after replay and validation pass, an operator may run the five-case live
validation with approved network access:

```bash
python3 scripts/run_hng2_schema_controller_hardening.py --mode live --run-id <run-id>
python3 scripts/validate_hng2_schema_controller_hardening.py --mode live
```

No command in this stage writes canonical Persons, Relations, Facts, Gold, SRM,
or prior HNG artifacts.
