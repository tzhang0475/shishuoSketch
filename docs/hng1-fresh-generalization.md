# HNG1 — Fresh Historical Network Generalization

HNG1 evaluates the frozen HNG0.2R source-driven growth path on 36 Persons
that are outside the original 24 HNG0 seeds. Selection is deterministic and
stratified into 12 high-, 12 medium-, and 12 low-connectivity Persons using
existing Story links, candidate relation degree, reviewed source-evidence
density, and processed Jinshu coverage. The frozen selection is written to
`data/generated/hng1/hng1-selection.json` before live execution.

Each fresh seed is researched once. Retrieval searches registered local
punctuated witnesses first (Shishuo canonical text and the WREF1 Jinshu and
Zizhi Tongjian witnesses), opens a short sentence/paragraph window, and uses
the existing local processed corpora as fallback. Search and evidence traces
retain searched, retrieved, opened, and used references plus the source form.
No Web search, embedding index, or second-hop research is used.

DeepSeek V4 Flash receives only a seed orientation and opened local passages.
It may return explicit relation and temporal candidates, but Python rejects
model-assigned Person IDs and validates every exact evidence quote. The
frozen HNG0.2R resolver handles exact, alias, title, contextual, and generic
decorated-name suffix resolution. Relation normalization keeps hard
relations, documented interactions, and interpreted relations distinct;
co-occurrence alone is never promoted.

All HNG1 output is candidate-only under `data/generated/hng1/`, with a local
review overlay at `data/annotation/hng1-review.json`. Provisional neighbors
are HNG-only nodes and unresolved/ambiguous surfaces remain visible. No
canonical Person, Relation, Fact, Gold, SRM, or frontend data is modified.

## Run boundary

Prepare the frozen offline selection with:

```text
python3 scripts/run_hng1.py --prepare
```

Run the live evaluation only from an approved-network execution:

```text
python3 scripts/run_hng1.py --live
```

The runner performs one authenticated preflight. If the environment cannot
reach DeepSeek, it records an execution-environment failure without creating
model findings; it does not substitute fixtures.
