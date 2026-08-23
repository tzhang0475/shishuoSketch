# HNG0.1 — Evidence-Guided Person Growth

HNG0.1 is a research-only growth layer over the frozen 24-person HNG0 seed
selection. It is deliberately separate from HNG0's existing relation
candidates and from canonical `Person`, `Relation`, `Event`, `Fact`, Gold, and
SRM data.

## Pipeline

For each seed, the runner builds a deterministic search profile, routes local
sources, performs lexical **FIND**, opens only a small set of source windows,
and sends those exact windows to DeepSeek for candidate extraction. Python
then validates each claim independently: the source ref must be opened and the
quote must occur in the opened source text. Invalid claims are discarded
without discarding valid claims from the same response.

The supported local source families are Jinshu, canonical Shishuo main text
and Liu annotation, the registered local Yu Jiaxi Jianshu bundles, SGZ1, and
the processed Zizhi Tongjian text/annotations. Paths under `data/generated/`
are never part of the searchable source inventory. Every retrieval trace
records `searched`, `retrieved`, `opened`, and `used` refs plus the routing
reason.

## One-hop and identity boundaries

Only a seed-to-new-neighbor edge is projected. An existing seed counterpart is
not counted as a new neighbor. Python resolves a returned surface against the
existing Person/alias/courtesy/title catalog; ambiguous and unresolved
surfaces remain candidate records with a provisional local node and never
create a canonical Person.

Relations are accepted as candidates only for explicit source-supported
classes. Story co-occurrence, shared surnames, and model-only interpretation
cannot create an edge. Multiple supporting passages merge into one candidate
edge while retaining all evidence refs and claim conflicts.

Temporal candidates are similarly evidence-backed. Existing HNG0 temporal
spines are used only as compatibility constraints; uncertain chronology is
flagged for review rather than silently rejected or converted into exact
years.

## Running and review

Run the real path with:

```bash
python3 scripts/run_hng0_1.py
```

The runner performs a minimal DeepSeek preflight. A sandbox/network failure
produces `execution_kind: live_model_unavailable` and zero model candidates;
it does not fabricate fixture output. Raw model responses, when available,
are append-only under `data/generated/hng0-1/raw-extractions/`. The candidate
and review overlay are under `data/generated/hng0-1/` and
`data/annotation/hng0-1-review.json`.

`audit-sample.json` deterministically contains the first ten relation
candidates, first five temporal candidates, and any ambiguous or temporally
flagged candidates together with their opened source passages.

The Person page shows HNG0.1 items with the label **Newly extracted**. Its
Accept / Reject / Uncertain / Needs more evidence controls use a separate
browser-local review store and do not write canonical history.

HNG0.1 is evidence infrastructure. A reviewed candidate still requires an
explicit later project decision before it could affect any canonical layer.
