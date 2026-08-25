# HDB1 — Controlled Historical Candidate Database Production, Wave 1

HDB1 is the first candidate-production wave on the frozen HNG2 contextual
historical extraction algorithm. It processes 48 Stories from the current
143-Story production boundary and writes only reviewable candidate data.

## Frozen execution

Person targets use:

```text
SELECT → READ EvidenceAtoms → Python grounding → FILL
→ Python identity/relation normalization → candidate projection
```

Story temporal targets use:

```text
SELECT → visible H0A anchor scan → READ TemporalAtoms
→ Python grounding → FILL → H0A-compatible normalization
→ candidate projection
```

The runner reuses the HNG2-V1 prompts, strict tools, model, grounding and
normalizers. It has no SearchPlan, ResearchGap loop, follow-up retrieval,
second-hop expansion, GraphRAG, embeddings, web search, or canonical write.

## Data boundary

HDB1 output is a candidate layer:

```text
source → validated evidence → candidate fact → human review → reviewed/canonical layer
```

Existing Person IDs are referenced only when the frozen resolver returns an
existing catalogue Person. New persons use deterministic `hdb1-*` provisional
identifiers; no `person-NNN` ID is allocated. Existing H0A/H0B facts and
relations are compared for novelty but never overwritten.

The production selection is frozen in
`data/annotation/hdb1-wave1-selection.json`. It records the complete prior
HNG2 exclusion snapshot and hashes of protected historical artifacts.

## Candidate normalization

Explicit `kinship`, `marriage`, `institutional`, and `interaction` outputs are
kept in their corresponding candidate families. The historical wording and
exact evidence span are retained. Co-occurrence does not create a relation;
non-identity self-relations are rejected after normalization. Temporal
evidence is separated into scene-time candidate evidence and contextual
evidence such as later outcomes, quoted precedents, and background; only the
former can be an H0A upgrade candidate, and H0A itself is unchanged.

Grounding rejects remain in a separate audit artifact rather than inflating
the human review queue. Review priorities are P0–P3 for conflicts, new
identities/facts, explicit new interactions/office observations, and useful
unresolved observations.

## Commands

```bash
python3 scripts/run_hdb1_wave1.py --prepare
python3 scripts/run_hdb1_wave1.py --live --run-id <run-id>
python3 scripts/build_hdb1_candidate_database.py --run-id <run-id>
python3 scripts/validate_hdb1.py --run-id <run-id>
python3 scripts/build_hdb1_candidate_database.py --run-id <run-id> --check-determinism --no-write
```

The live command performs one authenticated preflight and then exactly two
semantic calls per selected Person target plus two calls per Story. Provider,
transport, and JSON parse failures use only the frozen one-identical-retry
policy; semantic repair and target-specific tuning are not performed.

