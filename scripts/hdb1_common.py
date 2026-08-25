#!/usr/bin/env python3
"""Shared deterministic selection and provenance helpers for HDB1-W1.

This module deliberately contains no model calls and no writes to canonical
historical data.  It defines the production boundary, frozen Story/target
selection, and stable identifiers used by the candidate projection.
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import run_hng2_fresh_validation as frozen
import run_hng2_read_fill_validation as c1
import historical_entity_resolver as resolver


ROOT = Path(__file__).resolve().parents[1]
SELECTION_PATH = ROOT / "data/annotation/hdb1-wave1-selection.json"
STAGE = "hdb1-wave1-controlled-candidate-production"
RUN_VERSION = "hdb1-w1-v1"
# HDB1 selections are historical production artifacts.  Their selection
# contract includes the HNG2 exclusion manifest that existed when W1/W2 were
# frozen; later HNG2 files must not make an old selection rebuild drift.
FROZEN_SELECTION_CONTRACT = "hdb1-wave1-wave2-selection-v1"
PRODUCTION_SCOPE_PATH = ROOT / "data/derived/sc1-site.json"
PERSON_LIKE_KINDS = {
    "named_person",
    "abbreviated_name",
    "courtesy_name",
    "person_title",
    "person_office_title",
    "kinship_reference",
    "pronoun_reference",
}
NON_SCENE_ROLES = {"later_outcome", "quoted_precedent", "background_context", "relative_person_time", "office_context"}
RELATION_MARKERS = ("父", "母", "子", "女", "兄", "弟", "妻", "婿", "婚", "嫁", "辟", "拜", "除", "召", "詣", "為", "爲", "任", "語", "問", "見", "從", "與")
TITLE_MARKERS = ("將軍", "将軍", "太守", "刺史", "丞相", "太尉", "太傅", "尚書", "尚书", "令", "校尉", "公", "侯", "王", "帝", "卿")
OFFICE_VERBS = ("為", "爲", "拜", "除", "辟", "召", "任", "授", "兼", "領", "領", "守", "征", "補", "补")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_frozen_previous_hng2_exclusion() -> dict[str, Any]:
    """Load the exclusion snapshot captured by the frozen HDB1 contract.

    The live HNG2 exclusion scanner is intentionally cumulative.  Reusing it
    for an HDB1 rebuild would add files from later experiments to the old
    manifest even when the excluded Story IDs remain identical.  HDB1's
    historical serializer therefore uses the immutable snapshot stored in
    the W1 artifact, falling back to the live scanner only for a brand-new
    checkout without a frozen artifact.
    """

    frozen = read_json(SELECTION_PATH, {}) or {}
    snapshot = frozen.get("previous_hng2_exclusion")
    if isinstance(snapshot, Mapping) and snapshot.get("exclusion_hash"):
        return dict(snapshot)
    import run_hng2_fresh_validation as current_exclusion  # local fallback

    return current_exclusion.collect_previous_hng2_exclusion()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def production_story_rows() -> list[dict[str, Any]]:
    doc = read_json(PRODUCTION_SCOPE_PATH, {}) or {}
    rows = [dict(row) for row in doc.get("stories", []) if isinstance(row, Mapping) and row.get("id")]
    rows.sort(key=lambda row: (int(row.get("global_ordinal") or 0), str(row["id"])))
    if len(rows) != 143 or len({str(row["id"]) for row in rows}) != 143:
        raise RuntimeError("hdb1_production_scope_must_be_143_unique_sc1_story_ids")
    return rows


def production_story_map() -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in production_story_rows()}


def load_people_catalog() -> dict[str, dict[str, Any]]:
    return {str(key): dict(value) for key, value in hng02.person_catalog().items()}


def load_mentions() -> list[dict[str, Any]]:
    doc = read_json(ROOT / "data/mentions/shishuo.json", {}) or {}
    return [dict(row) for row in doc.get("mentions", []) if isinstance(row, Mapping)]


def load_participant_map() -> dict[str, dict[str, Any]]:
    doc = read_json(ROOT / "data/derived/h0b1-story-participants.json", {}) or {}
    return {str(row.get("story_id")): dict(row) for row in doc.get("records", []) if isinstance(row, Mapping) and row.get("story_id")}


def load_h0a_maps() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    anchors_doc = read_json(ROOT / "data/annotation/story-temporal-anchors-h0a.json", {}) or {}
    evidence_doc = read_json(ROOT / "data/annotation/story-temporal-evidence-h0a.json", {}) or {}
    anchors = {str(row.get("story_id")): dict(row) for row in anchors_doc.get("records", []) if isinstance(row, Mapping) and row.get("story_id")}
    evidence: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in evidence_doc.get("records", []):
        if isinstance(row, Mapping) and row.get("story_id"):
            evidence[str(row["story_id"])].append(dict(row))
    return anchors, dict(evidence)


@lru_cache(maxsize=None)
def story_main_text(story_id: str) -> str:
    path = c1._entry_path(story_id)
    text = path.read_text(encoding="utf-8")
    for section, source_text, _metadata in c1.parse_shishuo_sections(text):
        if section == "main_text":
            return str(source_text).rstrip("\n")
    return ""


def _marker_count(text: str) -> int:
    return sum(text.count(marker) for marker in RELATION_MARKERS)


def _mention_rows_by_story(mentions: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in mentions:
        story_id = str(row.get("entry_id") or "")
        if story_id and row.get("section") == "main_text":
            result[story_id].append(dict(row))
    return dict(result)


def target_options(story_id: str, mentions: Sequence[Mapping[str, Any]], participants: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return main-text person target options with no model-derived input."""

    main_rows = _mention_rows_by_story(mentions).get(story_id, [])
    participant_rows = list((participants.get(story_id) or {}).get("participants", []))
    preferred_ids = {
        str(row.get("person_id"))
        for row in participant_rows
        if row.get("role") in {"present", "actor", "speaker"} and str(row.get("person_id")) in catalog
    }
    participant_roles = {
        str(row.get("person_id")): str(row.get("role") or "")
        for row in participant_rows
        if str(row.get("person_id")) in catalog
    }
    main_text = story_main_text(story_id)
    options: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for row in main_rows:
        surface = str(row.get("surface") or "").strip()
        if not surface:
            continue
        person_id = str(row.get("person_id") or "")
        if person_id not in catalog:
            person_id = ""
        candidate_ids = tuple(sorted(str(value) for value in row.get("candidate_person_ids", []) if str(value) in catalog))
        if not person_id and not candidate_ids:
            # Main-text, person-like unresolved mentions remain eligible as
            # observations only when the existing mention layer says they are
            # person candidates.  Generic text is not a production target.
            if not row.get("alias_type") or str(row.get("alias_type")) not in {"personal_name", "courtesy_name", "contextual_title", "office_title", "kinship_reference"}:
                continue
        key = (surface, person_id, candidate_ids)
        if key in seen:
            continue
        seen.add(key)
        canonical = str((catalog.get(person_id) or {}).get("canonical_name") or "")
        role = participant_roles.get(person_id, "")
        title_like = any(marker in surface for marker in TITLE_MARKERS)
        kinship_like = any(marker in main_text for marker in ("父", "母", "子", "女", "兄", "弟", "妻", "婿", "婚", "嫁"))
        institutional_like = any(marker in main_text for marker in ("辟", "拜", "除", "召", "詣", "為掾", "爲掾", "任"))
        if not person_id or len(candidate_ids) > 1:
            category = "ambiguous_or_unresolved"
        elif title_like or surface != canonical:
            category = "abbreviated_or_title"
        elif kinship_like:
            category = "kinship_or_marriage"
        elif institutional_like:
            category = "institutional_or_interaction"
        else:
            category = "clear_full_name"
        selection_key = stable_hash({"story_id": story_id, "surface": surface, "person_id": person_id, "candidate_ids": candidate_ids})
        options.append(
            {
                "surface": surface,
                "person_id": person_id or None,
                "candidate_person_ids": list(candidate_ids),
                "canonical_name": canonical,
                "category": category,
                "role": role,
                "participant_preferred": bool(person_id and person_id in preferred_ids),
                "selection_key": selection_key,
                "mention_id": row.get("mention_id"),
                "source_section": "main_text",
                "mention_evidence_ids": list((row.get("evidence") or {}).get("evidence_ids", [])),
            }
        )
    return sorted(options, key=lambda row: (row["selection_key"], row["surface"]))


def choose_targets(story_id: str, mentions: Sequence[Mapping[str, Any]], participants: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    options = target_options(story_id, mentions, participants, catalog)
    if not options:
        raise RuntimeError(f"hdb1_story_has_no_main_text_person_target:{story_id}")
    primary = sorted(
        options,
        key=lambda row: (
            0 if row.get("participant_preferred") else 1,
            0 if row.get("role") in {"present", "actor", "speaker"} else 1,
            0 if row.get("person_id") else 1,
            row["selection_key"],
        ),
    )[0]
    chosen = [dict(primary)]
    # A secondary target is selected only when it adds a distinct main-text
    # person and an explicit structural signal or hard participant status.
    secondary_candidates = [
        row for row in options
        if row is not primary
        and (row.get("person_id") or row.get("candidate_person_ids"))
        and row.get("surface") != primary.get("surface")
        and (
            row.get("participant_preferred")
            or row.get("role") in {"present", "actor", "speaker"}
            or row.get("category") in {"kinship_or_marriage", "institutional_or_interaction"}
        )
    ]
    if secondary_candidates:
        chosen.append(sorted(secondary_candidates, key=lambda row: row["selection_key"])[0])
    for index, row in enumerate(chosen, start=1):
        row["target_index"] = index
        row["target_id"] = f"hdb1-target-{story_id}-p{index}"
    return chosen


def social_density_score(story_id: str, mentions: Sequence[Mapping[str, Any]], participants: Mapping[str, Mapping[str, Any]]) -> tuple[int, int, int, int, str]:
    main = [row for row in mentions if row.get("entry_id") == story_id and row.get("section") == "main_text"]
    known = {str(row.get("person_id")) for row in main if row.get("person_id")}
    participant_rows = list((participants.get(story_id) or {}).get("participants", []))
    hard = sum(row.get("role") in {"present", "actor", "speaker"} for row in participant_rows)
    text = story_main_text(story_id)
    return (len(known), len(main), hard, _marker_count(text), stable_hash({"story_id": story_id, "stratum": "social-density"}))


def temporal_gap_score(story_id: str, anchors: Mapping[str, Mapping[str, Any]], evidence: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[int, int, int, int, str]:
    anchor = anchors.get(story_id, {})
    rows = list(evidence.get(story_id, []))
    precision = str(anchor.get("precision") or "unknown")
    weak = 1 if precision in {"unknown", "phase_only", ""} else 0
    annotation = sum(str(row.get("source_layer")) == "liu_annotation" for row in rows)
    historical = sum(row.get("evidence_type") in {"historical_event_reference", "ruler_reference", "era_year"} for row in rows)
    evidence_count = len(rows)
    return (weak, annotation, historical, evidence_count, stable_hash({"story_id": story_id, "stratum": "temporal-gap"}))


def protected_paths() -> list[Path]:
    candidates = [
        ROOT / "data/people.json",
        ROOT / "data/derived/sc1-site.json",
        ROOT / "data/derived/h0b1-social-backbone.json",
        ROOT / "data/derived/person-relations-r3b.json",
        ROOT / "data/annotation/story-temporal-anchors-h0a.json",
        ROOT / "data/annotation/story-temporal-evidence-h0a.json",
        ROOT / "data/annotation/kinship-h0b1.json",
        ROOT / "data/annotation/marriages-h0b1.json",
        ROOT / "data/annotation/office-tenures-h0b1.json",
    ]
    return [path for path in candidates if path.is_file()]


def protected_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): file_hash(path) for path in protected_paths()}


def source_refs_for_story(story_id: str, target: Mapping[str, Any]) -> dict[str, list[str]]:
    person_windows = c1._select_story_windows(story_id, target=str(target.get("surface") or ""), canonical_name=str(target.get("canonical_name") or ""), lane="person")
    temporal_windows = c1._select_story_windows(story_id, lane="temporal")
    return {
        "person": sorted({str(row.get("ref")) for row in person_windows if row.get("ref")}),
        "temporal": sorted({str(row.get("ref")) for row in temporal_windows if row.get("ref")}),
        "all": sorted({str(row.get("ref")) for row in [*person_windows, *temporal_windows] if row.get("ref")}),
    }


def build_selection() -> dict[str, Any]:
    rows = production_story_rows()
    story_map = {str(row["id"]): row for row in rows}
    mentions = load_mentions()
    participants = load_participant_map()
    catalog = load_people_catalog()
    options = {story_id: target_options(story_id, mentions, participants, catalog) for story_id in story_map}
    missing = sorted(story_id for story_id, values in options.items() if not values)
    if missing:
        raise RuntimeError(f"hdb1_missing_main_text_targets:{','.join(missing)}")
    exclusion = load_frozen_previous_hng2_exclusion()
    excluded_ids = set(exclusion.get("story_ids", []))
    untouched = sorted(story_id for story_id in story_map if story_id not in excluded_ids)
    reused_pool = sorted(story_id for story_id in story_map if story_id in excluded_ids)
    available = list(untouched)
    reused = False
    if len(available) < 48:
        reused = True
        available.extend(sorted(reused_pool, key=lambda story_id: stable_hash({"story_id": story_id, "reuse": True}))[: 48 - len(available)])
    if len(available) < 48:
        raise RuntimeError(f"hdb1_story_count_unavailable:{len(available)}")

    social_ranked = sorted(available, key=lambda story_id: tuple([-value for value in social_density_score(story_id, mentions, participants)[:4]] + [social_density_score(story_id, mentions, participants)[4]]))
    social_ids = social_ranked[:16]
    remaining = [story_id for story_id in available if story_id not in social_ids]
    temporal_ranked = sorted(remaining, key=lambda story_id: tuple([-value for value in temporal_gap_score(story_id, *load_h0a_maps())[:4]] + [temporal_gap_score(story_id, *load_h0a_maps())[4]]))
    temporal_ids = temporal_ranked[:16]
    remaining = [story_id for story_id in remaining if story_id not in temporal_ids]
    baseline_ids = sorted(remaining, key=lambda story_id: stable_hash({"story_id": story_id, "stratum": "baseline"}))[:16]
    selected_ids = [*social_ids, *temporal_ids, *baseline_ids]
    if len(selected_ids) != 48 or len(set(selected_ids)) != 48:
        raise RuntimeError("hdb1_selection_not_48_unique")
    anchors, evidence = load_h0a_maps()
    rows_out: list[dict[str, Any]] = []
    stratum_by_id = {story_id: "social-density" for story_id in social_ids}
    stratum_by_id.update({story_id: "temporal-gap" for story_id in temporal_ids})
    stratum_by_id.update({story_id: "baseline" for story_id in baseline_ids})
    for story_id in selected_ids:
        target_rows = choose_targets(story_id, mentions, participants, catalog)
        target_out: list[dict[str, Any]] = []
        for target in target_rows:
            refs = source_refs_for_story(story_id, target)
            target_out.append({
                **target,
                "story_id": story_id,
                "reference_person_id": target.get("person_id"),
                "reference_candidate_person_ids": target.get("candidate_person_ids", []),
                "reference_canonical_name": target.get("canonical_name"),
                "source_refs": refs["person"],
                "selection_key": stable_hash({"story_id": story_id, "target_id": target["target_id"], "surface": target["surface"], "source_refs": refs["person"]}),
            })
        source_refs = source_refs_for_story(story_id, target_out[0])
        selection_key = stable_hash({"story_id": story_id, "stratum": stratum_by_id[story_id], "target_ids": [row["target_id"] for row in target_out], "source_refs": source_refs})
        rows_out.append({
            "story_id": story_id,
            "stratum": stratum_by_id[story_id],
            "selection_key": selection_key,
            "previous_hng2_overlap": story_id in excluded_ids,
            "reused_story": story_id in excluded_ids,
            "source_refs": source_refs,
            "h0a_anchor": dict(anchors.get(story_id, {})),
            "h0a_evidence_count": len(evidence.get(story_id, [])),
            "targets": target_out,
        })
    rows_out.sort(key=lambda row: (str(row["stratum"]), str(row["selection_key"])))
    core = {
        "stage": STAGE,
        "wave_id": "HDB1-W1",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HNG2-V1-frozen",
        "prompt_versions": {
            "person_read": frozen.PROMPT_VERSION,
            "person_fill": frozen.PROMPT_VERSION,
            "temporal_read": frozen.PROMPT_VERSION,
            "temporal_fill": frozen.PROMPT_VERSION,
        },
        "model": frozen.MODEL,
        "temperature": 0,
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "story_count": 48,
        "production_scope": "sc1-site.json:143-stories",
        "production_scope_story_count": len(rows),
        "stories": rows_out,
        "stratum_targets": {"social-density": 16, "temporal-gap": 16, "baseline": 16},
        "stratum_actual": dict(collections.Counter(row["stratum"] for row in rows_out)),
        "reused_story_count": sum(row["reused_story"] for row in rows_out),
        "person_target_count": sum(len(row["targets"]) for row in rows_out),
        "expected_semantic_calls": 2 * sum(len(row["targets"]) for row in rows_out) + 2 * len(rows_out),
        "previous_hng2_exclusion": exclusion,
        "previous_hng2_exclusion_hash": exclusion.get("exclusion_hash"),
        "overlap_with_previous_hng2": sorted(row["story_id"] for row in rows_out if row["previous_hng2_overlap"]),
        "protected_hashes_before_live": protected_hashes(),
        "no_search_plan": True,
        "no_research_gap_loop": True,
        "no_recursive_retrieval": True,
        "selection_method": "deterministic production boundary + stable evidence metadata; no model output",
    }
    core["selection_hash"] = stable_hash(core)
    return core


def ensure_selection() -> dict[str, Any]:
    candidate = build_selection()
    if SELECTION_PATH.is_file():
        existing = read_json(SELECTION_PATH, {}) or {}
        expected_hash = existing.get("selection_hash")
        existing_core = {key: value for key, value in existing.items() if key != "selection_hash"}
        if not expected_hash or stable_hash(existing_core) != expected_hash:
            raise RuntimeError("hdb1_selection_existing_hash_invalid")
        if stable_hash(existing) != stable_hash(candidate):
            raise RuntimeError("hdb1_selection_immutable_mismatch")
        return existing
    write_json(SELECTION_PATH, candidate)
    return candidate


def load_frozen_selection() -> dict[str, Any]:
    selection = read_json(SELECTION_PATH, {}) or {}
    selection_hash = selection.get("selection_hash")
    if not selection_hash or stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}) != selection_hash:
        raise RuntimeError("hdb1_selection_hash_invalid")
    if selection.get("frozen_before_live") is not True or selection.get("story_count") != 48:
        raise RuntimeError("hdb1_selection_not_frozen")
    if len(selection.get("stories", [])) != 48 or len({row.get("story_id") for row in selection.get("stories", [])}) != 48:
        raise RuntimeError("hdb1_selection_shape_invalid")
    return selection


def hdb_stable_id(kind: str, material: Mapping[str, Any]) -> str:
    return f"hdb1-{kind}-{stable_hash(dict(material))[:24]}"


def source_hash_for_ref(windows: Sequence[Mapping[str, Any]], ref: str) -> str | None:
    for row in windows:
        if str(row.get("ref")) == str(ref):
            return str(row.get("evidence_text_sha256") or stable_hash(row.get("evidence_text") or ""))
    return None


def is_person_like(kind: Any) -> bool:
    return str(kind or "") in PERSON_LIKE_KINDS


def is_office_or_title_entity(kind: Any) -> bool:
    return str(kind or "") in {"person_title", "person_office_title"}


def looks_like_office_relation(relation: Mapping[str, Any], entities_by_key: Mapping[str, Mapping[str, Any]]) -> bool:
    if is_office_or_title_entity((entities_by_key.get(str(relation.get("object_entity_key"))) or {}).get("entity_kind")):
        return True
    surface = str(relation.get("relation_surface") or "")
    span = str(relation.get("exact_span") or "")
    return any(marker in surface or marker in span for marker in (*TITLE_MARKERS, *OFFICE_VERBS))


def relation_has_explicit_evidence(relation: Mapping[str, Any]) -> bool:
    return bool(str(relation.get("evidence_ref") or "") and str(relation.get("exact_span") or ""))
