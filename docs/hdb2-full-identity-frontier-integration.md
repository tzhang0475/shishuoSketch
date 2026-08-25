# HDB2-F — Full Identity Frontier Integration

HDB2-F is the candidate-only integration of the frozen HNG2/HDB1/HDB2
identity pipeline. It treats each HDB1 identity observation as an occurrence,
not as a global surface cluster.

The processing order is:

```text
HDB1 occurrence
→ Python occurrence type and candidate generation
→ Python explicit resolution
→ Python structural interpretation
→ one contextual P1.1/P2T LLM call only when ambiguity remains
→ optional one-round P1 EvidenceAtom rescue for high-value residuals
→ Python hard validation
→ occurrence decision
→ cross-occurrence candidate aggregation
→ relation/fact endpoint projection
```

The 425-observation ledger keeps HDB1 direct resolutions and prior P1.1/P2T
decisions as explicit overlays. HDB2-F live work is frozen separately in
`data/annotation/hdb2-f-frontier-selection.json`; in the current inputs it is
the remaining 162 observations after 198 HDB1 direct resolutions and 65 prior
decisions.

All model keys are local (`c0`, `c1`, …). Existing Person IDs are never sent
as answer labels, new candidates never receive `person-NNN`, and no canonical
Person, Relation, H0A, or H0B file is written.

Relation endpoints are reported independently as existing, candidate,
unresolved, structural, conflict, or rejected self-relation. The endpoint
bottleneck audit records one primary reason for every incomplete candidate
fact. Person knowledge is an evidence-preserving candidate projection, not
biography prose.

The immutable raw API run is under `data/generated/hdb2-f/live/<run_id>/`.
`scripts/validate_hdb2_full.py` rechecks protected hashes, prompt leakage,
structural-reference safety, endpoint safety, and byte-identical offline
projection rebuilds.

