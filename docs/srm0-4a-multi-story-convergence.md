# SRM0.4A — Multi-Story Convergence Pilot

SRM0.4A is a generated, research-only pilot. It tests whether a bounded
reading loop can move from a Story's own reading gaps to attached commentary,
then to a narrow local evidence lookup, while stopping when the Story-reading
gap is closed or evidence has saturated.

## Selection

The builder excludes the prior SRM/DS/IRR pilot Stories. It classifies the
remaining canonical Shishuo entries using deterministic main-text, Liu-block,
and non-duplicate Jianshu character counts. Within each class it orders Story
IDs by SHA-256 and selects three rich-commentary, two medium-commentary, and
one low-context control Story. The selection and its rationale are stored in
`data/generated/srm0/srm0-4a-selection.json`.

## Rounds

Round 0 sends only the canonical main text and freezes at most three exact
reading gaps. A Python gate removes gaps that the Story directly resolves or
that are only name/biography expansion without reading leverage.

Round 1 sends the frozen gaps with all Liu annotations and the non-duplicate
Jianshu notes. The model returns semantic deltas only; Python derives the
reading state and creates child questions only from high-impact unresolved
aspects.

Later rounds search registered local projections only. The registry currently
covers Shishuo, Liu annotation, Jianshu, Jinshu, Sanguozhi, and the two local
Zizhi Tongjian indexes. Search results are compacted before the model sees
them, while `search-trace.jsonl` records retrieved, opened, and actually used
refs. No web or network retrieval is enabled.

## Convergence

Each evidence round records `G_t`, `D_t`, and `N_t`: active reading gaps,
whether a material semantic change occurred, and the fraction of used refs
that are new. A question stops on reading sufficiency, two-round evidence
saturation, stable conflict, two retrieval attempts without adequate evidence,
or the four-round evidence cap. A Story converges only when its active
reading questions have stopped.

## Commands

Use fixture mode for deterministic offline validation:

```bash
python3 scripts/run_srm0_4a.py --batch --fixture
python3 scripts/validate_srm0_4a.py --mode portable
```

With `DEEPSEEK_API_KEY`, the real batch command is:

```bash
python3 scripts/run_srm0_4a.py --batch
```

`--story STORY_ID` limits a run to one of the selected Stories. `--replay-existing`
rebuilds projections from archived raw outputs without another API call.

Fixture artifacts are plumbing tests only and are marked
`execution_kind=fixture`; they must not be read as model findings. Live model
outputs that violate the exact semantic-delta/evidence contract fail closed
and retain their validation errors rather than being repaired into a result.

All model outputs, state, traces, and metrics remain under
`data/generated/srm0/<story_id>/convergence/`. They are not source evidence,
Gold annotations, canonical facts, or frontend data. `canonical_write_back` and
`external_search_performed` are explicitly false in every generated state.
