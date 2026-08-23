# SRM0.5 — Fresh-Story Generalization & Convergence Evaluation

SRM0.5 evaluates the frozen SRM0.4 convergence protocol on a deterministic,
fresh 15-Story sample. It is an evaluation layer only: it does not tune the
prompts, retrieval ranking, stopping thresholds, or semantic contracts after
live execution begins.

## Selection

The selector reuses the SRM0.4 commentary richness rules:

- rich: main text ≥ 50 characters, at least 4 Liu blocks, and at least 500
  Jianshu characters;
- medium: attached commentary exists but the rich rule is not met;
- low-context: at most 1 Liu block and at most 99 Jianshu characters.

Within each stratum, `SHA-256(Story ID)` selects five records. Every Story ID
recorded by earlier SRM artifacts is excluded, including IDs that appeared as
retrieval evidence. The frozen selection and its rationale are in
`data/generated/srm0/srm0-5-selection.json`.

## Frozen protocol

Round 0 receives only the canonical main text. Round 1 receives the attached
Liu and Jianshu commentary. Later rounds use the existing bounded local
retrieval and semantic-delta contracts only for unresolved high-impact
questions. The maximum number of evidence rounds remains four. The current
SRM0.4 helper hashes, prompt version, model parameters, and selection hash are
recorded in `data/generated/srm0/srm0-5/protocol-freeze.json`.

Live execution performs one authenticated preflight before creating Story run
results. Transport failures, protocol failures, and semantic failures remain
separate. A preflight/network failure aborts the batch and is not counted as a
model finding. Transport retry follows SRM0.4C: at most one retry for an
allowed transport error; valid model responses are never rerun.

## Metrics

The primary unit is a question, not a Story. A question converges only when it
reaches one of `reading_sufficient`, `evidence_saturated`,
`stable_conflict`, `unresolved_no_evidence`, `not_worth_pursuing`, or
`hard_cap`. Active unresolved questions remain visible. Each evidence round
retains `G_t`, `D_t`, `N_t`, and `Q_t`, along with retrieved, opened, and
actually used evidence refs.

Attached-commentary resolution and later local historical retrieval are
reported separately. “External evidence need” means evidence beyond the
attached commentary; it is counted when the controller actually enters a
post-commentary retrieval attempt, even if the model ultimately uses none of
the returned hits. The retrieval itself remains local and never uses the web.

## Artifacts and execution

All outputs are isolated below `data/generated/srm0/srm0-5/`. Fixture output,
when used for plumbing tests, is under `fixture/` and is never included in
the live summary. Live raw responses are immutable under
`live/<story_id>/<run_id>/`.

```bash
python3 scripts/run_srm0_5.py --select
python3 scripts/run_srm0_5.py --batch       # approved network required
python3 scripts/validate_srm0_5.py --mode full
python3 scripts/run_srm0_5.py --replay-existing
```

`data/generated/srm0/srm0-5/summary.json` contains Story and question-level
results. `metrics.json` contains round trajectories. The two files under
`data/annotation/` are review-only artifacts and never update Gold or
canonical historical data.

The post-live deterministic replay excludes `refined_to_child` parent nodes
from the evaluable-question denominator, as in SRM0.4D. This is recorded in
`metrics.json`; it changes only the reporting projection, not raw outputs or
the frozen research loop.

SRM0.5 does not claim statistical significance from 15 Stories and does not
collapse convergence behavior into an opaque score.
