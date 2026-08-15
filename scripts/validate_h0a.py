#!/usr/bin/env python3
"""Validate H0A temporal artifacts and their static Story projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "data/derived/sc1-site.json"
COORDINATES_PATH = ROOT / "data/derived/h0a-temporal-coordinates.json"
EVIDENCE_PATH = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
EVENTS_PATH = ROOT / "data/annotation/historical-events-h0a.json"
ACTIVITY_PATH = ROOT / "data/annotation/person-activity-anchors-h0a.json"
ANCHORS_PATH = ROOT / "data/annotation/story-temporal-anchors-h0a.json"
GAP_PATH = ROOT / "data/derived/h0a-temporal-gap-audit.json"
METRICS_PATH = ROOT / "data/derived/h0a-metrics.json"
H0A1_BASELINE_PATH = ROOT / "data/derived/h0a1-baseline.json"
ZTJ_INDEX_PATH = ROOT / "data/derived/ztj0-chronology-index.json"
SGZ_PATH = ROOT / "data/derived/sgz0-processed-corpus.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    bundle = read_json(BUNDLE_PATH)
    coordinates = read_json(COORDINATES_PATH)
    evidence_doc = read_json(EVIDENCE_PATH)
    events_doc = read_json(EVENTS_PATH)
    activity_doc = read_json(ACTIVITY_PATH)
    anchors_doc = read_json(ANCHORS_PATH)
    gap = read_json(GAP_PATH)
    metrics = read_json(METRICS_PATH)
    baseline = read_json(H0A1_BASELINE_PATH)
    ztj = read_json(ZTJ_INDEX_PATH)
    sgz = read_json(SGZ_PATH)

    stories = [item for item in bundle.get("stories", []) if isinstance(item, Mapping)]
    story_by_id = {str(item.get("id")): item for item in stories}
    story_ids = set(story_by_id)
    people_ids = {str(item.get("id")) for item in bundle.get("people", []) if isinstance(item, Mapping)}
    evidence_ids = {str(item.get("id")) for item in bundle.get("evidence", []) if isinstance(item, Mapping)}
    source_ids = {str(item.get("id")) for item in bundle.get("sources", []) if isinstance(item, Mapping)}

    phases = coordinates.get("phases", [])
    phase_ids = {str(item.get("phase_id")) for item in phases if isinstance(item, Mapping)}
    if phase_ids != {"phase-1", "phase-2", "phase-3", "phase-4", "phase-5"}:
        errors.append("H0A phases do not reuse the five stable W3/C0 phase IDs")
    for phase in phases:
        if not isinstance(phase, Mapping):
            errors.append("invalid phase record")
            continue
        if phase.get("approximate_start_year") > phase.get("approximate_end_year"):
            errors.append(f"phase interval invalid: {phase.get('phase_id')}")

    ztj_block_ids = {str(item.get("block_id")) for item in ztj.get("records", []) if isinstance(item, Mapping)}
    reign_ids = {str(item.get("reign_id")) for item in coordinates.get("reign_periods", []) if isinstance(item, Mapping)}
    era_year_ids = {str(item.get("era_year_id")) for item in coordinates.get("era_years", []) if isinstance(item, Mapping)}
    ruler_context_ids = {str(item.get("ruler_context_id")) for item in coordinates.get("ruler_contexts", []) if isinstance(item, Mapping)}
    for ruler_context in coordinates.get("ruler_contexts", []):
        if not isinstance(ruler_context, Mapping):
            errors.append("invalid ruler context record")
            continue
        if ruler_context.get("start_year_ce") is None or ruler_context.get("end_year_ce") is None or ruler_context["start_year_ce"] > ruler_context["end_year_ce"]:
            errors.append(f"Ruler context interval invalid: {ruler_context.get('ruler_context_id')}")
        if any(str(item) not in reign_ids for item in ruler_context.get("reign_ids", [])):
            errors.append(f"Ruler context ReignPeriod missing: {ruler_context.get('ruler_context_id')}")
    for reign in coordinates.get("reign_periods", []):
        if not isinstance(reign, Mapping):
            errors.append("invalid ReignPeriod record")
            continue
        if reign.get("start_year_ce") is not None and reign.get("end_year_ce") is not None and reign["start_year_ce"] > reign["end_year_ce"]:
            errors.append(f"ReignPeriod interval invalid: {reign.get('reign_id')}")
        for ref in reign.get("evidence_refs", []):
            if str(ref.get("block_id")) not in ztj_block_ids:
                errors.append(f"ReignPeriod source block missing: {ref.get('block_id')}")
    for era_year in coordinates.get("era_years", []):
        if not isinstance(era_year, Mapping):
            errors.append("invalid EraYear record")
            continue
        if str(era_year.get("reign_id")) not in reign_ids:
            errors.append(f"EraYear ReignPeriod missing: {era_year.get('era_year_id')}")
        if era_year.get("year_ce") is not None and not isinstance(era_year.get("year_ce"), int):
            errors.append(f"EraYear year_ce invalid: {era_year.get('era_year_id')}")

    evidence_records = evidence_doc.get("records", [])
    temporal_evidence_ids = {str(item.get("evidence_record_id")) for item in evidence_records if isinstance(item, Mapping)}
    for record in evidence_records:
        if not isinstance(record, Mapping):
            errors.append("invalid TemporalEvidence record")
            continue
        story_id = str(record.get("story_id"))
        if story_id not in story_ids:
            errors.append(f"TemporalEvidence Story missing: {story_id}")
            continue
        source_span = record.get("source_span", {})
        section = str(source_span.get("section"))
        if section == "main_text":
            source_text = str(story_by_id[story_id].get("text", ""))
        elif section == "liu_annotation":
            annotation_id = source_span.get("annotation_id")
            annotation = next((item for item in story_by_id[story_id].get("annotations", []) if isinstance(item, Mapping) and item.get("id") == annotation_id), None)
            source_text = str(annotation.get("text", "")) if annotation else ""
            if annotation is None:
                errors.append(f"TemporalEvidence annotation missing: {record.get('evidence_record_id')}")
        else:
            errors.append(f"TemporalEvidence section invalid: {record.get('evidence_record_id')}")
            continue
        start = source_span.get("char_start")
        end = source_span.get("char_end_exclusive")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start or end > len(source_text):
            errors.append(f"TemporalEvidence source span invalid: {record.get('evidence_record_id')}")
        if record.get("source_evidence_ids") and any(str(item) not in evidence_ids for item in record.get("source_evidence_ids", [])):
            errors.append(f"TemporalEvidence source Evidence missing: {record.get('evidence_record_id')}")
        constraint = record.get("temporal_constraint")
        if constraint is not None:
            if not isinstance(constraint, Mapping):
                errors.append(f"TemporalEvidence constraint invalid: {record.get('evidence_record_id')}")
            else:
                start_constraint = constraint.get("start_year_ce")
                end_constraint = constraint.get("end_year_ce")
                if start_constraint is None or end_constraint is None or start_constraint > end_constraint:
                    errors.append(f"TemporalEvidence constraint interval invalid: {record.get('evidence_record_id')}")
                if constraint.get("applicability") not in {"direct_story_time", "event_context"}:
                    errors.append(f"TemporalEvidence non-binding constraint promoted: {record.get('evidence_record_id')}")
        candidate = record.get("normalized_candidate")
        if isinstance(candidate, Mapping) and candidate.get("ruler_context_id") is not None and str(candidate.get("ruler_context_id")) not in ruler_context_ids:
            errors.append(f"TemporalEvidence ruler context missing: {record.get('evidence_record_id')}")
        if record.get("relation_to_story") == "quoted_ancient_precedent" and record.get("evidence_type") in {"reign_reference", "era_year"}:
            if record.get("relation_to_story") == "direct_story_time":
                errors.append(f"quoted precedent incorrectly binds Story time: {record.get('evidence_record_id')}")

    event_records = events_doc.get("records", [])
    event_ids = {str(item.get("event_id")) for item in event_records if isinstance(item, Mapping)}
    for event in event_records:
        if not isinstance(event, Mapping):
            errors.append("invalid HistoricalEvent record")
            continue
        if event.get("start_year_ce") is not None and event.get("end_year_ce") is not None and event["start_year_ce"] > event["end_year_ce"]:
            errors.append(f"HistoricalEvent interval invalid: {event.get('event_id')}")
        if any(str(item) not in temporal_evidence_ids for item in event.get("evidence_ids", [])):
            errors.append(f"HistoricalEvent evidence missing: {event.get('event_id')}")
        if any(str(item) not in story_ids for item in event.get("linked_story_ids", [])):
            errors.append(f"HistoricalEvent Story link missing: {event.get('event_id')}")
        if "production_relation_id" in event:
            errors.append(f"HistoricalEvent illegally contains production relation: {event.get('event_id')}")

    activity_ids = {str(item.get("anchor_id")) for item in activity_doc.get("records", []) if isinstance(item, Mapping)}
    for activity in activity_doc.get("records", []):
        if not isinstance(activity, Mapping):
            errors.append("invalid PersonActivityAnchor record")
            continue
        if str(activity.get("person_id")) not in people_ids:
            errors.append(f"PersonActivityAnchor Person missing: {activity.get('anchor_id')}")
        if str(activity.get("event_id")) not in event_ids:
            errors.append(f"PersonActivityAnchor Event missing: {activity.get('anchor_id')}")
        if any(str(item) not in temporal_evidence_ids for item in activity.get("evidence_ids", [])):
            errors.append(f"PersonActivityAnchor evidence missing: {activity.get('anchor_id')}")

    anchor_records = anchors_doc.get("records", [])
    anchors_by_story = {str(item.get("story_id")): item for item in anchor_records if isinstance(item, Mapping)}
    if set(anchors_by_story) != story_ids or len(anchor_records) != len(story_ids):
        errors.append("H0A must contain exactly one StoryTemporalAnchor for every current published Story")
    for anchor in anchor_records:
        if not isinstance(anchor, Mapping):
            errors.append("invalid StoryTemporalAnchor record")
            continue
        story_id = str(anchor.get("story_id"))
        if any(str(item) not in temporal_evidence_ids for item in anchor.get("evidence_ids", [])):
            errors.append(f"StoryTemporalAnchor evidence missing: {story_id}")
        if any(str(item) not in event_ids for item in anchor.get("event_ids", [])):
            errors.append(f"StoryTemporalAnchor Event missing: {story_id}")
        if any(str(item) not in activity_ids for item in anchor.get("supporting_activity_anchor_ids", [])):
            errors.append(f"StoryTemporalAnchor activity anchor missing: {story_id}")
        if anchor.get("phase_id") is not None and str(anchor.get("phase_id")) not in phase_ids:
            errors.append(f"StoryTemporalAnchor phase missing: {story_id}")
        if anchor.get("reign_id") is not None and str(anchor.get("reign_id")) not in reign_ids:
            errors.append(f"StoryTemporalAnchor ReignPeriod missing: {story_id}")
        if anchor.get("ruler_context_id") is not None and str(anchor.get("ruler_context_id")) not in ruler_context_ids:
            errors.append(f"StoryTemporalAnchor ruler context missing: {story_id}")
        if any(str(item) not in era_year_ids for item in anchor.get("era_year_ids", [])):
            errors.append(f"StoryTemporalAnchor EraYear missing: {story_id}")
        start = anchor.get("start_year_ce")
        end = anchor.get("end_year_ce")
        if start is not None and end is not None and start > end:
            errors.append(f"StoryTemporalAnchor interval invalid: {story_id}")
        precision = str(anchor.get("precision"))
        if precision == "event_bounded" and not anchor.get("event_ids"):
            errors.append(f"event_bounded Story lacks HistoricalEvent: {story_id}")
        if precision == "reign_bounded":
            if anchor.get("reign_id") is None and anchor.get("ruler_context_id") is None:
                errors.append(f"reign_bounded Story lacks ReignPeriod or ruler context: {story_id}")
            if not isinstance(start, int) or not isinstance(end, int):
                errors.append(f"reign_bounded Story lacks bounded interval: {story_id}")
            direct_reign_records = [
                item for item in evidence_records
                if isinstance(item, Mapping)
                and item.get("story_id") == story_id
                and item.get("evidence_type") == "reign_reference"
                and item.get("relation_to_story") == "direct_story_time"
            ]
            if not direct_reign_records:
                errors.append(f"reign_bounded Story lacks direct local reign evidence: {story_id}")
        if precision == "phase_only" and (start is not None or end is not None):
            errors.append(f"phase_only Story has invented year bounds: {story_id}")
        if precision == "year_range":
            if not isinstance(start, int) or not isinstance(end, int) or start == end:
                errors.append(f"year_range Story lacks a genuine interval: {story_id}")
            if len(anchor.get("temporal_constraint_evidence_ids", [])) < 2:
                errors.append(f"year_range Story lacks intersected constraints: {story_id}")
        if precision == "exact_year":
            if not isinstance(start, int) or start != end or not anchor.get("era_year_ids"):
                errors.append(f"exact_year Story lacks deterministic EraYear: {story_id}")
            direct_records = [
                item for item in evidence_records
                if isinstance(item, Mapping)
                and item.get("story_id") == story_id
                and item.get("evidence_type") == "era_year"
                and item.get("relation_to_story") == "direct_story_time"
            ]
            if not direct_records:
                errors.append(f"exact_year Story lacks direct local era evidence: {story_id}")
        projection = anchor.get("reader_projection", {})
        label = projection.get("label_zh") if isinstance(projection, Mapping) else None
        if label and any(token in str(label) for token in ("未詳", "未详", "unknown", "phase-", "event-bounded", "candidate", "review_status")):
            errors.append(f"reader temporal label exposes internal/unknown wording: {story_id}")

    for story_id, story in story_by_id.items():
        anchor = anchors_by_story.get(story_id)
        if not anchor:
            continue
        projection = anchor.get("reader_projection", {})
        should_show = bool(projection.get("show")) if isinstance(projection, Mapping) else False
        if should_show:
            if story.get("temporal_anchor_id") != anchor.get("anchor_id") or not isinstance(story.get("temporal_orientation"), Mapping):
                errors.append(f"frontend temporal projection missing: {story_id}")
        elif "temporal_orientation" in story:
            errors.append(f"unknown Story must not project a temporal label: {story_id}")

    baseline_story_ids = {str(item.get("story_id")) for item in baseline.get("records", []) if isinstance(item, Mapping)}
    # H0A.1 froze the pre-W4 83-Story audit.  W4 adds new anchors but does
    # not retroactively mutate that baseline; require the frozen set to remain
    # present as a subset of the enlarged current scope.
    if not baseline_story_ids <= story_ids:
        errors.append("H0A.1 baseline Story set is not contained in current production Story set")
    baseline_by_story = {str(item.get("story_id")): item for item in baseline.get("records", []) if isinstance(item, Mapping)}
    for upgrade in metrics.get("h0a1", {}).get("upgrades", []):
        story_id = str(upgrade.get("story_id"))
        if baseline_by_story.get(story_id, {}).get("precision") != "unknown":
            errors.append(f"H0A.1 upgrade did not start from unknown: {story_id}")
        if not upgrade.get("evidence_ids"):
            errors.append(f"H0A.1 upgrade lacks evidence: {story_id}")
        if upgrade.get("to") == "phase_only" and upgrade.get("resolution_basis") == "w3_frozen_phase_orientation":
            errors.append(f"H0A.1 phase upgrade is W3-only: {story_id}")
    if metrics.get("h0a1", {}).get("unknown_to_still_unknown") != len(gap.get("unknown_story_ids", [])):
        errors.append("H0A.1 unknown count does not match gap audit")

    if len(sgz.get("records", [])) == 0 or int(sgz.get("main_text_unit_count", 0)) <= 0 or int(sgz.get("pei_annotation_unit_count", 0)) <= 0:
        errors.append("SGZ0 Chen Shou / Pei Songzhi layers are not present")
    ztj_primary = read_json(ROOT / "data/derived/ztj0-processed-corpus.json").get("primary", {})
    if int(ztj_primary.get("volume_count", 0)) != 294 or int(ztj_primary.get("hu_annotation_unit_count", 0)) <= 0:
        errors.append("ZTJ0 primary/Hu layers are not present")
    if gap.get("unknown_story_ids") != [row["story_id"] for row in gap.get("records", []) if row.get("precision") == "unknown"]:
        errors.append("H0A gap audit unknown list is not deterministic")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("H0A validation passed (" + args.mode + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
