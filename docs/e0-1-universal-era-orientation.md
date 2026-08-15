# E0.1 — Universal Era Orientation

## Product rule

E0.1 makes the Era Card a universal reading entry. Every published Story has
one primary orientation card, while the card's precision follows the evidence:

1. ruler-reign when the Story has a safe Story-time ruler/reign coordinate;
2. broad-period when H0A/W3 evidence supports a useful historical window;
3. corpus-context when the surviving local evidence cannot narrow the Story
   without speculation.

The reader-facing idea remains: **帝王是时间的尺子**. A ruler is a useful
chronological coordinate, but a 纪元卡 is not an emperor biography and broad
cards are not disguised ruler cards.

## Two layers, one chronology

H0A's StoryTemporalAnchor remains the authoritative historical assertion. It
may be exact, bounded, phase-only, or unknown. E0.1's StoryEraOrientation is a
build-time product projection for navigation. An unknown H0A anchor may
therefore have a broad-period or corpus-context card. E0.1 never upgrades the
H0A precision field.

The projection reuses H0A HistoricalPhase, ReignPeriod, EraYear,
HistoricalEvent, and PersonActivityAnchor records. It does not create a
second chronology system.

## Person safety

Participant-derived orientation uses only current Scene Context rows with
scene_role == present, and requires the Person to be in the Story's safe
production Person set. Off-frame references, Liu-only biography subjects,
comparisons, ancestors, later outcomes, and quoted historical examples cannot
drive the primary card. A Person's presence can support a broad period; it
cannot establish an exact year or ruler merely because the Person is famous.

The universal orientation does not add rulers to the Person registry, change
PersonStory, create Relations, or alter Random Person eligibility.

## Ruler cards and tenure

The three current ruler-reign cards are 晋武帝, 晋元帝, and 晋明帝. Their
personal names come from local Jinshu 帝纪 evidence. Their actual tenure
coordinates come from the reviewed H0A ruler contexts, not from the subset of
era-name rows observed in the current Story corpus. The cards retain observed
ReignPeriod/EraYear references for the year-name strip.

Imperial titles remain collision-safe. A bare 武帝, 明帝, or another shared
title is not clickable unless Story-local evidence resolves its ruler. A
referenced ruler also cannot replace the Story-time primary orientation.

## Broad cards and chronology

The broad window set reuses the five H0A phase bands and adds only
Eastern-Jin early/late windows where current H0A event evidence justifies
them. Broad card content is derived from assigned current Stories,
scene-participant intersections, and relevant H0A events.

Event lists are always ordered from old to new by:

    start_year_ce, end_year_ce, event_id

Era-name segments use the same chronological discipline. Story lists use safe
H0A temporal order when available and otherwise stable canonical Story order;
chapter adjacency is never treated as historical sequence.

## Frontend behavior

The Story reader displays one small, secondary orientation link near the Story
title:

    晋明帝 · 太宁 ›
    东晋早期 ›
    世说时代 ›

Clicking it opens the existing Era side panel/drawer. Ruler mentions in the
text remain independently clickable only when safely resolved. Broad and
corpus cards lead back to current Stories and scene-derived Persons. The UI
does not expose phase_only, unknown, candidate, ruler_context_id, or other
internal ontology terms.

## Current result and limits

The current 83-Story scope produces 6 ruler-reign orientations, 33
broad-period orientations, and 44 corpus-context orientations. The remaining
H0A unknowns are intentionally not converted into dates. The corpus card is
an honest exploration fallback, not a historical claim.

E0.1 stops at universal orientation. It does not start H0A.2, H0B, P4, ES0,
or a global timeline.
