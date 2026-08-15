#!/usr/bin/env python3
"""Validate the E0 Era Card pilot and its static reading projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate(bundle: Mapping[str, Any] | None = None) -> list[str]:
    bundle = bundle or read("data/derived/sc1-site.json")
    coordinates = read("data/derived/h0a-temporal-coordinates.json")
    identities_doc = read("data/annotation/ruler-identities-e0.json")
    cards_doc = read("data/annotation/era-cards-e0.json")
    orientation_doc = read("data/derived/e0-story-era-orientations.json")
    audit_doc = read("data/derived/e0-ruler-mention-audit.json")
    projection = read("data/derived/e0-era-card-projection.json")
    errors: list[str] = []
    stories = [item for item in bundle.get("stories", []) if isinstance(item, Mapping)]
    story_ids = {str(item.get("id")) for item in stories}
    people = [item for item in bundle.get("people", []) if isinstance(item, Mapping)]
    person_ids = {str(item.get("id")) for item in people}
    relations = [item for item in bundle.get("relations", []) if isinstance(item, Mapping)]
    production_relations = read("data/annotation/wp1-relations.json").get("records", [])

    if len(stories) != len(story_ids): fail(errors, "Story IDs are not unique")
    if not people: fail(errors, "production Person registry is empty")
    if len(relations) != len(production_relations) or {item.get("id") for item in relations} != {item.get("id") for item in production_relations}:
        fail(errors, "E0 changed production Relations")
    if len(identities_doc.get("records", [])) != len({item.get("ruler_id") for item in identities_doc.get("records", [])}): fail(errors, "duplicate ruler IDs")
    ruler_ids = {str(item.get("ruler_id")) for item in identities_doc.get("records", []) if isinstance(item, Mapping)}
    if ruler_ids & person_ids: fail(errors, "ruler namespace overlaps Person namespace")
    cards = [item for item in cards_doc.get("records", []) if isinstance(item, Mapping)]
    card_ids = {str(item.get("era_card_id")) for item in cards}
    if len(cards) != len(card_ids): fail(errors, "duplicate Era Card IDs")
    if any(
        (item.get("card_kind") == "ruler_reign" and item.get("ruler_id") not in ruler_ids)
        or (item.get("card_kind") != "ruler_reign" and item.get("ruler_id") is not None)
        for item in cards
    ): fail(errors, "Era Card ruler namespace/reference is invalid")
    if projection.get("era_cards") != cards: fail(errors, "projection Era Cards differ from annotation artifact")
    if projection.get("ruler_identities") != identities_doc.get("records"): fail(errors, "projection ruler registry differs from annotation artifact")
    if projection.get("story_era_orientations") != orientation_doc.get("records"): fail(errors, "projection Story Era orientations differ from annotation artifact")
    audit = [item for item in audit_doc.get("records", []) if isinstance(item, Mapping)]
    if set(audit_doc.get("scope", {}).get("story_ids", [])) != story_ids:
        fail(errors, "ruler audit scope does not cover the current Story set")
    if any(item.get("story_id") not in story_ids for item in audit): fail(errors, "ruler audit references unknown Story")
    audit_by_id = {str(item.get("mention_id")): item for item in audit if isinstance(item.get("mention_id"), str)}
    if len(audit_by_id) != len(audit): fail(errors, "ruler audit Mention IDs are not unique")

    reigns = {str(item.get("reign_id")): item for item in coordinates.get("reign_periods", []) if isinstance(item, Mapping) and isinstance(item.get("reign_id"), str)}
    years = {str(item.get("era_year_id")): item for item in coordinates.get("era_years", []) if isinstance(item, Mapping) and isinstance(item.get("era_year_id"), str)}
    events = {str(item.get("event_id")): item for item in read("data/annotation/historical-events-h0a.json").get("records", []) if isinstance(item, Mapping) and isinstance(item.get("event_id"), str)}
    for identity in identities_doc.get("records", []):
        if not isinstance(identity, Mapping):
            fail(errors, "malformed ruler identity")
            continue
        for reign_id in identity.get("reign_period_ids", []):
            if reign_id not in reigns: fail(errors, f"ruler {identity.get('ruler_id')} references unknown reign {reign_id}")
        for year_id in identity.get("era_year_ids", []):
            if year_id not in years: fail(errors, f"ruler {identity.get('ruler_id')} references unknown era year {year_id}")

    card_by_id = {str(item.get("era_card_id")): item for item in cards}
    for card in cards:
        start, end = card.get("reign_start_year"), card.get("reign_end_year")
        if isinstance(start, int) and isinstance(end, int) and start > end: fail(errors, f"Era Card interval invalid: {card.get('era_card_id')}")
        if isinstance(card.get("start_year_ce"), int) and isinstance(card.get("end_year_ce"), int) and card["start_year_ce"] > card["end_year_ce"]:
            fail(errors, f"Era Card orientation interval invalid: {card.get('era_card_id')}")
        previous_start = None
        for era_name in card.get("era_names", []):
            current_start = era_name.get("start_year_ce") if isinstance(era_name, Mapping) else None
            if isinstance(previous_start, int) and isinstance(current_start, int) and current_start < previous_start:
                fail(errors, f"Era Card era-name order invalid: {card.get('era_card_id')}")
            if isinstance(current_start, int):
                previous_start = current_start
        for event_id in card.get("historical_event_ids", []):
            event = events.get(str(event_id))
            if event is None:
                fail(errors, f"Era Card references unknown event: {event_id}")
                continue
            if all(isinstance(value, int) for value in (start, end, event.get("start_year_ce"), event.get("end_year_ce"))):
                if event["end_year_ce"] < start or event["start_year_ce"] > end:
                    fail(errors, f"event does not intersect Era Card: {card.get('era_card_id')} / {event_id}")
            if not event.get("linked_story_ids"):
                fail(errors, f"Era Card event is outside current Story scope: {event_id}")
        primary_links = [link for link in card.get("ruler_story_links", []) if isinstance(link, Mapping)]
        for link in primary_links:
            if link.get("story_id") not in story_ids:
                fail(errors, f"Era Card Story link is invalid: {link}")
            if link.get("link_type") not in {"appears", "referenced", "reign_context"}:
                fail(errors, f"invalid Era Card Story link type: {link.get('link_type')}")
        for intersection in card.get("person_intersections", []):
            if not isinstance(intersection, Mapping) or intersection.get("person_id") not in person_ids:
                fail(errors, f"invalid Era Card Person intersection: {intersection}")
            if not isinstance(intersection, Mapping): continue
            if intersection.get("story_count") != len(intersection.get("story_ids", [])):
                fail(errors, f"Era Card Person intersection count mismatch: {intersection}")
            for story_id in intersection.get("story_ids", []):
                story = next((item for item in stories if item.get("id") == story_id), None)
                if not story or intersection.get("person_id") not in story.get("person_ids", []):
                    fail(errors, f"Era Card Person intersection is not story-derived: {intersection}")

    orientations = [item for item in orientation_doc.get("records", []) if isinstance(item, Mapping)]
    orientation_by_story = {str(item.get("story_id")): item for item in orientations}
    if set(orientation_doc.get("scope", {}).get("story_ids", [])) != story_ids:
        fail(errors, "E0.1 orientation scope does not cover the current Story set")
    if len(orientations) != len(orientation_by_story) or set(orientation_by_story) != story_ids:
        fail(errors, "E0.1 primary Era orientation does not cover each Story exactly once")
    bundle_orientations = bundle.get("story_era_orientations", [])
    if bundle_orientations != orientations:
        fail(errors, "bundle Story Era orientations differ from E0.1 artifact")
    for story in stories:
        story_id = str(story.get("id"))
        orientation = orientation_by_story.get(story_id)
        if not isinstance(story.get("primary_era_card_id"), str) or not isinstance(orientation, Mapping) or story.get("primary_era_card_id") != orientation.get("primary_era_card_id"):
            fail(errors, f"Story has invalid primary Era Card: {story_id}")
        card = card_by_id.get(str(orientation.get("primary_era_card_id"))) if isinstance(orientation, Mapping) else None
        if not isinstance(card, Mapping) or card.get("card_kind") != orientation.get("card_kind"):
            fail(errors, f"Story primary Era Card kind mismatch: {story_id}")
        if isinstance(orientation, Mapping) and orientation.get("h0a_precision") == "unknown" and orientation.get("orientation_basis") != "direct_ruler":
            # E0.1 is a reader projection; it must not silently rewrite H0A.
            anchor_id = orientation.get("h0a_anchor_id")
            if not isinstance(anchor_id, str):
                fail(errors, f"Story orientation lost its H0A anchor reference: {story_id}")
        if isinstance(card, Mapping) and story_id not in card.get("story_ids", []):
            fail(errors, f"Story primary Era Card does not list its Story: {story_id}")

    projected_mentions = [item for item in projection.get("ruler_mentions", []) if isinstance(item, Mapping)]
    if {item.get("mention_id") for item in projected_mentions} != {item.get("mention_id") for item in bundle.get("ruler_mentions", [])}:
        fail(errors, "bundle ruler mention projection differs from E0 projection")
    placed: dict[str, int] = {str(item.get("mention_id")): 0 for item in projected_mentions}
    for story in stories:
        reading = story.get("reading", {})
        segments = []
        if isinstance(reading, Mapping):
            main = reading.get("main_text", {})
            if isinstance(main, Mapping): segments.extend(main.get("segments", []))
            for annotation in reading.get("annotations", []):
                if isinstance(annotation, Mapping): segments.extend(annotation.get("segments", []))
        for segment in segments:
            if isinstance(segment, Mapping) and segment.get("type") == "ruler_mention":
                mention_id = str(segment.get("mention_id"))
                if mention_id not in placed: fail(errors, f"unknown ruler segment {mention_id}")
                else: placed[mention_id] += 1
    for mention_id, count in placed.items():
        if count != 1: fail(errors, f"ruler Mention {mention_id} projected {count} times")
    for item in projected_mentions:
        if item.get("resolution_status") != "resolved" or item.get("ruler_id") not in ruler_ids or item.get("era_card_id") not in card_ids:
            fail(errors, f"clickable ruler Mention is not fully resolved: {item.get('mention_id')}")
        story = next((candidate for candidate in stories if candidate.get("id") == item.get("story_id")), None)
        if story is None: continue
        section = item.get("section")
        if section == "main_text":
            text = str(story.get("text", ""))
        else:
            annotation = next((candidate for candidate in story.get("annotations", []) if isinstance(candidate, Mapping) and candidate.get("id") == item.get("annotation_id")), None)
            text = str(annotation.get("text", "")) if annotation else ""
        offset = item.get("anchor", {}).get("offset") if isinstance(item.get("anchor"), Mapping) else None
        surface = item.get("surface")
        if not isinstance(offset, int) or not isinstance(surface, str) or text[offset:offset + len(surface)] != surface:
            fail(errors, f"ruler Mention source anchor mismatch: {item.get('mention_id')}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("E0 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
