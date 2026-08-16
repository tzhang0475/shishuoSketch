# NL0 — Grounded Story Sketch Prototype

NL0 is a seven-Story, non-canonical narrative projection built from the
reviewed HR0 HistoricalSituation set, HR0.1 ambiguity cases, existing
reviewed historical-fact indexes, and the Story evidence IDs already present
in SC1. It is a product slice for judging whether a small amount of grounded
augmentation helps a reader enter a Story. It is not a new historical layer.

## Pilot scope

The selected Stories cover a simple single exchange, a multi-episode report,
title and identity ambiguity, a retrospective annotation, comparative
evaluation, family context, and event context:

`02-yanyu-035`, `02-yanyu-036`, `05-fangzheng-032`, `06-yaliang-017`,
`09-pinzao-017`, `19-xianyuan-026`, and `27-jiajue-008`.

The selection is frozen in [nl0-story-sketch-review.json](../data/annotation/nl0-story-sketch-review.json).
It is a hand-reviewed deterministic candidate layer, not a ranking and not a
model output.

## StorySketch v0

Each accepted record contains only:

- `era_profile`: a coarse, evidence-backed orientation; it may be `null`.
- `scene_core`: the action or exchange that carries the Story.
- `essential_background`: zero to two short items only.
- `resonance`: an optional restrained after-note; it may be `null`.
- `supporting_evidence`: evidence IDs and their existing source layers.
- `review_status`: `accepted` in the Gold projection.

Every narrative claim carries one or more existing SC1/HR0 evidence IDs.
HR0.1 case IDs and reviewed historical-fact IDs are retained in the review
and Gold artifacts as grounding lineage, but are not copied into the browser
display shard. The original Story text remains in SC1 and is never rewritten.

The projection deliberately keeps the distinctions already established by
the historical pipeline. Liu annotation remains annotation evidence; an
annotation-backed after-note is not silently presented as a new canonical
fact. Unknown dates remain unknown, and an empty field is an explicit
abstention rather than an invitation to fill a gap with interpretation.

## Candidate, review, and display boundary

The flow is:

```text
HR0 / HR0.1 / reviewed fact inputs
        ↓
manual grounded StorySketch candidate
        ↓
reviewed + accepted
        ↓
small static StorySketch shard
```

`data/derived/nl0-story-sketch-candidates.json` retains the candidate/review
decision state. `data/derived/nl0-story-sketch-gold.json` contains only
accepted records. The frontend serves only the latter through
`site/public/generated/nl0/story-sketch/<story_id>.json`.

NL0 uses no LLM, RAG, vector retrieval, temporal solver, or automatic fact
materialization. It does not write back to canonical Stories, Persons,
Mentions, Relations, HistoricalFacts, HR0, or HR0.1.

## Frontend prototype

When the development feature flag is enabled, the seven Stories expose an
`Original | Sketch` switch. Development mode enables it by default; a
production build can opt in with `VITE_NL0_STORY_SKETCH=1`.

The Story text remains the reading anchor in both views. Sketch mode adds a
restrained panel for `Era`, `Scene Core`, `Essential Background`, and the
optional `Resonance`, followed by a compact evidence disclosure. A Sketch
shard is fetched only after the user chooses `Sketch`; it is not statically
imported or fetched on Story-reader startup. The existing in-memory evidence
loader supplies full evidence only after `查看依据` is opened.

## Initial judgment

The first slice is intentionally small enough for direct human comparison.
The NL0 metrics record two resonance notes and explicit abstentions for the
remaining fields. The next decision should be made from reading tests: if
Era, Scene Core, Background, or Resonance does not improve most selected
Stories without adding interpretive weight, revise this projection before
expanding coverage.

NL0 does not implement HR1, HG1.1, ML1.1, X1.2B, or ER2.
