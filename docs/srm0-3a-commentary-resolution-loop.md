# SRM0.3A — Commentary Resolution Loop Pilot

SRM0.3A is an isolated two-completion experiment for
`03-zhengshi-005`:

1. Completion 1 sees only the canonical Shishuo main text and discovers at
   most three reading questions.
2. Completion 2 sees the unchanged questions, all ten Liu annotation blocks,
   and only the non-duplicate local Jianshu blocks (`J07` and `J08`–`J14`).

Completion 2 must provide its own commentary `ref` and exact short `quote`.
Python validates those references and aligns whitespace only; it does not
guess which note supports a claim.

The persistent `research-state.json` stores compact working answers,
sufficiency states, supporting refs, remaining gaps, and next actions. Long
source quotations remain in the round artifacts. `events.jsonl` is a
deterministic projection of auditable decisions and contains no hidden model
reasoning.

`external_search` is a boundary signal only. SRM0.3A never executes it, never
executes a refined question, and never writes canonical, Gold, PersonStory,
graph, or frontend data.

Run the pilot with exactly two API completions:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_srm0_3a.py --story 03-zhengshi-005
python3 scripts/validate_srm0_3a.py
```

Artifacts are under:

```text
data/generated/srm0/03-zhengshi-005/commentary-resolution/
```

The human review template is:

```text
data/annotation/srm0-3a-commentary-resolution-review.json
```
