# SRM0.1R — Evidence Consumption & Memory Revision Retest

SRM0.1R retests only the second model stage for `27-jiajue-008`. It reads the
successful SRM0.1 Q1 and the exact eight model-facing candidates from
`data/generated/srm0/27-jiajue-008/round-01-search-trace.json`. It does not
rerun Completion 1, local retrieval, candidate ranking, or any next question.

The model receives only:

```text
Story text
Q1 and its reading target
eight {ref, work, source_layer, snippet} candidates
```

Paths, hashes, scores, source locators, audit metadata, Person research
surfaces, and the previous database-style memory state are excluded from the
model payload. One JSON-mode DeepSeek V4 Flash completion returns a semantic
result: useful evidence, Q1 resolution, reading links, optional static
relation/appraisal candidates, an optional constrained subquestion,
deprioritized associations, and a stop recommendation.

Python turns this result into an isolated retest memory state and append-style
event log. Unselected frozen candidates become `seen_not_selected`; this does
not imply that the model rejected them. Static relation and appraisal rows are
candidate records only. Dynamic states such as trust, dominance, fear,
deference, or intimacy are not relations. A later `噉薤留白`/`為政之實`
association cannot automatically explain the earlier `陶不覺釋然`; it may be
deprioritized because of temporal direction.

Run the retest with exactly one real completion:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_srm0_1r.py --story 27-jiajue-008
python3 scripts/validate_srm0_1r.py
```

The original SRM0.1 artifacts are preserved. Inspect or review:

```text
data/generated/srm0/27-jiajue-008/retest/
data/annotation/srm0-1r-review.json
```

The candidate subquestion, when present, is recorded only; SRM0.1R never
executes it and never writes canonical or Gold data.
