# HDB1-W2 — Remaining-Scope Production Validation

HDB1-W2 is a second candidate-production wave on the frozen HNG2-C.3/V1
algorithm. It computes the current 143-Story production boundary minus the
54 prior-HNG2 Story IDs and the 48 frozen HDB1-W1 Story IDs. The prior set
contains 32 IDs outside the current production boundary, so the actual
remaining in-scope set is 73 Stories rather than the approximate 41 implied by
counting the historical exclusion snapshot without intersecting it with the
current production set.

W2 is independent of W1 during live extraction. The semantic prompts receive
only the canonical/reviewed resolver inputs and the selected evidence windows;
W1 provisional Persons, candidate relations, and candidate temporal outputs are
not loaded into the W2 runner.

## Frozen execution

```text
Person:   SELECT → READ EvidenceAtoms → GROUND → FILL → RESOLVE/NORMALIZE
Temporal: SELECT → visible anchor scan → READ TemporalAtoms → GROUND → FILL → H0A normalize
```

The model remains `deepseek-v4-flash`, with the HNG2-V1 prompt/tool versions.
There is no SearchPlan, ResearchGap loop, follow-up retrieval, recursive
expansion, GraphRAG, embedding search, web retrieval, or canonical write.

## Offline aggregation

After W2 completes, `build_hdb1_cross_wave_database.py` combines W1 and W2
observations. Same normalized surfaces are retained as surface buckets only;
they are never identity merges. Compatible clusters require an existing
Person resolution or source-grounded identity evidence. Unresolved relation
endpoints may be reactivated only through independent identity support, never
through surface similarity alone.

Facts retain all source observations. Duplicate candidate facts are collapsed
only when their safely resolved endpoints and evidence meaning agree. Temporal
assertions remain Story-owned; aggregation reports reusable H0A-compatible
statistics without transferring a date from one Story to another.

P0/P1/P2 items form the active review queue. P3 items remain a searchable
backlog unless cross-wave aggregation shows repeated or structurally blocking
value.

## Commands

```bash
python3 scripts/run_hdb1_wave2.py --prepare
python3 scripts/run_hdb1_wave2.py --live --run-id <run-id>
python3 scripts/build_hdb1_cross_wave_database.py --w2-run-id <run-id>
python3 scripts/validate_hdb1_wave2.py --run-id <run-id>
python3 scripts/validate_hdb1_wave2.py --aggregate --w2-run-id <run-id>
python3 scripts/build_hdb1_cross_wave_database.py --check-determinism --w2-run-id <run-id> --no-write
```

All output remains candidate-only. No production Person, Relation, H0A, H0B,
Gold, NL, SRM, or frontend data is modified.
