# HNG2-SL — Schema Hardening & Targeted Live Validation

HNG2-SL hardens Historical Entity Schema V1 and validates only the existing
open `ResearchGap` cases from `data/generated/hng2-schema/`.

The live controller performs at most two semantic-assist rounds and one local
punctuated-first retrieval round per selected case. It does not expand a
frontier, create canonical Persons, or write historical facts. Model output
is stored immutably under `data/generated/hng2-schema-live/raw-api/`; Python
owns hard constraints, final `IdentityDecision`, `GraphAction`, and the
projection of `ResearchGap` transitions.

The frozen selection is written before any semantic API call:

```bash
python3 scripts/run_hng2_schema_live.py --selection-only
```

Live execution must use approved network access:

```bash
python3 scripts/run_hng2_schema_live.py --run-id hng2-sl-<UTC>
python3 scripts/validate_hng2_schema_live.py
```

There were no native metatextual open gaps in the frozen projection. Such
required regressions are therefore reported as offline fixture coverage and
are never counted as live model findings. Selection proxy strata are marked
explicitly in `selection.json`.

Schema hardening includes controlled assessment/fit/confidence enums,
metatextual discourse-role protection, nullable non-candidate constraint
scopes, and separation of `IdentityDecision.new_entity_key` from the
GraphAction provisional node identifier.
