# W4 — Structural & Temporal Expansion

W4 is a story-first expansion wave. Its purpose is to make the existing
Story–Person–Era network denser and more useful for later social-backbone
work, rather than to increase corpus counts in isolation. The wave uses only
the repository's acquired Shishuo, Liu, Jinshu, Sanguozhi, Tongjian and H0A /
H0B-derived evidence.

## Frozen selection

The candidate audit covers all canonical entries that were not already in the
83-Story production/preview scope. It records canonical hashes, punctuation
availability, current Person connections, strong identity candidates,
structural signals, temporal/event signals, chapter diversity, narrative
value, identity risk and isolation risk in
`data/derived/w4-story-candidate-audit.json`.

The selection is frozen in
`data/annotation/story-expansion-wave-4.json`. The first deterministic wave
publishes 60 Stories, bringing the static reading scope to 143. The wave is
inside the requested 45–75 range, but the count is a result of the evidence
ranking rather than a publication quota. Every selected Story has a canonical
source hash, punctuation projection, identity-coverage record, H0A anchor and
one E0.1 primary Era orientation.

The 25 selected new Persons are frozen in
`data/annotation/person-expansion-wave-4.json`, with ranking detail in
`data/derived/w4-person-expansion-ranking.json`. They receive opaque IDs
`person-051` through `person-075`; `person-001` through `person-050` remain
unchanged. Materialized identity records retain candidate review status. A
historical identity is not promoted merely because it was mentioned: the
selection favors identities with multiple useful Story uses, connections to
existing Persons, bridge value, or at least one unambiguous exact source
coordinate. The final materialization also leaves ambiguous span collisions
non-clickable.

The selected names are 荀顗、祖約、王廙、王隱、氾騰、李重、沈充、鍾雅、孫盛、虞預、習鑿齒、
郭奕、郭象、陶侃、孟嘉、卞範之、周浚、崔遊、束晳、趙至、劉遐、劉隗、吳隱之、干寳、徐廣.

## Identity publication gate

W4 reuses the effective ER1 resolution layer, including derived Story-local
span decisions. Exact string matching remains candidate evidence; a selected
Story is not allowed to ship with an expected safe identity silently omitted.
The identity projection records safe, ambiguous, non-production and unresolved
surfaces separately. Withheld spans remain explicit rather than being counted
as omissions.

The gate preserves the existing collision fixes:

- `14-rongzhi-024`: `庾太尉` is Story-locally `庾亮` (`person-010`); `庾公`
  is not a global alias for `公`.
- `23-rendan-013`: `仲容` is the non-production historical identity 阮咸,
  never 石苞 (`person-037`).
- `01-dexing-026`: `少孤` remains ordinary lexical prose, not 孟陋.
- repeated `周侯` and `桓子野` span decisions remain governed by the
  existing contextual resolver.

For this wave the identity projection reports 219 safe resolved surfaces, 10
ambiguous surfaces, 8 non-production identities, 0 unresolved surfaces, 10
withheld span collisions and 0 unexpected safe omissions. Non-production and
ambiguous identities are honest exclusions from reader navigation, not
reasons to invent a Person.

## Social-temporal projection

W4 does not recompute or replace the frozen H0B-0 pilot. It creates a new
readiness projection in `data/derived/w4-structural-readiness.json`; the
original H0B-0 selection, facts and rationale remain inputs, not mutable
outputs. New Persons and Stories expose future H0B-1 opportunities, but W4
does not materialize new Clan, Kinship, Marriage or Office facts and does not
create reviewed Relations.

`data/derived/w4-social-temporal-constraints.json` is a research projection,
not a second temporal backbone. It keeps direct H0A evidence separate from
participant constraints and only considers scene-present Persons when such a
projection is possible. Off-frame references, Liu biography subjects,
later-outcome statements, clan membership and friendship do not date a Story.
Any possible H0A refinement is recorded as a candidate and must not silently
rewrite `StoryTemporalAnchor`. In this first wave there are no automatic H0A
upgrade candidates; the new Stories retain the conservative H0A result,
including honest `unknown` anchors where appropriate.

Reader orientation is separate from historical assertion. The E0.1 builder
still assigns exactly one primary Era Card to every Story. A broad or corpus
orientation may help a reader enter the historical neighborhood without
claiming an exact year.

## Network effect and limits

The wave produces 881 PersonStory edges (876 reviewed and 5 candidate), with
75 production Persons and 143 Stories. Seven newly materialized Persons are
currently useful bridge candidates to existing Persons; their structural
meaning remains a future H0B-1 review question. Random-Person eligibility
rises from 45 to 69 without adding a title-only or span-collision identity.
The reviewed Relation count remains 12, Scene Context count remains 44, and
orphan Mentions remain zero.

The remaining family, marriage and office gaps are recorded rather than
filled speculatively. Missing bridge identities and possible future Stories
remain in the H0B readiness artifacts. W4 therefore stops before H0B-1,
H0A.2, P4, ES0 and another expansion wave.

## Deterministic artifacts

The W4 builders are:

- `scripts/build_w4_expansion.py` — candidate audit and frozen Story/Person
  selection;
- `scripts/materialize_w4_person_expansion.py` — recoverable W4 Person,
  Alias, Mention, Evidence and Sketch projection;
- `scripts/build_w4_projections.py` — identity coverage,
  social-temporal constraints, structural readiness and metrics;
- `scripts/validate_w4.py` — publication, identity, temporal, navigation and
  protected-baseline checks.

All generated IDs are based on frozen allocation or source coordinates. The
wave is rebuilt twice during validation and its generated artifacts are
compared byte-for-byte. Canonical source payloads are never rewritten.
