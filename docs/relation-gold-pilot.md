# R1 / R1.1 Relation Gold Pilot

This document records the manually reviewed hard-relation pilot for the six
WP1 people. It is an editorial audit, not a frontend graph or a complete
genealogy. Direct Gold relations with `review_status: reviewed` are supported
by a direct primary-text or Liu Xiaobiao annotation quotation. A reviewed
derived relation is separate: it is deterministic, carries no direct quotation,
and points to its reviewed source relations.

The existing Relation object remains one semantic edge. `subject_id` and
`object_id` carry the edge direction where a kinship role is directional;
spouse edges use one canonical endpoint order and `配偶` on both ends. Source
entry/unit IDs and Evidence locators preserve the route back to the canonical
artifacts.

## Direct Gold relations

The six atomic R1 Gold relations below are unchanged. Each has
`relation_basis: direct`.

| Relation | Person A / role | Relation | Person B / role | Evidence and location | Why secure |
| --- | --- | --- | --- | --- | --- |
| `relation-gold-001` | 王導 / 從伯 | kinship · collateral_kinship | 王羲之 / 從子 | `evidence-007`, `evidence-012`; 《晉書》`080-liezhuan-001`, `王羲之字逸少司徒導之從子也`、`深為從伯敦導所器重` | The biography explicitly identifies 導 as 羲之的從子關係中的從伯. |
| `relation-gold-002` | 王羲之 / 父 | kinship · parent_child | 王凝之 / 子 | `evidence-008`; 《晉書》`080-liezhuan-001`, `諸子遵父先㫖固讓不受有七子知名者五人<!-- wikisource-SKchar: {"value": "2593"} -->之早卒次凝之亦工草<!-- wikisource-SKchar: {"value": "1452"} -->` | The preserved passage places 凝之 among 王羲之諸子 and continues with 凝之's biography; source markup is retained exactly. |
| `relation-gold-003` | 王凝之 / 配偶 | marriage · spouse | 謝道韞 / 配偶 | `evidence-005`; 《晉書》`096-liezhuan-016`, `王凝之妻謝氏字道韞` | The unit opening explicitly states the marriage and identifies 謝氏字道韞. |
| `relation-gold-004` | 謝安 / 叔父 | kinship · uncle_niece | 謝道韞 / 姪女 | `evidence-009`; 《晉書》`096-liezhuan-016`, `王凝之妻謝氏字道韞安西將軍弈之女也聰識有才辯叔父安嘗問` | The biography explicitly calls 安 叔父 while discussing 道韞. |
| `relation-gold-005` | 郗璿 / 配偶 | marriage · spouse | 王羲之 / 配偶 | `evidence-010`, `evidence-011`; canonical Shishuo entry `06-yaliang-019` main text `因嫁\n女與焉` and Liu annotation `妻太傅郗鑒女名璿字子房` | The main text records the marriage; the annotation identifies the bride as 郗鑒's daughter 璿. |
| `relation-gold-006` | 郗鑒 / 父 | kinship · parent_child | 郗璿 / 女 | `evidence-011`; canonical Shishuo entry `06-yaliang-019`, Liu annotation `妻太傅郗鑒女名璿字子房` | The annotation explicitly states that 璿 is 郗鑒's daughter. |

The relation evidence is drawn only from the existing canonical Shishuo entry,
its preserved Liu annotation, and the complete local Jinshu structural units.
No reference witness, web page, or general-knowledge genealogy is used to
promote a relation.

## Derived relation

`relation-001` (`person-002` → `person-001`, `婚姻亲属`) is now a reviewed
deterministic relation with:

```text
review_status: reviewed
assertion_status: inferred
relation_basis: derived
derived_from_relation_ids:
  - relation-gold-006
  - relation-gold-005
evidence_ids: []
```

Its derivation is the explicit path `郗鑒 → 郗璿 → 王羲之`. It is not an
additional directly attested atomic edge, and no source quotation claiming
“郗鑒是王羲之岳父” has been fabricated. The existing broad label is retained
for compatibility only.

## Supporting person

`person-007` — 郗璿 — is the sole supporting person registered in unified
`data/people.json` and its WP1 projection. She is required to express the two explicit atomic edges
`郗鑒 → 郗璿` and `郗璿 ↔ 王羲之`; replacing them with a direct inferred
`郗鑒 ↔ 王羲之` edge would hide the source's family structure. Her identity is
attested by `evidence-011` in `06-yaliang-019`. Her registry record has
`scope_role: supporting`; the six original records have `scope_role: primary`.
No wider 郗氏 family tree is introduced.

## Candidate and unresolved relations

* No additional direct edge is created for `relation-001`; it is the single
  reviewed derived record described above.
* A direct relation between 謝安 and 王凝之 is not stored. It would require
  moving through 謝道韞's marriage and would be a transitive inference, not a
  directly cited R1 edge.
* A direct relation between 王導 and 王凝之 is not stored merely from the
  family path 王導 → 王羲之 → 王凝之.
* Other apparent relations among the six people remain unresolved unless a
  source passage states a hard kinship or marriage relation.

## Explicitly rejected shortcuts

R1 does not promote an edge from co-occurrence in one story or unit, a shared
surname, a shared office/title, the existence of a common annotation, or graph
transitivity. In particular, `CO-OCCURRENCE ≠ HISTORICAL RELATION`; these
signals may support a future candidate queue but cannot create a reviewed Gold
record. A direct historical edge, a deterministic derived relation, and a
co-occurrence signal remain distinct states:

```text
DIRECT HISTORICAL EDGE ≠ DERIVED RELATION ≠ CO-OCCURRENCE
```
