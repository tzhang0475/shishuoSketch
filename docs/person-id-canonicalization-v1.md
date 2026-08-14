# P-ID1 Person ID canonicalization

This one-time migration changes production Person identity keys and their
structured foreign keys only. It does not change historical assertions,
canonical text, source provenance, punctuation, Story publication, Relations,
or Person identity membership.

## Frozen allocation

The migration manifest is `data/migrations/person-id-canonicalization-v1.json`.
The six bootstrap assignments follow the existing `PERSON_DEFINITIONS` order;
`person-007` remains the supporting bridge Person; Wave 1 follows the frozen
pre-materialization P3A rank order.

| Old production ID | New production ID | Canonical name | Allocation basis |
|---|---|---|---|
| `wang-xizhi` | `person-001` | 王羲之 | bootstrap order 1 |
| `xi-jian` | `person-002` | 郗鑒 | bootstrap order 2 |
| `wang-dao` | `person-003` | 王導 | bootstrap order 3 |
| `wang-ningzhi` | `person-004` | 王凝之 | bootstrap order 4 |
| `xie-daoyun` | `person-005` | 謝道韞 | bootstrap order 5 |
| `xie-an` | `person-006` | 謝安 | bootstrap order 6 |
| `person-007` | `person-007` | 郗璿 | supporting Person preserved |
| `huan-wen` | `person-008` | 桓溫 | P3B Wave 1 rank 1 |
| `liu-dan` | `person-009` | 劉惔 | P3B Wave 1 rank 2 |
| `yu-liang` | `person-010` | 庾亮 | P3B Wave 1 rank 3 |
| `wang-dun` | `person-011` | 王敦 | P3B Wave 1 rank 4 |
| `yuan-hong` | `person-012` | 袁宏 | P3B Wave 1 rank 5 |
| `wen-qiao` | `person-013` | 温嶠 | P3B Wave 1 rank 6 |
| `wang-meng` | `person-014` | 王濛 | P3B Wave 1 rank 7 |
| `sun-gui` | `person-015` | 孫晷 | P3B Wave 1 rank 8 |
| `wang-xia` | `person-016` | 王遐 | P3B Wave 1 rank 9 |
| `su-jun` | `person-017` | 蘇峻 | P3B Wave 1 rank 10 |

The next available production Person ID is `person-018`. IDs are assigned
once, are never generated from names or display text, and are not a runtime
translation layer.

The frozen ranking identity is unchanged. The pre-P-ID1 ranking snapshot hash
was `15dec56de3beb7617fe87c727fb5800ef3313de6025303ad05750d3cf3f18ae3`.
Because the ranking artifact contains scoped Person foreign keys, its
post-migration hash is
`a81eefefea58f7910dd5ad997a84b395a5220a906ee46f19f44ef630362dcab2`; both
values are retained in the Wave 1 manifest as distinct audit facts.

## Migrated layers

The field-aware migration utility is `scripts/migrate_person_ids.py`; it
updates only registered Person-reference fields and narrow generated Person
record/key contexts. The source builders now use the opaque bootstrap IDs,
and the Wave 1 materialization path consumes the frozen manifest. P3A.1
rediscovery classifies all 17 existing identities as `already_materialized`.

Migrated/rebuilt projections include:

- canonical Person, Alias, Mention, Person Sketch, Relation-adjacent WP1
  projections, and Scene Context Person references;
- PersonStory and SC0 chain indexes;
- P3A/P3A.1 derived analysis projections;
- R3A candidate endpoints (candidate IDs remain frozen opaque analysis IDs);
- WP1/SC1 generated bundles and the Vite input.

After migration, P3A.1 reports 17 `already_materialized` identities and 313
eligible `strong_candidate` identities; the rerun P3A ranking contains those
313 eligible candidates and excludes all 17 production Persons. The frozen
Wave 1 membership remains the same ten candidates and is not reselected from
this post-migration ranking.

Alias IDs, Mention IDs, Evidence IDs, Relation IDs, Story IDs, candidate IDs,
source IDs, and canonical source payloads were not renamed. Generated
PersonStory link records retain the same Story/source-layer/mention topology;
their generated link keys are rebuilt from the new Person keys.

## Semantic before/after checks

The canonical-name keyed comparison was byte-equivalent after removing only
primary-key fields from the comparison:

- Persons: 17 before / 17 after; canonical-name set unchanged.
- Shishuo Mentions: 773 / 773; Jinshu Mentions: 711 / 711; surfaces, anchors,
  source layers, resolution semantics, and evidence unchanged.
- Alias surfaces and exact/contextual semantics unchanged.
- PersonStory: 330 links before / 330 after; Story IDs, source layers,
  presence kinds, and supporting Mention IDs unchanged.
- Relations: 7 before / 7 after; 6 reviewed direct and 1 reviewed derived;
  neighbor topology, relation IDs, roles, evidence, and basis unchanged.
- Scene Context: 9 before / 9 after; scene people, roles, text, evidence, and
  review status unchanged.
- SC0/SC1 publication selection: 16 Stories before / 16 after.
- Random Person eligibility: 13 before / 13 after, with only the ID keys
  translated.

## Deterministic output hashes

| Artifact | SHA-256 |
|---|---|
| `data/people.json` | `a921afaf903f5838c3bb2ed1945bfea33bd6cbe7338c7cc672a28ec57b3808d6` |
| `data/aliases.json` | `eff45bfa7110226d053cd17efe829469b8bbe356c95cee00cd29494855363f1e` |
| `data/mentions/shishuo.json` | `5834eb625a60ee9c19f6af2e9e5777cf16dcdf269a5a8453a1167871210fa361` |
| `data/mentions/jinshu.json` | `e8d07481a0ea9fd7ce93467f71e907c76b0b975ff5b4f8972ff15c2d7b56bab4` |
| `data/derived/person-story-links.json` | `da630bf3bfc3c9758f54e5ee8152a8d534b61a89b78f7db883ba121422466d34` |
| `data/derived/story-scene-contexts.json` | `236dd3b439ea006c82444bc88a731cc5a4b2500358c965dd7cfbfdc9cbc37332` |
| `data/derived/sc1-site.json` | `575a345be65e23afe1491a281f46b476c36679490df159d15a7fd307746b3cc7` |
| `site/src/generated/sc1-site.json` | `575a345be65e23afe1491a281f46b476c36679490df159d15a7fd307746b3cc7` |
| `data/derived/person-expansion-wave-1-materialization.json` | `c6c6585a42bd21e8793b13954187fdd15a70951b945e40a7bdcf8fbf4e0adac8` |
| `data/derived/person-relation-candidates-r3.json` | `bede98151442d13a44359e5e3e9a7884e17f739daab8445dba896b72cbd22d72` |

The generated SC1 projection grew from 4,050,061 to 4,051,185 bytes
(`+1,124`) because its internal Person foreign keys changed; its displayed
content and navigation semantics are unchanged. The production Vite build
emits a 3,533.13 kB JavaScript asset (1,094.58 kB gzip).

## Legacy-ID leak audit

No former slug remains in an active structured Person-reference field, source
builder, validator, frontend code, or generated frontend bundle. The old
values have this explicit allowlist:

- `data/migrations/person-id-canonicalization-v1.json`: `old_person_id`
  history in the one-time migration manifest;
- this document: the old-to-new audit table and migration explanation;
- existing `alias_id` values in `data/aliases.json`, the bootstrap
  `ALIAS_SPECS`, and their generated projections; these are Alias IDs, not
  Person IDs;
- existing generated Mention/Evidence namespaces where a legacy token is part
  of an opaque semantic ID; these are not Person foreign keys.

The active structured-reference validator rejects every former production ID
outside that allowlist. No former slug remains as an active structured Person
reference in production data, builders, validators, frontend code, or the
generated frontend Person projection.

The canonical Shishuo/Jinshu text, raw witnesses, punctuation records,
provenance identities, SC0/SC1 selection, Relation facts, Scene facts,
Sanguozhi data, and Wave 1 candidate/rank membership remain unchanged.

## Validation

- P-ID1 and related focused tests: 43 tests, 1 expected skip.
- Full Python suite: 301 tests, 1 expected skip, green in full and portable
  provenance modes.
- P3A.1, P3A, P3B.1, Person Sketch, PersonStory, Relation/R3A, Scene Context,
  SC0, SC1, CRL1, and WP1 validators: green in required full/portable modes.
- `npm run typecheck`, `npm run build`, production frontend artifact
  validation, deterministic report rebuild, and `git diff --check`: green.

The protected punctuation/index hashes were unchanged, and no protected
processed corpus, raw source payload, or publication-selection path was
modified. This migration changes identity keys only; it does not change
historical assertions.
