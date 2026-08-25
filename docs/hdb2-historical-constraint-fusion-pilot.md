# HDB2-P1 — Historical Constraint Fusion & Identity Resolution Pilot

HDB2-P1 is a candidate-only reasoning layer above the frozen HDB1
observations. It does not change HNG2 extraction, canonical Persons, facts,
H0A, H0B, Gold, NL, or SRM.

The pilot is deliberately Python-led:

```text
HDB1 unresolved identity cluster
  → deterministic IdentityCase
  → Python query generation
  → registered local-source FIND / short OPEN windows
  → DeepSeek EvidenceAtoms
  → exact Python quotation validation
  → typed constraints and candidate-set solver
  → resolved_existing / resolved_new_candidate / narrowed /
    unresolved / conflict
  → candidate-only fact re-projection
```

The model sees only the target surfaces and selected source passages. It does
not receive expected Person IDs, candidate scores, graph actions, or search
instructions. It cannot create IDs or merge candidates. Evidence atoms are
accepted independently, and every accepted textual surface must occur in its
same exact source span.

The local index uses the registered Shishuo main text and Liu annotations,
the local structured Yu Jiaxi Jianshu cache when present, Jinshu, Sanguozhi,
and Zizhi Tongjian processed witnesses. Search is broad and deterministic; at
most four short passages and about 2,000 characters are sent per round. A
second deterministic retrieval/reading round is allowed once
when the first Python decision remains open. It is not a ResearchGap or
SearchPlan controller.

Temporal compatibility, office compatibility, and kinship compatibility are
hard constraints only when the repository contains sufficiently explicit
bounded evidence. Compatibility alone never proves identity; missing facts
are not contradictions. All unblocked relations and knowledge deltas remain
reviewable candidates.

Run the offline selection and tests with:

```bash
python3 scripts/build_hdb2_identity_cases.py
python3 -m unittest tests.test_hdb2_constraint_fusion
```

The live runner requires `DEEPSEEK_API_KEY` and performs the frozen strict
EvidenceAtom call against `deepseek-v4-flash` at the DeepSeek beta endpoint:

```bash
python3 scripts/run_hdb2_identity_pilot.py
python3 scripts/validate_hdb2_pilot.py data/generated/hdb2-p1/live/<run-id>
```

Generated outputs are candidate/research artifacts only. No HDB2-P2 or
canonical materialization is started automatically.
