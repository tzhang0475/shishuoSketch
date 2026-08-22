# SRM0.1 — Single-Story Single-Cycle Research Memory Pilot

SRM0.1 is an isolated experiment for `27-jiajue-008`. It runs one bounded
cycle:

```text
Story + orientation cards
  → Completion 1: textual puzzles and one active question
  → local character-window retrieval
  → Completion 2: evidence decisions and a memory patch
  → one refined next question (recorded, not executed)
```

The model sees the original Story, Liu annotations, a compact era card,
deduplicated person orientation cards, and a narrow conflict notice. It does
not receive biographies, historical interpretations, Gold annotations, full
Person research surfaces, or generated DS output.

Retrieval is local and deterministic. It searches registered Shishuo,
Jianshu assertion, and processed Jinshu source units using exact character
matches plus small 2/3-character overlap terms. Windows are formed directly
from source-unit character offsets; no punctuation or sentence segmentation is
used as an evidence boundary. Model-facing windows contain only a ref, work,
source layer, and source-derived snippet. Paths, hashes, offsets, and ranking
details stay in the local trace.

The generated state and JSONL event log are research memory, not canonical
history. Evidence decisions and claims retain refs, and the state is marked
`canonical_write_back: false`. The manual review template is separate from
HR/NL Gold data. `Q2` is written as `next_question_pending_not_executed`; the
pilot stops after Completion 2.

Run a local fixture without an API call:

```bash
python3 scripts/run_srm0_1.py --fixture --story 27-jiajue-008
```

Run the one real cycle with the existing client:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_srm0_1.py --story 27-jiajue-008
python3 scripts/validate_srm0_1.py
```

Inspect or manually edit only:

```text
data/generated/srm0/27-jiajue-008/
data/annotation/srm0-1-review.json
```

No SRM artifact is consumed by production builders, and the refined question
is not executed by this milestone.
