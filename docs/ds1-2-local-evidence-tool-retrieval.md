# DS1.2 — Local Evidence Tool Retrieval

DS1.2 is a bounded retrieval-path experiment for the existing DS1 Story
`27-jiajue-008`. It is separate from the DS1-v0 fixed-context candidate and
does not write to canonical history, Gold, the frontend, or the DS1-v0 review.

The model initially receives only:

- the original Story text and chapter;
- reviewed resolved participant identities;
- the existing broad temporal orientation.

It can use exactly two normal DeepSeek tools:

```text
search_local_evidence(query, entity_hints, source_layers, top_k)
open_local_evidence(evidence_ref)
```

The first tool searches only the registered WP1 evidence index and the
registered S1 Jianshu assertion index. The second tool can open only a
reference returned by the first tool. No model output, review file, frontend
prose, arbitrary path, shell, web result, embedding index, or external source
is searchable.

The loop is capped at six tool-call rounds, five hits per search, and a fixed
total evidence-text budget. Retrieval scores are deterministic ranking signals,
not historical evidence. Final claims must cite references actually returned by
the tool loop; unsupported claims are rejected by the validator.

## Run

From the repository root:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_ds1_2.py \
  --story 27-jiajue-008 \
  --max-tool-rounds 6
```

The optional `--thinking enabled` flag sends the configurable DeepSeek
thinking parameter. The default is non-thinking mode.

Inspect the generated candidate and complete retrieval trace at:

```text
data/generated/ds1-2/27-jiajue-008.json
data/generated/ds1-2/27-jiajue-008-trace.json
```

The candidate is marked `candidate` and `canonical_write_back: false`. The
trace records each model query, returned evidence references and scores,
opened references, source locators, and token usage. The manifest records
repository-relative paths and protected input hashes.

Validate the boundary with:

```bash
python3 scripts/validate_ds1_2.py
```

## Compare with DS1-v0

DS1-v0 sends the reviewed fixed context bundle and writes its candidate at:

```text
data/generated/ds1/27-jiajue-008.json
data/generated/ds1/27-jiajue-008-context.json
```

DS1.2 starts from the minimal input and lets DeepSeek choose searches. Compare
the two candidates for the same final fields, then inspect the DS1.2 trace for:

1. what the model chose to search;
2. which local source layers and evidence references were returned;
3. which references it opened;
4. which final claims cite which retrieved references;
5. whether it independently found the political and relationship context of
   庾亮 and 陶侃.

The DS1.2 candidate is an experimental review input only. A successful API run
does not automatically create a review decision or canonical fact.
