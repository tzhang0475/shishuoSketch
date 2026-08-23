# SRM0.4B — Robust Live Convergence Protocol

SRM0.4B retests the frozen six-Story SRM0.4A pilot without changing its
research loop. The protocol is additive: it reuses the existing local
commentary and historical-source registry, but writes into a separate
`convergence/live/<run_id>/` or `convergence/fixture/<fixture_version>/`
tree. A fixture run can exercise plumbing and normalization, but is never
included in live-model findings.

## Fail-soft boundary

Initial gaps are gated independently. Invalid spans, explanation leakage,
self-resolved gaps, and low-leverage gaps are recorded as rejected while
other valid gaps continue. In later rounds, harmless structural noise is
recorded and removed; Python-owned state fields are never treated as model
semantics. Evidence is validated one item at a time against the supplied
local source text. An invalid evidence item removes its claim only when no
valid evidence remains; other claims and questions survive.

Python derives state, `next_action`, terminal reasons, Working Answers, and
`G_t / D_t / N_t / Q_t`. `D_t` requires a validated evidence-backed change;
wording-only edits do not count. `Q_t` is set only for a child linked to a
specific parent unresolved aspect. The SRM0.4A stopping rules remain in
force, including reading sufficiency, saturation, stable conflict, no
adequate evidence, and the four-round cap.

## Running

Before a live batch creates any Story artifact, the runner performs one
minimal request through the same DeepSeek client. If the request is blocked by
the Codex sandbox, local proxy, DNS, timeout, authentication, or server
failure, the batch exits with `live_network_unavailable`; it does not create a
Story-level protocol failure or write a live summary. The diagnostic is kept
at `/tmp/srm0-4b-live-preflight.json`. Run live mode from a network-approved
Codex execution. Replay and fixture mode do not require network access.

Reset generated 0.4A/0.4B results before a clean run:

```bash
python3 scripts/reset_srm0_4.py
```

The reset preserves `srm0-4a-selection.json`, source code, tests, review
templates, and earlier SRM artifacts. It writes only the clean-run marker
`data/generated/srm0/srm0-4-status.json`.

Fixture plumbing:

```bash
python3 scripts/run_srm0_4b.py --fixture --batch
python3 scripts/validate_srm0_4b.py --mode fixture
```

Live model run (requires `DEEPSEEK_API_KEY`):

```bash
# execute this command with network approval from the start
python3 scripts/run_srm0_4b.py --batch
python3 scripts/validate_srm0_4b.py --mode live
```

Live output is stored below each Story's deterministic `live/<run_id>/`
directory. Fixture output is stored below `fixture/fixture-v1/`; the two
trees and their batch summaries are never merged. No web search or canonical
trees and their batch summaries are never merged. A post-preflight API
transport interruption is recorded separately from protocol/semantic
evaluation failures. No web search or canonical write-back is performed.
