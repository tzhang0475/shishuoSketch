# HNG2-L — Live Hybrid Resolver & Frontier Growth Validation

HNG2-L is an evaluation wrapper around the frozen HNG2 implementation. It
does not change the resolver, retrieval ranking, source corpora, canonical
Persons, relations, facts, Gold, NL, SRM, or the HNG2 generated baseline.

## Run boundary

`scripts/run_hng2_live.py` first writes a deterministic 24-person selection
under `data/generated/hng2-live/live-selection.json`. The selection is frozen
against the HNG2 frontier and baseline hashes before any network request.

The runner then performs one authenticated DeepSeek preflight. A failure such
as `sandbox_denied`, `proxy_failure`, DNS failure, timeout, or authentication
failure stops the run as `live_network_unavailable`; it does not create a
Story/person model finding or a protocol failure. Preflight details are kept
in `/tmp/hng2-live-preflight.json`.

Live extraction uses the existing persistent DeepSeek transport and the frozen
punctuated-first FIND/OPEN implementation. Each opened passage is checked by
the seed identity gate and temporal gate before being sent to Flash. Valid
model claims still require an exact source quote. Deterministic identity
resolution runs first; only ambiguous/unresolved residuals are eligible for
identity assist. The model receives candidate keys, never Person IDs.

Only two research waves are allowed. Wave 2 is capped at eight independently
eligible new nodes. A third wave cannot be created. Candidate relations and
temporal items remain a generated review layer and are never promoted to
canonical history.

## Artifacts

The live namespace contains selection, retrieval/gate traces, immutable raw
API responses, deterministic and LLM identity projections, relations,
temporal candidates, Wave-2 results, audits, metrics, and a manifest. Raw API
responses are written below `data/generated/hng2-live/raw-api/<run_id>/` and
are never overwritten within a run.

The review overlay is
`data/annotation/hng2-live-review.json`; all rows start as `not_reviewed`.

Offline validation is safe and makes no API calls:

```text
python3 scripts/validate_hng2_live.py --mode portable
python3 -m unittest tests.test_hng2_live
```

Run the live command only with approved network access:

```text
python3 scripts/run_hng2_live.py
```

If preflight reports `live_network_unavailable`, rerun the same command in a
network-approved Codex execution. Do not substitute fixture data and do not
classify environment denial as an HNG2 protocol or semantic result.
