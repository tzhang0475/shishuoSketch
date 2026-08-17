# F0 — User Feedback Foundation

F0 adds a small feedback boundary without making feedback part of the
historical corpus. The flow is:

```text
reader
  → raw feedback
  → human review
  → reviewed export
```

Feedback is never read by SC1, H0C, HR, NL, HG, or ML builders and cannot
promote a Story, Person, Mention, Relation, Fact, Gold annotation, or
narrative projection.

## Reader entry points

Published Stories expose `反馈此页`. The submission captures the current
Story, target type/ID, category, reason, page URL, frontend version, data
version, an optional comment, and a bounded text snapshot. No name, email, or
other account field is requested.

The same control is available for stable evidence IDs shown in Story/Scene,
Further Reading, and Story Sketch evidence disclosures. The reviewed NL0
Sketch uses its existing `story-sketch-nl0-<story_id>` ID as a narrative target.

Categories are `text`, `historical_fact`, `narrative`, `bug`, and `other`.
Narrative reasons include `inaccurate`, `unnecessary`, `overinterpreted`,
`insufficient_evidence`, `missing_context`, and `other`.

## Storage boundary

`site/src/feedback.ts` defines the small `FeedbackRepository` interface and
the HTTP contract:

```text
POST  /api/feedback
GET   /api/feedback?story_id=...&target_type=...&target_id=...
PATCH /api/feedback/<feedback_id>
```

Set `VITE_FEEDBACK_ENDPOINT` to use an API/database adapter. Without that
setting, local development uses browser `localStorage` under the dedicated
`shishuoSketch.feedback.raw.v1` key. This fallback is disposable runtime
storage, not repository data. It has bounded text sanitization and duplicate
protection; the API remains responsible for production authentication,
durable storage, and server-side rate limits.

The Python `LocalFeedbackRepository` in `scripts/feedback_store.py` is the
file-backed development/export implementation. It writes raw JSONL only to
the ignored path:

```text
.cache/shishuo-feedback/raw-feedback.jsonl
```

It exposes a rate-limit hook so a future server adapter can provide a real
request/IP policy without changing the record contract.

## Review and export

In development, or when `VITE_FEEDBACK_REVIEW=1` is set, the current Story
shows a compact `反馈审阅` surface. Reviewers can inspect target IDs and
snapshots, set the existing lifecycle statuses, and mark one record as a
duplicate of another. This surface changes only feedback storage.

`python3 scripts/export_user_feedback.py` writes the deterministic reviewed
projection:

```text
data/annotation/user-feedback-reviewed.json
```

Only final review states (`accepted`, `rejected`, `duplicate`, `resolved`)
are exported. Transport/runtime fields such as the page URL and the raw
fingerprint are omitted. The export has its own `f0-reviewed-feedback` schema
and explicitly records that canonical and Gold write-back are disabled.

Run `python3 scripts/validate_feedback.py` to check Story/target references,
status/category enums, export determinism, and the storage boundary.

