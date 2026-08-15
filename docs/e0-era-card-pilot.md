# E0 — 纪元卡 / Era Card Pilot

E0 adds a small, static reading projection on top of H0A. Its reader-facing
idea is simple: **帝王是时间的尺子**. A 纪元卡 uses a ruler's reign window to
help a reader locate a Story, then return to related Stories and Persons.

## Separate namespace

纪元卡 is not a Person Card. Rulers in this pilot live in the `ruler_id`
namespace and are never added to `data/people`, PersonStory, Random Person, or
the reviewed Relation graph. The card unit is ruler + reign window; multiple
era names remain one card.

The first evidence-backed pilot cards are:

- 晋武帝 — 265–289, 泰始 / 太康
- 晋元帝 — 317–322, 建武 / 大兴 / 永昌
- 晋明帝 — 323–326, 太宁

The set is deliberately small. H0A directly reviewed Story-local ruler
contexts for these three rulers. Other surfaces such as bare `文帝`, `武帝`,
`明帝`, `高贵乡公`, `宣王`, and `文王` remain in
`data/derived/e0-ruler-mention-audit.json`; a string match alone does not make
them clickable.

## Story link semantics

Each card keeps three non-equivalent link types:

- `appears`: the ruler acts, speaks, receives, asks, or is directly involved
  in the Story action.
- `referenced`: the ruler is named or recalled, but the Story is not thereby
  dated to that ruler's reign.
- `reign_context`: H0A places the Story inside the reviewed reign window;
  the ruler need not be named in the Story.

The UI presents these as 《世说》中的他, 被提及, and 这一时期. Person
intersections are derived from `appears` Stories and do not create Relations.
Historical events are reused from H0A only when their interval intersects a
card and the event already matters to the current Story scope.

## Projection and navigation

Ruler mentions are a distinct `ruler_mention` reading segment. They are not
encoded as Person mentions. A reviewed segment opens the card in the existing
desktop side panel / mobile drawer. The exploration stack supports

    Story → Era → Story
    Story → Era → Person → Story

Person navigation, Random Person, Random Story, and the canonical source
projection remain unchanged. Era cards are static build-time data; no runtime
search, network, AI, or second chronology system is introduced.

## Provenance and limits

Ruler identity and reign coordinates reference H0A `ruler_context`,
`ReignPeriod`, and `EraYear` evidence. Card prose is short inferred editorial
context with candidate review status. The pilot does not add personal names
when the current local evidence projection does not expose a safe source
coordinate for that field.

The audit is intentionally broader than the card set. It records unresolved
and ambiguous imperial titles, including the shared-title collision cases.
Future work may review those records, but E0 does not promote them, add
rulers as Persons, build a dynasty timeline, or begin H0B/P4/ES0.
