# SRM0.3B — Minimal Question + Semantic Delta Pilot

SRM0.3B is an isolated, two-completion experiment for `03-zhengshi-005`.
Completion 1 sees only the canonical Story正文 and emits at most three concise
reading gaps. Python freezes `question_id`, `story_span`, and `gap`; no model
explanation is passed to Completion 2.

Completion 2 sees the frozen gaps plus the ten canonical Liu notes and the
non-duplicate Yu Jiaxi commentary notes already resolved by S1. It emits only
semantic deltas: answered aspects, unanswered aspects, conflicts, sufficiency,
and an optional narrow refined question. Evidence refs and exact quotes are
validated against the supplied commentary packet. Python mechanically derives
the state, next action, compact Working Answer, events, and comparison report.

The run is bounded to exactly two DeepSeek completions and performs no search.
`research-state.json` is generated working memory; it is not a cache and never
writes canonical, Gold, PersonStory, frontend, or previous SRM artifacts.

Generated artifacts are under:

```text
data/generated/srm0/03-zhengshi-005/commentary-resolution-v2/
```

Use the live run only when `DEEPSEEK_API_KEY` is available:

```bash
python3 scripts/run_srm0_3b.py --story 03-zhengshi-005
python3 scripts/validate_srm0_3b.py
```

Offline contract checks use:

```bash
python3 scripts/run_srm0_3b.py --story 03-zhengshi-005 --fixture
python3 -m unittest tests.test_srm0_3b
```

The fixture is plumbing-only and must not be reported as model evidence.
