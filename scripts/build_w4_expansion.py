#!/usr/bin/env python3
"""Freeze the W4 story-first structural/temporal expansion inputs.

W4 is intentionally a separate wave.  The older M2/W3 manifests remain
immutable; this builder only audits the remaining canonical entries and
freezes a deterministic story and Person selection for the new wave.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

try:
    from .build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
    from .build_sc1_frontend_data import publication_state
except ImportError:  # direct execution
    from build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
    from build_sc1_frontend_data import publication_state


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data/shishuo-corpus-index.json"
PUNCTUATION_PATH = ROOT / "data/annotation/wp1-punctuation.json"
SC1_PATH = ROOT / "data/derived/sc1-site.json"
EFFECTIVE_PATH = ROOT / "data/derived/person-resolution-effective.json"
PEOPLE_PATH = ROOT / "data/people.json"
PERSON_CANDIDATES_PATH = ROOT / "data/derived/person-identity-candidates.json"
PERSON_OCCURRENCES_PATH = ROOT / "data/derived/person-candidate-occurrences.json"
PERSON_RANKING_PATH = ROOT / "data/derived/m2-person-expansion-ranking.json"
STORY_RANKING_PATH = ROOT / "data/derived/m2-story-expansion-ranking.json"
GOLD_PATH = ROOT / "data/story-chain-gold-set.json"
WAVE1_PATH = ROOT / "data/annotation/story-expansion-wave-1.json"
WAVE3_PATH = ROOT / "data/annotation/story-expansion-wave-3.json"
H0B_READINESS_PATH = ROOT / "data/derived/h0b0-w4-readiness.json"
H0B_GAPS_PATH = ROOT / "data/derived/h0b0-structural-gap-audit.json"

STORY_AUDIT_PATH = ROOT / "data/derived/w4-story-candidate-audit.json"
STORY_SELECTION_PATH = ROOT / "data/annotation/story-expansion-wave-4.json"
PERSON_RANKING_OUT_PATH = ROOT / "data/derived/w4-person-expansion-ranking.json"
PERSON_SELECTION_PATH = ROOT / "data/annotation/person-expansion-wave-4.json"

TARGET_STORY_COUNT = 60
TARGET_PERSON_COUNT = 25

TEMPORAL_TERMS = (
    "年", "帝", "王敦", "蘇峻", "苏峻", "永嘉", "過江", "过江", "南渡",
    "遭亂", "遭乱", "即位", "登阼", "在位", "亂", "乱", "咸和", "太寧",
    "太宁", "元帝", "明帝", "成帝", "武帝", "惠帝", "正始", "泰始",
)
STRUCTURAL_TERMS = (
    "父", "子", "兄", "弟", "姊", "妹", "夫", "妻", "婚", "嫁", "娶",
    "女", "婿", "家", "族", "氏", "丞相", "太傅", "太尉", "大司馬", "大司马",
    "右軍", "右军", "將軍", "将军", "刺史", "尚書", "尚书", "參軍", "参军",
)
EVENT_TERMS = ("王敦", "蘇峻", "苏峻", "八王", "永嘉", "淝水", "北伐", "過江", "过江", "南渡")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, *values: object) -> str:
    material = "|".join(str(value) for value in values)
    return f"{prefix}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def sections(path: Path) -> tuple[dict[str, Any], str, str]:
    text = path.read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    main = ""
    annotations: list[str] = []
    for section, body, _section_metadata in parse_shishuo_sections(text):
        if section == "main_text":
            main = body.rstrip("\n")
        elif section == "liu_annotation":
            annotations.append(body.rstrip("\n"))
    return metadata, main, "\n".join(annotations)


def current_story_ids() -> set[str]:
    bundle = read(SC1_PATH)
    return {
        str(item["id"])
        for item in bundle.get("stories", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }


def frozen_w4_story_ids() -> set[str]:
    path = ROOT / "data/annotation/story-expansion-wave-4.json"
    if not path.is_file():
        return set()
    document = read(path)
    if document.get("selection_status") != "frozen":
        return set()
    return {
        str(item["story_id"])
        for item in document.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
    }


def existing_person_ids() -> set[str]:
    return {
        str(item["person_id"])
        for item in read(PEOPLE_PATH).get("people", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }


def materialized_candidate_ids() -> set[str]:
    result: set[str] = set()
    for path in (
        ROOT / "data/annotation/person-expansion-wave-1.json",
        ROOT / "data/annotation/person-expansion-wave-2.json",
        ROOT / "data/annotation/person-expansion-wave-3.json",
    ):
        if not path.is_file():
            continue
        result.update(
            str(item["candidate_id"])
            for item in read(path).get("members", [])
            if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
        )
    return result


def unambiguous_exact_candidate_ids() -> set[str]:
    """Return candidates with at least one safe exact source coordinate.

    Candidate occurrence extraction is deliberately conservative: a source
    annotation block can give several identities the same coarse offset.
    Such a candidate may remain a valid historical identity, but it must not
    be promoted to a production Person if every exact occurrence is covered
    by that collision.  W4 therefore requires one coordinate whose exact
    candidate set is unambiguous; the materializer's finer span guard remains
    the final publication gate.
    """

    grouped: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for occurrence in read(PERSON_OCCURRENCES_PATH).get("occurrences", []):
        if not isinstance(occurrence, Mapping):
            continue
        candidate_id = occurrence.get("candidate_id")
        source_id = occurrence.get("source_id")
        section = occurrence.get("section")
        offset = occurrence.get("offset")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(source_id, str)
            or not isinstance(section, str)
            or not isinstance(offset, int)
            or occurrence.get("association_mode") != "exact"
        ):
            continue
        grouped[(source_id, section, offset)].add(candidate_id)
    return {
        candidate_id
        for candidate_ids in grouped.values()
        if len(candidate_ids) == 1
        for candidate_id in candidate_ids
    }


def parse_current_mentions() -> dict[str, dict[str, set[str]]]:
    result: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"main_text": set(), "liu_annotation": set()})
    document = read(EFFECTIVE_PATH)
    mention_rows = [
        *document.get("mentions", []),
        *document.get("derived_mentions", []),
    ]
    for mention in mention_rows:
        if not isinstance(mention, Mapping):
            continue
        story_id = mention.get("entry_id") or mention.get("source_id")
        person_id = mention.get("person_id")
        if isinstance(story_id, str) and isinstance(person_id, str):
            result[story_id].setdefault(str(mention.get("section", "main_text")), set()).add(person_id)
    return result


def candidate_occurrences() -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for occurrence in read(PERSON_OCCURRENCES_PATH).get("occurrences", []):
        if isinstance(occurrence, Mapping) and isinstance(occurrence.get("source_id"), str):
            result[str(occurrence["source_id"])].append(occurrence)
    return result


def story_score(row: Mapping[str, Any], *, chapter_seen: int, story_text: str) -> tuple[float, dict[str, float]]:
    main_people = len(set(row.get("current_main_person_ids", [])))
    annotation_people = len(set(row.get("materialized_person_ids", [])) - set(row.get("current_main_person_ids", [])))
    candidate_people = len(set(row.get("selected_wave_person_ids", [])))
    m2_score = float(row.get("score", 0.0))
    components = row.get("components", {}) if isinstance(row.get("components"), Mapping) else {}
    bridge = float(components.get("multi_person_bridge_value", 0.0))
    narrative = min(5.0, max(0.0, m2_score / 15.0))
    structure_hits = sum(1 for term in STRUCTURAL_TERMS if term in story_text)
    temporal_hits = sum(1 for term in TEMPORAL_TERMS if term in story_text)
    event_hits = sum(1 for term in EVENT_TERMS if term in story_text)
    identity_risk = 0.0
    if not main_people and not candidate_people:
        identity_risk += 1.5
    if row.get("flags", {}).get("liu_only_person_path"):
        identity_risk += 1.0
    isolation = 2.0 if main_people == 0 and candidate_people == 0 else 0.0
    diversity = 1.5 if chapter_seen == 0 else 0.0
    values = {
        "existing_person_connection_value": main_people * 4.0 + annotation_people * 0.5,
        "bridge_person_value": candidate_people * 2.5 + bridge * 2.0,
        "structural_value": min(6.0, structure_hits * 0.6),
        "temporal_constraint_value": min(6.0, temporal_hits * 0.7 + event_hits * 1.2),
        "era_coverage_value": diversity,
        "narrative_value": narrative,
        "identity_ambiguity_risk": identity_risk,
        "isolated_story_penalty": isolation,
    }
    score = (
        values["existing_person_connection_value"]
        + values["bridge_person_value"]
        + values["structural_value"]
        + values["temporal_constraint_value"]
        + values["era_coverage_value"]
        + values["narrative_value"]
        - 2.0 * values["identity_ambiguity_risk"]
        - 2.0 * values["isolated_story_penalty"]
    )
    return round(score, 6), {key: round(value, 6) for key, value in values.items()}


def build_story_audit() -> tuple[list[dict[str, Any]], list[str]]:
    corpus = read(CORPUS_PATH).get("entries", [])
    punctuation = {str(item["entry_id"]): item for item in read(PUNCTUATION_PATH).get("records", []) if isinstance(item, Mapping)}
    ranking = {str(item["story_id"]): item for item in read(STORY_RANKING_PATH).get("stories", []) if isinstance(item, Mapping)}
    current = current_story_ids() - frozen_w4_story_ids()
    current_mentions = parse_current_mentions()
    occurrences = candidate_occurrences()
    candidates = {str(item["candidate_id"]): item for item in read(PERSON_CANDIDATES_PATH).get("candidates", []) if isinstance(item, Mapping)}
    audit: list[dict[str, Any]] = []
    chapter_counts: Counter[str] = Counter()
    candidates_by_story: dict[str, set[str]] = defaultdict(set)
    for story_id, rows in occurrences.items():
        for row in rows:
            candidate = candidates.get(str(row.get("candidate_id")), {})
            if candidate.get("status") == "strong_candidate" and candidate.get("materialization_state") == "new_candidate":
                candidates_by_story[story_id].add(str(row.get("candidate_id")))
    for entry in corpus:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("id"), str):
            continue
        story_id = str(entry["id"])
        if story_id in current:
            continue
        path = ROOT / str(entry.get("path", ""))
        punctuation_record = punctuation.get(story_id)
        if not path.is_file() or punctuation_record is None:
            continue
        metadata, main, annotation = sections(path)
        state = publication_state(punctuation_record, main)
        rank_row = ranking.get(story_id, {})
        current_row = current_mentions.get(story_id, {})
        current_main = sorted(current_row.get("main_text", set()))
        current_annotation = sorted(current_row.get("liu_annotation", set()) - set(current_main))
        candidate_ids = sorted(candidates_by_story.get(story_id, set()))
        candidate_names = sorted({str(candidates[cid].get("preferred_name")) for cid in candidate_ids if cid in candidates})
        story_text = main + annotation
        chapter = str(metadata.get("chapter_id", story_id.split("-", 1)[0]))
        score, components = story_score(rank_row, chapter_seen=chapter_counts[chapter], story_text=story_text)
        if state != "blocked":
            chapter_counts[chapter] += 1
        audit.append(
            {
                "story_id": story_id,
                "chapter": chapter,
                "global_ordinal": int(entry.get("global_ordinal", 10**9)),
                "title": str(metadata.get("chapter_heading", "")),
                "publication_state": state,
                "canonical_entry_path": str(entry.get("path", "")),
                "canonical_entry_sha256": sha256_file(path),
                "main_text_length": len(main),
                "existing_production_person_ids": current_main,
                "annotation_only_production_person_ids": current_annotation,
                "strong_identity_candidate_ids": candidate_ids,
                "strong_identity_candidate_names": candidate_names,
                "h0b_structural_signals": sorted(term for term in STRUCTURAL_TERMS if term in story_text),
                "temporal_signals": sorted(term for term in TEMPORAL_TERMS if term in story_text),
                "event_signals": sorted(term for term in EVENT_TERMS if term in story_text),
                "score": score,
                "score_components": components,
                "eligible": state in {"production_ready", "preview_ready"},
                "identity_ambiguity_risk": components["identity_ambiguity_risk"],
                "isolation_risk": components["isolated_story_penalty"],
            }
        )
    audit.sort(key=lambda item: (item["global_ordinal"], item["story_id"]))
    return audit, sorted(current)


def select_stories(audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [item for item in audit if item.get("eligible")]
    selected: list[dict[str, Any]] = []
    chapters: Counter[str] = Counter()
    for item in sorted(eligible, key=lambda row: (-float(row["score"]), int(row["global_ordinal"]), str(row["story_id"]))):
        if len(selected) >= TARGET_STORY_COUNT:
            break
        chapter = str(item["chapter"])
        # Keep the selection broad without imposing a chapter quota.
        bonus = 1.0 if chapters[chapter] == 0 else 0.0
        item["selection_score"] = round(float(item["score"]) + bonus, 6)
        selected.append(item)
        chapters[chapter] += 1
    selected.sort(key=lambda row: (int(row["global_ordinal"]), str(row["story_id"])))
    records = []
    for rank, item in enumerate(selected, 1):
        reasons = []
        if item["existing_production_person_ids"]:
            reasons.append("connects existing production Persons")
        if item["strong_identity_candidate_ids"]:
            reasons.append("opens safely identified bridge candidates")
        if item["h0b_structural_signals"]:
            reasons.append("contains family/office structural material")
        if item["temporal_signals"]:
            reasons.append("contains temporal or event signals")
        if not reasons:
            reasons.append("narratively worthwhile canonical entry")
        records.append(
            {
                "story_id": item["story_id"],
                "selection_rank": rank,
                "selection_score": item["selection_score"],
                "score_components": item["score_components"],
                "selection_reasons": reasons,
                "publication_state": item["publication_state"],
                "review_status": "candidate",
                "canonical_entry_sha256": item["canonical_entry_sha256"],
                "expected_production_person_ids": item["existing_production_person_ids"],
                "expected_candidate_ids": item["strong_identity_candidate_ids"],
                "temporal_signals": item["temporal_signals"],
                "structural_signals": item["h0b_structural_signals"],
            }
        )
    return records


def build_person_selection(selected_stories: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_story_ids = {str(item["story_id"]) for item in selected_stories}
    candidates = {str(item["candidate_id"]): item for item in read(PERSON_CANDIDATES_PATH).get("candidates", []) if isinstance(item, Mapping)}
    ranking = {str(item["candidate_id"]): item for item in read(PERSON_RANKING_PATH).get("candidates", []) if isinstance(item, Mapping)}
    materialized = materialized_candidate_ids()
    current_ids = existing_person_ids()
    safe_occurrence_candidates = unambiguous_exact_candidate_ids()
    rows: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates.items():
        if candidate_id in materialized or candidate.get("status") != "strong_candidate" or candidate.get("materialization_state") != "new_candidate":
            continue
        if not candidate.get("identity_evidence_ids"):
            continue
        if candidate_id not in safe_occurrence_candidates:
            continue
        if set(candidate.get("risk_flags", [])) & {"conflicting_identity_evidence", "multiple_possible_people", "no_full_name", "unresolved_identity"}:
            continue
        story_ids = [str(value) for value in candidate.get("shishuo_story_ids", []) if isinstance(value, str)]
        selected_ids = sorted(set(story_ids) & selected_story_ids)
        if not selected_ids:
            continue
        rank_row = ranking.get(candidate_id, {})
        connected = sorted(set(str(value) for value in rank_row.get("connected_current_person_ids", []) if str(value) in current_ids))
        metrics = candidate.get("metrics", {}) if isinstance(candidate.get("metrics"), Mapping) else {}
        family_hint = 1 if any(term in str(candidate.get("preferred_name", "")) for term in ("王", "庾", "桓", "謝", "郗", "顧", "诸葛", "諸葛")) else 0
        structural = len(connected) * 4 + family_hint * 1.5
        narrative = min(8.0, len(selected_ids) * 0.8 + int(metrics.get("shishuo_main_occurrence_count", 0)) * 0.1)
        temporal = min(5.0, float(metrics.get("shishuo_main_story_count", 0)) * 0.25 + (1.0 if "office_title" in str(candidate.get("identity_basis")) else 0.0))
        risk = 1.0 if "contextual_surface_association" in set(candidate.get("risk_flags", [])) else 0.0
        score = round(structural + narrative + temporal - risk, 6)
        rows.append(
            {
                "candidate_id": candidate_id,
                "preferred_name": str(candidate.get("preferred_name")),
                "score": score,
                "score_components": {
                    "structural_bridge_value": round(structural, 6),
                    "narrative_value": round(narrative, 6),
                    "temporal_value": round(temporal, 6),
                    "identity_risk": round(risk, 6),
                },
                "supporting_story_ids": selected_ids,
                "all_story_ids": sorted(story_ids),
                "connected_current_person_ids": connected,
                "identity_evidence_ids": sorted(str(value) for value in candidate.get("identity_evidence_ids", []) if isinstance(value, str)),
                "risk_flags": sorted(str(value) for value in candidate.get("risk_flags", [])),
                "selection_reasons": [
                    f"selected W4 Stories: {len(selected_ids)}",
                    f"connects current Persons: {len(connected)}",
                    "source-backed identity candidate with stable evidence",
                ],
            }
        )
    rows.sort(key=lambda row: (-float(row["score"]), -len(row["supporting_story_ids"]), str(row["preferred_name"]), str(row["candidate_id"])))
    rows = rows[:TARGET_PERSON_COUNT]
    rows = [dict(row, rank=index + 1) for index, row in enumerate(rows)]
    start = 51
    members = []
    for row in rows:
        members.append(
            {
                "candidate_id": row["candidate_id"],
                "rank_at_selection": row["rank"],
                "preferred_name": row["preferred_name"],
                "person_id": f"person-{start + row['rank'] - 1:03d}",
                "candidate_status": "strong_candidate",
                "materialization_status": "pending",
                "review_status": "candidate",
                "selection_basis": row["selection_reasons"],
                "supporting_story_ids": row["supporting_story_ids"],
                "supporting_evidence_ids": row["identity_evidence_ids"],
                "connected_current_person_ids": row["connected_current_person_ids"],
                "structural_value": row["score_components"]["structural_bridge_value"],
                "temporal_value": row["score_components"]["temporal_value"],
                "narrative_value": row["score_components"]["narrative_value"],
                "identity_risk": row["score_components"]["identity_risk"],
            }
        )
    ranking_doc = {
        "schema": 1,
        "stage": "w4-person-expansion-ranking",
        "ranking_version": "w4-story-first-structural-temporal-v2-safe-occurrence-gate",
        "generated_from": [str(PERSON_CANDIDATES_PATH.relative_to(ROOT)), str(PERSON_RANKING_PATH.relative_to(ROOT)), str(STORY_SELECTION_PATH.relative_to(ROOT))],
        "selection_policy": "Freeze the first eligible W4 candidates from the deterministic story-first network ranking; production promotion requires at least one unambiguous exact source coordinate, and IDs are allocated from the existing allocation state.",
        "selected_candidate_ids": [row["candidate_id"] for row in rows],
        "selected_person_count": len(rows),
        "candidates": rows,
    }
    wave = {
        "schema": 1,
        "stage": "w4-person-expansion-wave",
        "wave_id": "w4-structural-temporal-person-wave-1",
        "source_ranking_artifact": str(PERSON_RANKING_OUT_PATH.relative_to(ROOT)),
        "source_ranking_sha256": "",
        "selection_policy": "Story-first W4 structural/temporal expansion; freeze candidate ranks before materialization and never substitute a later identity.",
        "gold_story_ids": [str(item["entry_id"]) for item in read(GOLD_PATH).get("records", [])],
        "selected_story_ids": sorted(selected_story_ids),
        "members": members,
        "notes": [
            "H0B-0 remains frozen; this wave creates only new W4 candidate Person projections.",
            "Non-production identities remain valid and are recorded in the W4 gap/readiness artifacts.",
        ],
    }
    return ranking_doc, wave


def main() -> int:
    audit, current = build_story_audit()
    frozen_story_path = ROOT / "data/annotation/story-expansion-wave-4.json"
    frozen_person_path = ROOT / "data/annotation/person-expansion-wave-4.json"
    frozen_story_document = read(frozen_story_path) if frozen_story_path.is_file() else None
    if isinstance(frozen_story_document, Mapping) and frozen_story_document.get("selection_status") == "frozen":
        selected = [dict(item) for item in frozen_story_document.get("records", []) if isinstance(item, Mapping)]
    else:
        selected = select_stories(audit)
    audit_by_id = {str(item["story_id"]): item for item in audit}
    for record in selected:
        audit_by_id[str(record["story_id"])] ["selected"] = True
        audit_by_id[str(record["story_id"])] ["selection_rank"] = record["selection_rank"]
    audit_doc = {
        "schema": 1,
        "stage": "w4-story-candidate-audit",
        "generated_from": [
            str(CORPUS_PATH.relative_to(ROOT)),
            str(PUNCTUATION_PATH.relative_to(ROOT)),
            str(STORY_RANKING_PATH.relative_to(ROOT)),
            str(EFFECTIVE_PATH.relative_to(ROOT)),
            str(PERSON_OCCURRENCES_PATH.relative_to(ROOT)),
            str(PERSON_CANDIDATES_PATH.relative_to(ROOT)),
        ],
        "scope": {"pre_w4_story_count": len(current), "unpublished_candidate_count": len(audit)},
        "selection_policy": {
            "target_story_count": TARGET_STORY_COUNT,
            "story_first": True,
            "weights": "existing connections + bridge candidates + structural signals + temporal/event signals + chapter diversity + narrative value - identity/isolation risk",
        },
        "selected_story_ids": [str(item["story_id"]) for item in selected],
        "records": sorted(audit_by_id.values(), key=lambda item: (int(item["global_ordinal"]), str(item["story_id"]))),
    }
    write(STORY_AUDIT_PATH, audit_doc)
    story_manifest = {
        "schema": 1,
        "stage": "w4-story-expansion-wave",
        "wave_id": "w4-structural-temporal-story-wave-1",
        "gold_story_ids": [str(item["entry_id"]) for item in read(GOLD_PATH).get("records", [])],
        "previous_expansion_story_ids": [
            *[str(item["story_id"]) for item in read(WAVE1_PATH).get("records", [])],
            *[str(item["story_id"]) for item in read(WAVE3_PATH).get("records", [])],
        ],
        "selection_policy": "Freeze the deterministic story-first W4 ranking before Person materialization; canonical source, punctuation, identity coverage and H0A anchor remain publication gates.",
        "selection_status": "frozen",
        "records": selected,
        "expansion_story_ids": [str(item["story_id"]) for item in selected],
        "source_artifacts": {
            "candidate_audit": str(STORY_AUDIT_PATH.relative_to(ROOT)),
            "candidate_audit_sha256": sha256_file(STORY_AUDIT_PATH),
        },
    }
    if isinstance(frozen_story_document, Mapping) and frozen_story_document.get("selection_status") == "frozen":
        # Enrich the frozen selection with the current deterministic audit
        # scores without changing its membership or rank.
        audit_by_id = {str(item["story_id"]): item for item in audit}
        enriched_records = []
        for record in selected:
            source = audit_by_id.get(str(record["story_id"]), {})
            enriched_records.append({
                **dict(record),
                "selection_score": source.get("score", record.get("selection_score", 0.0)),
                "score_components": source.get("score_components", record.get("score_components", {})),
                "publication_state": source.get("publication_state", record.get("publication_state", "preview_ready")),
                "canonical_entry_sha256": source.get("canonical_entry_sha256", record.get("canonical_entry_sha256")),
                "expected_production_person_ids": source.get("existing_production_person_ids", record.get("expected_production_person_ids", [])),
                "expected_candidate_ids": source.get("strong_identity_candidate_ids", record.get("expected_candidate_ids", [])),
                "temporal_signals": source.get("temporal_signals", record.get("temporal_signals", [])),
                "structural_signals": source.get("h0b_structural_signals", record.get("structural_signals", [])),
            })
        frozen_story_document = {
            **dict(frozen_story_document),
            "records": enriched_records,
            "source_artifacts": {
                **dict(frozen_story_document.get("source_artifacts", {})),
                "candidate_audit_sha256": sha256_file(STORY_AUDIT_PATH),
            },
        }
        write(STORY_SELECTION_PATH, frozen_story_document)
    else:
        write(STORY_SELECTION_PATH, story_manifest)
    frozen_person_document = read(frozen_person_path) if frozen_person_path.is_file() else None
    frozen_person_members = frozen_person_document.get("members", []) if isinstance(frozen_person_document, Mapping) else []
    frozen_person_is_valid = (
        isinstance(frozen_person_document, Mapping)
        and frozen_person_document.get("wave_id") == "w4-structural-temporal-person-wave-1"
        and "unambiguous exact source coordinate" in str(frozen_person_document.get("selection_policy", ""))
        and all(
            str(member.get("candidate_id")) in unambiguous_exact_candidate_ids()
            for member in frozen_person_members
            if isinstance(member, Mapping)
        )
    )
    if frozen_person_is_valid:
        wave = frozen_person_document
    else:
        ranking_doc, wave = build_person_selection(selected)
        write(PERSON_RANKING_OUT_PATH, ranking_doc)
        wave["source_ranking_sha256"] = sha256_file(PERSON_RANKING_OUT_PATH)
        write(PERSON_SELECTION_PATH, wave)
    print(f"W4 story candidates audited: {len(audit)}; selected: {len(selected)}")
    print(f"W4 Person candidates selected: {len(wave['members'])}")
    print("W4 stories:", ", ".join(str(item["story_id"]) for item in selected))
    print("W4 Persons:", ", ".join(f"{item['person_id']} {item['preferred_name']}" for item in wave["members"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
