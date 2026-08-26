#!/usr/bin/env python3
"""Candidate-only HDB2-PSL1 collective identity experiment.

PSL1 is deliberately separate from ``hdb2_psl0_common``.  It reuses the
frozen LJ0 case/candidate construction, but gives identity evidence its own
predicates and treats contextual compatibility as non-identifying unless it
is specifically identity-bearing.  Nothing in this module writes canonical
or reviewed historical data.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import hdb2_lj0_common as lj0
import hdb2_psl0_common as psl0


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
PSL0_SELECTION = ANNOTATION / "hdb2-psl0-selection.json"
PSL0_CASES = ROOT / "data/generated/hdb2-psl0/live/20260827T-HDB2-PSL0-04/graph-cases.json"
LJ0_CASES = ROOT / "data/generated/hdb2-lj0/live/20260826T-HDB2-LJ0-02/cases.json"
HOLDOUT_SELECTION = ANNOTATION / "hdb2-psl1-holdout-selection.json"

MODEL = "deepseek-v4-flash"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
RUN_VERSION = "hdb2-psl1-v1"
PROMPT_VERSION = "hdb2-psl1-identity-predicates-v1"
REVIEW_PROMPT_VERSION = "hdb2-psl1-adversarial-review-v1"
FUNCTION_NAME = "submit_hdb2_psl1_predicates"
REVIEW_FUNCTION_NAME = "submit_hdb2_psl1_review"

LLM_PREDICATES = {
    "Coreference",
    "IdentityContextSupport",
    "CrossStoryIdentitySupport",
    "IdentityContradiction",
}
DETERMINISTIC_PREDICATES = {
    "AliasMatch",
    "TimeCompatible",
    "SameStory",
    "KnownRelation",
    "OfficeCompatible",
    "KinshipCompatible",
    "Distinct",
}
ALL_PREDICATES = LLM_PREDICATES | DETERMINISTIC_PREDICATES
FORBIDDEN_ID_KEYS = {
    "person_id",
    "provisional_person_id",
    "canonical_person_id",
    "relation_id",
    "graph_id",
    "candidate_id",
}

# Fixed, deliberately transparent experiment weights.  TimeCompatible and
# SameStory are diagnostic/context edges only; neither supplies positive Link
# pressure on its own.  KnownRelation contributes only through another
# linked mention during collective iterations.
RULE_WEIGHTS = {
    "AliasMatch": 2.4,
    "IdentityContextSupport": 2.2,
    "CrossStoryIdentitySupport": 1.8,
    "IdentityContradiction": 2.8,
    "OfficeCompatible": 0.9,
    "KinshipCompatible": 0.9,
    "Coreference": 1.5,
    "KnownRelation": 0.8,
    "Distinct": 3.0,
}
ITERATIONS = 4
HIGH_LINK_THRESHOLD = 0.65
HIGH_MARGIN_THRESHOLD = 0.20
HIGH_RAW_SCORE_THRESHOLD = 1.8
HIGH_SUPPORT_FAMILIES = 1
RELATIONAL_SUPPORT_FAMILIES = {
    "Coreference",
    "KnownRelation",
    "OfficeCompatible",
    "KinshipCompatible",
}
DIRECT_IDENTITY_PREDICATES = {
    "AliasMatch",
    "IdentityContextSupport",
    "CrossStoryIdentitySupport",
}
COMPOSITIONAL_TYPES = {"kinship_reference", "kinship_compositional_reference"}
PERSON_LIKE_TYPES = {
    "named_person",
    "named_person_reference",
    "abbreviated_name",
    "abbreviated_person_name",
    "courtesy_name",
    "courtesy_name_reference",
}
ROLE_MARKERS = set("帝公侯尹史令將軍太傅司空僕射主卿侯王")
REVIEW_VERDICTS = {
    "resolve",
    "retain_review",
    "genuinely_unresolved",
    "reject_top_candidate",
}
REVIEW_REASON_TYPES = {
    "direct_identity_evidence",
    "contextual_compatibility_only",
    "alternative_candidate",
    "insufficient_evidence",
    "temporal_contradiction",
    "identity_contradiction",
    "semantic_contradiction",
    "explicit_distinctness",
    "relation_path_only",
    "compositional_reference",
}


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def matching(value: Any) -> str:
    return psl0.matching(value)


def _selection_category(item: Mapping[str, Any]) -> str:
    review_type = str(item.get("review_type") or "")
    occurrence_type = str(item.get("occurrence_type") or "")
    surface = str(item.get("target_surface") or item.get("surface") or "")
    if occurrence_type in COMPOSITIONAL_TYPES or review_type == "compositional_kinship":
        return "compositional_kinship"
    if occurrence_type == "ruler_reference" or surface in lj0.RULER_SURFACES:
        return "ruler_reference"
    if review_type == "candidate_person" or occurrence_type in {"abbreviated_person_name", "courtesy_name_reference"}:
        return "abbreviated_or_courtesy"
    if review_type == "identity":
        return "ambiguous_identity"
    if review_type == "office_or_title_holder" or occurrence_type in {"title_reference", "office_reference"}:
        return "office_or_title"
    return "ordinary_unresolved"


def _holdout_rank(item: Mapping[str, Any], *, anchor: bool = False) -> tuple[Any, ...]:
    row = lj0._selection_row(item)
    # Selection is based only on frozen review metadata, never on a PSL
    # result.  The anchor bit ensures the requested existing frontier Stories
    # are represented while the remaining order is stable hash order.
    return (
        0 if anchor else 1,
        -int(row.get("selection_value") or 0),
        str(row.get("selection_key") or ""),
    )


def _selection_row(item: Mapping[str, Any], *, category: str) -> dict[str, Any]:
    row = lj0._selection_row(item)
    row["target_surface"] = row.get("surface")
    row["selection_category"] = category
    return row


def build_holdout_selection(*, limit: int = 20) -> dict[str, Any]:
    if limit < 20 or limit > 30:
        raise ValueError("psl1_holdout_limit_out_of_range")
    items = lj0.load_review_items()
    psl0_doc = read_json(PSL0_SELECTION, {}) or {}
    excluded = {str(row.get("occurrence_id")) for row in psl0_doc.get("cases", [])}
    anchors = [
        "02-yanyu-035",
        "02-yanyu-036",
        "02-yanyu-042",
        "02-yanyu-046",
        "02-yanyu-107",
        "04-wenxue-024",
        "04-wenxue-036",
        "05-fangzheng-027",
        "05-fangzheng-030",
        "06-yaliang-027",
        "06-yaliang-029",
        "07-shijian-018",
        "24-jianao-003",
    ]
    eligible = [item for item in items if str(item.get("occurrence_id")) not in excluded]
    by_story: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for item in eligible:
        by_story[str(item.get("story_id"))].append(item)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for story_id in anchors:
        candidates = sorted(by_story.get(story_id, []), key=lambda item: _holdout_rank(item, anchor=True))
        if candidates:
            item = candidates[0]
            row = _selection_row(item, category=_selection_category(item))
            selected.append(row)
            selected_ids.add(str(row.get("occurrence_id")))
    # Prefer new Stories for the fill, preserving category diversity by
    # taking the highest ranked item from each unseen Story before allowing a
    # second item from a Story already represented.
    remaining = [item for item in eligible if str(item.get("occurrence_id")) not in selected_ids]
    new_story_rows = sorted(
        remaining,
        key=lambda item: _holdout_rank(item, anchor=False),
    )
    represented = {str(row.get("story_id")) for row in selected}
    for item in new_story_rows:
        if len(selected) >= limit:
            break
        story_id = str(item.get("story_id"))
        occurrence_id = str(item.get("occurrence_id"))
        if story_id in represented or occurrence_id in selected_ids:
            continue
        row = _selection_row(item, category=_selection_category(item))
        selected.append(row)
        selected_ids.add(occurrence_id)
        represented.add(story_id)
    for item in new_story_rows:
        if len(selected) >= limit:
            break
        occurrence_id = str(item.get("occurrence_id"))
        if occurrence_id in selected_ids:
            continue
        row = _selection_row(item, category=_selection_category(item))
        selected.append(row)
        selected_ids.add(occurrence_id)
    if len(selected) != limit:
        raise RuntimeError(f"psl1_holdout_count:{len(selected)}")
    selected.sort(key=lambda row: str(row.get("selection_key") or ""))
    result: dict[str, Any] = {
        "schema": "hdb2-psl1-holdout-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "source": "current HDB2 review frontier excluding frozen PSL0 occurrences",
        "excluded_psl0_occurrence_ids": sorted(excluded),
        "anchor_story_ids": anchors,
        "cases": selected,
        "selected_count": len(selected),
        "review_queue_hash": stable_hash(read_json(ANNOTATION / "hdb2-f-review-queue.json", {}) or {}),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    return result


def freeze_holdout_selection(path: Path = HOLDOUT_SELECTION, *, limit: int = 20) -> dict[str, Any]:
    proposed = build_holdout_selection(limit=limit)
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hdb2_psl1_holdout_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def freeze_experiment_selection(path: Path = ANNOTATION / "hdb2-psl1-selection.json", *, holdout_limit: int = 20) -> dict[str, Any]:
    psl0_selection = read_json(PSL0_SELECTION, {}) or {}
    holdout = freeze_holdout_selection(limit=holdout_limit)
    regression_rows = [dict(row) for row in psl0_selection.get("cases", [])]
    holdout_rows = [dict(row) for row in holdout.get("cases", [])]
    regression_ids = {str(row.get("occurrence_id")) for row in regression_rows}
    holdout_ids = {str(row.get("occurrence_id")) for row in holdout_rows}
    if regression_ids & holdout_ids:
        raise RuntimeError("psl1_regression_holdout_overlap")
    result: dict[str, Any] = {
        "schema": "hdb2-psl1-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "review_prompt_version": REVIEW_PROMPT_VERSION,
        "model": MODEL,
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "regression_source": "frozen HDB2-PSL0 24-case selection",
        "regression_selection_hash": psl0_selection.get("selection_hash"),
        "regression_cases": regression_rows,
        "holdout_selection_hash": holdout.get("selection_hash"),
        "holdout_cases": holdout_rows,
        "regression_count": len(regression_rows),
        "holdout_count": len(holdout_rows),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != result:
            raise RuntimeError("hdb2_psl1_selection_changed")
        return existing
    write_json(path, result)
    return result


def load_regression_cases() -> dict[str, Any]:
    # Rebuild the regression input from the frozen LJ0 case source.  The PSL0
    # graph-cases artifact contains an already-expanded graph representation;
    # feeding that back through the PSL0 builder would make this regression
    # depend on an implementation artifact rather than the frozen selection.
    source = psl0.load_frozen_lj0_cases()
    return {
        "schema": "hdb2-psl1-regression-cases-v1",
        "selection_hash": source.get("selection_hash"),
        "cases": list(source.get("cases", [])),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def load_holdout_cases(selection: Mapping[str, Any]) -> dict[str, Any]:
    # LJ0's existing case builder is the frozen SELECT/candidate construction;
    # only the selection rows differ.  No PSL0 or HDB2 decision is passed to
    # the model as an answer.
    return lj0.build_cases({
        "schema": "hdb2-psl1-holdout-input-v1",
        "cases": list(selection.get("holdout_cases", [])),
    })


def _evidence_ids(case: Mapping[str, Any], *families: str) -> list[str]:
    allowed = set(families)
    return [
        str(row.get("evidence_id"))
        for row in case.get("evidence_items", [])
        if row.get("evidence_id") and str(row.get("family")) in allowed
    ][:6]


def _candidate_matches_exclusion(candidate: Mapping[str, Any], exclusion: Mapping[str, Any]) -> bool:
    candidate_pid = str(candidate.get("person_id") or "")
    candidate_name = matching(candidate.get("display_name"))
    exclusion_pid = str(exclusion.get("person_id") or "")
    exclusion_name = matching(exclusion.get("display_name"))
    return bool((candidate_pid and exclusion_pid and candidate_pid == exclusion_pid) or (candidate_name and exclusion_name and candidate_name == exclusion_name))


def _explicit_surname_mismatch(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    occurrence_type = str(case.get("psl_occurrence_type") or case.get("occurrence_type") or "")
    surface = str(case.get("target_surface") or "")
    display = str(candidate.get("display_name") or "")
    if occurrence_type not in PERSON_LIKE_TYPES or len(surface) < 2 or len(display) < 2:
        return False
    if surface[0] in ROLE_MARKERS or display[0] in ROLE_MARKERS:
        return False
    # This conservative gate only applies when the target is a name-shaped
    # expression.  Single-character abbreviations and title/office forms are
    # intentionally left to contextual evidence.
    return surface[0] != display[0]


def _candidate_hard_reasons(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    occurrence_type = str(case.get("psl_occurrence_type") or case.get("occurrence_type") or "")
    for exclusion in [*case.get("hard_exclusions", []), *case.get("psl_hard_exclusions", [])]:
        if isinstance(exclusion, Mapping) and _candidate_matches_exclusion(candidate, exclusion):
            reasons.extend(str(value) for value in exclusion.get("reasons", []) if value)
    if occurrence_type == "ruler_reference" and str(candidate.get("semantic_type") or "person") != "ruler_title":
        reasons.append("ruler_semantic_type_mismatch")
    if occurrence_type in COMPOSITIONAL_TYPES:
        base = matching(lj0._base_surface(str(case.get("target_surface") or "")))
        forms = [candidate.get("display_name"), *_profile_forms(candidate)]
        if base and any(matching(value) == base for value in forms if value):
            reasons.append("compositional_base_person")
    if _explicit_surname_mismatch(case, candidate):
        reasons.append("explicit_surname_mismatch")
    for row in case.get("deterministic_predicates", []):
        if str(row.get("candidate_key")) == str(candidate.get("candidate_key")) and str(row.get("predicate")) == "TimeCompatible" and float(row.get("value", 0.5)) <= 0:
            reasons.append("impossible_chronology")
    return sorted(set(reasons))


def _profile_forms(candidate: Mapping[str, Any]) -> list[str]:
    profile = candidate.get("profile") if isinstance(candidate.get("profile"), Mapping) else {}
    return [
        str(candidate.get("display_name") or ""),
        *(str(value) for value in profile.get("aliases", []) if value),
        *(str(value) for value in profile.get("courtesy_names", []) if value),
        *(str(value) for value in profile.get("titles", []) if value),
    ]


def _has_neighbor(knowledge: Mapping[str, Mapping[str, Any]], left_pid: str, right_pid: str) -> bool:
    for current, other in ((left_pid, right_pid), (right_pid, left_pid)):
        row = knowledge.get(current, {})
        social = row.get("social") if isinstance(row.get("social"), Mapping) else {}
        for neighbor in social.get("resolved_neighbors", []) if isinstance(social, Mapping) else []:
            if isinstance(neighbor, Mapping) and str(neighbor.get("person_id")) == other:
                return True
    return False


def _same_story_pairs(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for case in cases:
        for row in case.get("same_story_predicates", []):
            left, right = sorted((str(row.get("mention_id")), str(row.get("other_mention_id"))))
            if not left or not right or left == right:
                continue
            pairs.setdefault((left, right), {
                "pair_id": f"coref:{left}:{right}",
                "predicate": "Coreference",
                "left_mention_id": left,
                "right_mention_id": right,
                "story_id": row.get("story_id"),
            })
    return [pairs[key] for key in sorted(pairs)]


def _distinct_text(left: str, right: str, text: str) -> bool:
    if not left or not right or left == right or not text:
        return False
    # The explicit list/coordination pattern is intentionally narrow.  A
    # shared Story or adjacent mentions alone are not distinctness evidence.
    patterns = (
        f"{left}、{right}",
        f"{right}、{left}",
        f"{left}與{right}",
        f"{right}與{left}",
    )
    return any(pattern in text for pattern in patterns)


def _distinct_pairs(cases: Sequence[Mapping[str, Any]], same_pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(case.get("mention_id")): case for case in cases}
    result: list[dict[str, Any]] = []
    for pair in same_pairs:
        left = by_id.get(str(pair.get("left_mention_id")), {})
        right = by_id.get(str(pair.get("right_mention_id")), {})
        if str(left.get("story_id")) != str(right.get("story_id")):
            continue
        if _distinct_text(str(left.get("target_surface") or ""), str(right.get("target_surface") or ""), str(left.get("story_context") or "")):
            ids = sorted(set(_evidence_ids(left, "story_local_context", "relevant_source_evidence") + _evidence_ids(right, "story_local_context", "relevant_source_evidence")))
            result.append({
                "pair_id": f"distinct:{pair.get('left_mention_id')}:{pair.get('right_mention_id')}",
                "predicate": "Distinct",
                "left_mention_id": pair.get("left_mention_id"),
                "right_mention_id": pair.get("right_mention_id"),
                "story_id": left.get("story_id"),
                "value": 1.0,
                "evidence_ids": ids,
                "reason": "explicit_coordination_names_separately",
            })
    return result


def _known_relation_rows(cases: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    knowledge_rows = lj0.load_person_knowledge()
    knowledge = {str(key): dict(value) for key, value in knowledge_rows.items()}
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for case in cases:
        current_id = str(case.get("mention_id"))
        for other in cases:
            if other is case or str(other.get("story_id")) != str(case.get("story_id")):
                continue
            for left in case.get("candidates", []):
                left_pid = str(left.get("person_id") or "")
                if not left_pid:
                    continue
                for right in other.get("candidates", []):
                    right_pid = str(right.get("person_id") or "")
                    if not right_pid or not _has_neighbor(knowledge, left_pid, right_pid):
                        continue
                    result[current_id].append({
                        "predicate": "KnownRelation",
                        "mention_id": current_id,
                        "other_mention_id": other.get("mention_id"),
                        "candidate_key": left.get("candidate_key"),
                        "other_candidate_key": right.get("candidate_key"),
                        "candidate_node_id": left.get("candidate_node_id"),
                        "other_candidate_node_id": right.get("candidate_node_id"),
                        "value": 1.0,
                        "evidence_ids": _evidence_ids(case, "confirmed_story_profile", "relevant_source_evidence"),
                    })
    for mention_id, rows in result.items():
        seen: set[tuple[Any, ...]] = set()
        unique: list[dict[str, Any]] = []
        for row in rows:
            key = (row.get("other_mention_id"), row.get("candidate_key"), row.get("other_candidate_key"))
            if key not in seen:
                seen.add(key)
                unique.append(row)
        result[mention_id] = unique
    return result


def build_graph_cases(cases_document: Mapping[str, Any]) -> dict[str, Any]:
    base = psl0.build_graph_cases(cases_document)
    cases = [dict(row) for row in base.get("cases", [])]
    same_pairs = _same_story_pairs(cases)
    distinct_pairs = _distinct_pairs(cases, same_pairs)
    distinct_by_mention: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for pair in distinct_pairs:
        for mention_id in (str(pair.get("left_mention_id")), str(pair.get("right_mention_id"))):
            oriented = dict(pair)
            if mention_id == str(pair.get("right_mention_id")):
                oriented["left_mention_id"], oriented["right_mention_id"] = oriented["right_mention_id"], oriented["left_mention_id"]
            distinct_by_mention[mention_id].append(oriented)
    known = _known_relation_rows(cases)
    for case in cases:
        mention_id = str(case.get("mention_id"))
        vetoes: dict[str, list[str]] = {}
        for candidate in case.get("candidates", []):
            reasons = _candidate_hard_reasons(case, candidate)
            if reasons:
                vetoes[str(candidate.get("candidate_key"))] = reasons
        case["psl1_hard_vetoes"] = vetoes
        case["known_relation_predicates"] = known.get(mention_id, [])
        case["distinct_predicates"] = sorted(distinct_by_mention.get(mention_id, []), key=lambda row: str(row.get("pair_id")))
        case["psl1_predicate_set"] = sorted(ALL_PREDICATES)
        case["candidate_only"] = True
        case["canonical_write_back"] = False
    return {
        "schema": "hdb2-psl1-graph-cases-v1",
        "selection_hash": cases_document.get("selection_hash"),
        "cases": cases,
        "context_mentions": list(base.get("context_mentions", [])),
        "coreference_pairs": same_pairs,
        "distinct_pairs": distinct_pairs,
        "predicate_set": sorted(ALL_PREDICATES),
        "positive_link_predicates": sorted({"AliasMatch", "IdentityContextSupport", "CrossStoryIdentitySupport", "OfficeCompatible", "KinshipCompatible", "Coreference", "KnownRelation"}),
        "non_identity_context_predicates": ["TimeCompatible", "SameStory"],
        "negative_rules": {
            "temporal_contradiction": "Python hard veto",
            "ruler_or_semantic_contradiction": "Python hard veto",
            "compositional_collapse": "Python hard veto",
            "surname_mismatch": "Python hard veto when name-shaped",
            "identity_contradiction": "validated negative evidence; zero-valued explicit contradiction may veto",
            "distinct": "explicit local distinctness vetoes shared candidate links",
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _walk_forbidden(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_ID_KEYS:
                found.append(f"{path}.{key}" if path else str(key))
            found.extend(_walk_forbidden(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_forbidden(child, f"{path}[{index}]"))
    return found


def _safe_profile_wire(candidate: Mapping[str, Any]) -> dict[str, Any]:
    profile = candidate.get("profile") if isinstance(candidate.get("profile"), Mapping) else {}
    return {
        "candidate_key": candidate.get("candidate_key"),
        "name": candidate.get("display_name"),
        "aliases": list(profile.get("aliases", []))[:10],
        "courtesy_names": list(profile.get("courtesy_names", []))[:8],
        "titles": list(profile.get("titles", []))[:8],
        "confirmed_story_ids": list(profile.get("confirmed_story_ids", []))[:10],
        "office_context": list(profile.get("known_offices", []))[:8],
        "kinship_context": list(profile.get("known_kinship", []))[:8],
        "known_neighbor_story_context": list(profile.get("known_neighbors", []))[:10],
    }


def _related_mentions(case: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    related = [row for row in cases if str(row.get("story_id")) == str(case.get("story_id")) and str(row.get("mention_id")) != str(case.get("mention_id"))]
    return [
        {
            "mention_id": row.get("mention_id"),
            "surface": row.get("target_surface"),
            "semantic_type": row.get("psl_occurrence_type") or row.get("occurrence_type"),
        }
        for row in sorted(related, key=lambda row: str(row.get("mention_id")))
    ][:8]


def _safe_relation_context(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expose local relation wording without exposing internal identifiers."""
    result: list[dict[str, Any]] = []
    for row in case.get("local_relations", []) or []:
        if not isinstance(row, Mapping):
            continue
        result.append({
            key: row.get(key)
            for key in ("relation_surface", "relation_class", "semantic_level", "story_id", "evidence_ref", "exact_span")
            if row.get(key) not in (None, "")
        })
    return result[:8]


def _request_predicates(case: Mapping[str, Any], graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    mention_id = str(case.get("mention_id"))
    requested: list[dict[str, Any]] = []
    counter = 0
    for candidate in case.get("candidates", []):
        for predicate in ("IdentityContextSupport", "CrossStoryIdentitySupport", "IdentityContradiction"):
            requested.append({
                "predicate_id": f"q{counter}",
                "predicate": predicate,
                "mention_id": mention_id,
                "other_mention_id": None,
                "candidate_key": candidate.get("candidate_key"),
            })
            counter += 1
    # Only the lexicographically first endpoint owns a pair request.  This
    # makes Coreference a single unordered variable, not two asymmetric
    # model judgments.
    for pair in graph.get("coreference_pairs", []):
        if mention_id != str(pair.get("left_mention_id")):
            continue
        requested.append({
            "predicate_id": f"q{counter}",
            "predicate": "Coreference",
            "mention_id": pair.get("left_mention_id"),
            "other_mention_id": pair.get("right_mention_id"),
            "candidate_key": None,
        })
        counter += 1
    return requested


def wire_packet(case: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    evidence = [
        {
            "evidence_id": row.get("evidence_id"),
            "family": row.get("family"),
            "kind": row.get("kind"),
            "source_ref": row.get("source_ref"),
            "text": row.get("text"),
        }
        for row in case.get("evidence_items", [])
        if row.get("evidence_id")
    ]
    evidence_ids = {str(row.get("evidence_id")) for row in evidence}
    # Include related source evidence and local context, but keep the packet
    # occurrence-focused and never expose internal candidate IDs.
    for other in cases:
        if str(other.get("story_id")) != str(case.get("story_id")) or str(other.get("mention_id")) == str(case.get("mention_id")):
            continue
        for row in other.get("evidence_items", [])[:4]:
            evidence_id = f"related:{other.get('mention_id')}:{row.get('evidence_id')}"
            if evidence_id not in evidence_ids:
                evidence.append({
                    "evidence_id": evidence_id,
                    "family": row.get("family"),
                    "kind": row.get("kind"),
                    "source_ref": row.get("source_ref"),
                    "text": row.get("text"),
                })
                evidence_ids.add(evidence_id)
    for context in graph.get("context_mentions", []):
        if str(context.get("story_id")) == str(case.get("story_id")):
            evidence_id = f"context:{context.get('mention_id')}"
            if evidence_id not in evidence_ids:
                evidence.append({
                    "evidence_id": evidence_id,
                    "family": "story_local_context",
                    "kind": "contextual_mention",
                    "source_ref": f"story:{case.get('story_id')}",
                    "text": str(case.get("story_context") or ""),
                })
                evidence_ids.add(evidence_id)
    deterministic: list[dict[str, Any]] = []
    for row in case.get("deterministic_predicates", []):
        predicate = str(row.get("predicate"))
        if predicate in {"AliasMatch", "TimeCompatible", "OfficeCompatible", "KinshipCompatible"}:
            deterministic.append({
                "predicate": predicate,
                "candidate_key": row.get("candidate_key"),
                "value": row.get("value"),
                "evidence_ids": list(row.get("evidence_ids", [])),
                "reason": row.get("reason"),
            })
    deterministic.extend({
        "predicate": "SameStory",
        "mention_id": row.get("left_mention_id"),
        "other_mention_id": row.get("right_mention_id"),
        "value": 1.0,
        "evidence_ids": list(row.get("evidence_ids", [])),
    } for row in case.get("same_story_predicates", []))
    deterministic.extend({
        "predicate": "Distinct",
        "other_mention_id": row.get("right_mention_id"),
        "value": row.get("value"),
        "evidence_ids": list(row.get("evidence_ids", [])),
        "reason": row.get("reason"),
    } for row in case.get("distinct_predicates", []))
    return {
        "task": "grounded PSL1 identity predicate evaluation",
        "mention": {
            "mention_id": case.get("mention_id"),
            "surface": case.get("target_surface"),
            "semantic_type": case.get("psl_occurrence_type") or case.get("occurrence_type"),
            "story_id": case.get("story_id"),
            "story_context": case.get("story_context"),
            "annotation_context": list(case.get("annotation_context", []))[:4],
            "temporal_context": list(case.get("temporal_context", []))[:8],
        },
        "related_mentions": _related_mentions(case, cases),
        "local_relation_context": _safe_relation_context(case),
        "known_relation_context": [
            {
                "mention_id": row.get("mention_id"),
                "other_mention_id": row.get("other_mention_id"),
                "candidate_key": row.get("candidate_key"),
                "other_candidate_key": row.get("other_candidate_key"),
                "evidence_ids": list(row.get("evidence_ids", [])),
            }
            for row in case.get("known_relation_predicates", [])[:8]
        ],
        "candidates": [_safe_profile_wire(candidate) for candidate in case.get("candidates", [])],
        "deterministic_predicates": deterministic,
        "evidence_items": evidence,
        "request_predicates": _request_predicates(case, graph),
        "predicate_constraints": {
            "identity_support_requires_specific_identity_link": True,
            "time_and_same_story_are_not_identity_support": True,
            "cooccurrence_is_not_identity": True,
            "coreference_is_unordered": True,
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def predicate_tool() -> dict[str, Any]:
    item = {
        "type": "object",
        "description": "一个由 supplied evidence 支持的身份谓词判断，不是最终人物决定。",
        "properties": {
            "predicate_id": {"type": "string", "description": "只能复制 supplied request_predicates 中的 q 编号。"},
            "predicate": {"type": "string", "enum": sorted(LLM_PREDICATES), "description": "只能返回 supplied request 中的四类身份谓词。"},
            "mention_id": {"type": "string", "description": "只能复制 supplied mention_id。"},
            "other_mention_id": {"type": ["string", "null"], "description": "Coreference 时复制 supplied pair 的另一端；否则 JSON null。"},
            "candidate_key": {"type": ["string", "null"], "description": "候选谓词只能复制 supplied c... key；Coreference 为 JSON null。"},
            "value": {"type": "number", "minimum": 0, "maximum": 1, "description": "谓词支持度 0 到 1；0.5 是 neutral，不是身份概率。"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "直接支持该谓词值的 supplied evidence_id；无直接证据时为空。"},
        },
        "required": ["predicate_id", "predicate", "mention_id", "other_mention_id", "candidate_key", "value", "evidence_ids"],
        "additionalProperties": False,
    }
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "只根据 supplied evidence 返回身份谓词值；不得选择最终人物或输出数据库 ID。",
            "strict": True,
            "parameters": {
                "type": "object",
                "description": "覆盖 supplied 请求的身份谓词，不做最终身份决定。",
                "properties": {
                    "predicates": {"type": "array", "maxItems": 100, "items": item, "description": "逐项覆盖 request_predicates，不新增请求外谓词。"},
                    "note": {"type": "string", "description": "仅供审计的简短说明；Python 不依赖 note。"},
                },
                "required": ["predicates", "note"],
                "additionalProperties": False,
            },
        },
    }


def tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": FUNCTION_NAME}}


SYSTEM_PROMPT = """只根据 supplied occurrence context、candidate dossiers 和 evidence_items 判断请求的身份谓词。IdentityContextSupport 与 CrossStoryIdentitySupport 只有在原文具体支持该 mention 指向该 candidate 时才可为正；同一时代、同一 Story、共同出现、一般生平相容都不是身份支持。IdentityContradiction 只记录 supplied evidence 明确反对该指派的内容。Coreference 只判断 supplied 的无序 mention pair。证据不足返回 0.5；每个非 neutral 值必须引用 supplied evidence_ids。不要选择最终人物，不要使用外部知识，不要输出任何 Person/Relation/Graph ID，逐项覆盖 request_predicates。"""


def validate_predicates(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors = [f"forbidden_id_field:{path}" for path in _walk_forbidden(payload)]
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": sorted(set(["payload_not_object", *errors]))}
    expected = {"predicates", "note"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    if not isinstance(payload.get("note"), str):
        errors.append("note_invalid")
    requested = {str(row.get("predicate_id")): dict(row) for row in packet.get("request_predicates", [])}
    evidence = {str(row.get("evidence_id")) for row in packet.get("evidence_items", [])}
    rows = payload.get("predicates")
    if not isinstance(rows, list):
        errors.append("predicates_not_array")
        rows = []
    elif len(rows) > 100:
        errors.append("predicates_too_many")
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"predicate_not_object:{index}")
            continue
        expected_row = {
            "predicate_id",
            "predicate",
            "mention_id",
            "other_mention_id",
            "candidate_key",
            "value",
            "evidence_ids",
        }
        errors.extend(
            f"unknown_predicate_field:{index}:{key}"
            for key in sorted(set(row) - expected_row)
        )
        predicate_id = row.get("predicate_id")
        if not isinstance(predicate_id, str) or not predicate_id:
            errors.append(f"predicate_id_invalid:{index}")
            predicate_id = ""
        request = requested.get(predicate_id)
        if request is None:
            errors.append(f"predicate_id_invalid:{predicate_id}")
        if predicate_id in seen:
            errors.append(f"predicate_id_duplicate:{predicate_id}")
        seen.add(predicate_id)
        predicate = row.get("predicate")
        if predicate not in LLM_PREDICATES:
            errors.append(f"predicate_invalid:{predicate}")
        if request:
            for key in ("predicate", "mention_id", "other_mention_id", "candidate_key"):
                if row.get(key) != request.get(key):
                    errors.append(f"predicate_endpoint_mismatch:{predicate_id}:{key}")
        if row.get("candidate_key") == "null" or row.get("other_mention_id") == "null":
            errors.append(f"literal_null_invalid:{predicate_id}")
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            errors.append(f"predicate_value_invalid:{predicate_id}")
        ids = row.get("evidence_ids")
        if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
            errors.append(f"evidence_ids_invalid:{predicate_id}")
            ids = []
        for evidence_id in ids:
            if evidence_id not in evidence:
                errors.append(f"evidence_reference_invalid:{predicate_id}:{evidence_id}")
        # In this predicate wire contract, 0 is an explicit absence of the
        # predicate (no support / no contradiction), while 0.5 is unknown.
        # Neither makes a historical claim.  Any fractional or positive
        # assertion away from those neutral endpoints must be grounded.
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and abs(float(value)) > 1e-9
            and abs(float(value) - 0.5) > 1e-9
            and not ids
        ):
            errors.append(f"non_neutral_without_evidence:{predicate_id}")
    if seen != set(requested):
        errors.append("predicate_request_not_fully_covered")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def reviewer_tool() -> dict[str, Any]:
    properties = {
        "verdict": {"type": "string", "enum": sorted(REVIEW_VERDICTS), "description": "对当前 PSL 排名的反事实审核结论；不是 canonical 写入。"},
        "accepted_candidate_key": {"type": ["string", "null"], "description": "只能复制 supplied candidate_key；没有安全接受项时使用 JSON null，禁止字符串 null。"},
        "direct_identity_support": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "直接支持 mention=候选的 supplied evidence_id。"},
        "identity_contradictions": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "直接反对当前指派的 supplied evidence_id。"},
        "reason_types": {"type": "array", "items": {"type": "string", "enum": sorted(REVIEW_REASON_TYPES)}, "maxItems": 6, "description": "短机器可审计理由标签。"},
    }
    return {
        "type": "function",
        "function": {
            "name": REVIEW_FUNCTION_NAME,
            "description": "对 supplied PSL identity ranking 做 adversarial review；不得发明候选、证据或数据库 ID。",
            "strict": True,
            "parameters": {
                "type": "object",
                "description": "只返回结构化审核结论，所有证据必须来自 supplied evidence_ids。",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def reviewer_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": REVIEW_FUNCTION_NAME}}


REVIEW_SYSTEM_PROMPT = """你是 adversarial identity reviewer。只重读 supplied Story、annotation、candidate dossier、PSL ranking 和 evidence IDs。检查：证据是否具体支持 mention=候选；是否明确表明两者不同；PSL 是否把一般相容或关系路径误当身份；是否有 supplied alternative；证据是否不足。不要使用外部知识，不要发明人物或证据，不要把 confidence 当概率。只有 supplied evidence 直接支持时才 resolve；否则 retain_review、genuinely_unresolved 或 reject_top_candidate。"""


def reviewer_packet(case: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], graph: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    packet = wire_packet(case, cases, graph)
    packet["task"] = "adversarial review of one PSL1 identity ranking"
    packet["request_predicates"] = []
    safe_rankings = []
    for row in decision.get("candidate_rankings", []):
        safe_rankings.append({
            "candidate_key": row.get("candidate_key"),
            "candidate": row.get("candidate"),
            "link": row.get("link"),
            "raw_score": row.get("raw_score"),
            "supporting_predicates": [
                {key: value for key, value in item.items() if key in {"predicate", "value", "evidence_ids", "reason", "contribution", "other_mention_id", "other_candidate_key"}}
                for item in row.get("supporting_predicates", [])
            ],
            "contradicting_predicates": [
                {key: value for key, value in item.items() if key in {"predicate", "value", "evidence_ids", "reason", "contribution", "other_mention_id", "other_candidate_key"}}
                for item in row.get("contradicting_predicates", [])
            ],
            "hard_conflict": bool(row.get("hard_conflict")),
        })
    packet["psl_ranking"] = {
        "top_candidate_key": decision.get("top_candidate_key"),
        "margin": decision.get("margin"),
        "result_state": decision.get("result_state"),
        "candidate_rankings": safe_rankings,
    }
    packet["review_evidence_ids"] = sorted({str(row.get("evidence_id")) for row in packet.get("evidence_items", []) if row.get("evidence_id")})
    return packet


def validate_reviewer(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors = [f"forbidden_id_field:{path}" for path in _walk_forbidden(payload)]
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": sorted(set(["payload_not_object", *errors]))}
    expected = {"verdict", "accepted_candidate_key", "direct_identity_support", "identity_contradictions", "reason_types"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    verdict = payload.get("verdict")
    if verdict not in REVIEW_VERDICTS:
        errors.append("verdict_invalid")
    candidate_keys = {str(row.get("candidate_key")) for row in packet.get("candidates", [])}
    accepted = payload.get("accepted_candidate_key")
    if accepted == "null":
        errors.append("literal_null_invalid:accepted_candidate_key")
    if accepted is not None and not isinstance(accepted, str):
        errors.append("accepted_candidate_key_invalid")
    elif accepted is not None and accepted not in candidate_keys:
        errors.append("accepted_candidate_key_invalid")
    evidence = {str(value) for value in packet.get("review_evidence_ids", [])}
    for field in ("direct_identity_support", "identity_contradictions"):
        values = payload.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"{field}_invalid")
            values = []
        elif len(values) > 8:
            errors.append(f"{field}_too_many")
        for evidence_id in values:
            if evidence_id not in evidence:
                errors.append(f"evidence_reference_invalid:{field}:{evidence_id}")
    reasons = payload.get("reason_types")
    if not isinstance(reasons, list) or not all(value in REVIEW_REASON_TYPES for value in reasons):
        errors.append("reason_types_invalid")
    if verdict == "resolve" and (accepted is None or not payload.get("direct_identity_support")):
        errors.append("resolve_requires_direct_identity_support")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def _deterministic_rows(case: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(row) for row in case.get("deterministic_predicates", []) if str(row.get("candidate_key")) == key]


def _softmax(scores: Mapping[str, float], hard_vetoes: set[str]) -> dict[str, float]:
    viable = {key: score for key, score in scores.items() if key not in hard_vetoes}
    if not viable:
        return {key: 0.0 for key in scores}
    maximum = max(viable.values())
    exps = {key: math.exp(max(-40.0, min(40.0, value - maximum))) for key, value in viable.items()}
    total = sum(exps.values()) or 1.0
    return {key: (exps[key] / total if key in exps else 0.0) for key in scores}


def _value_for(rows: Sequence[Mapping[str, Any]], predicate: str, key: str) -> tuple[float, list[dict[str, Any]]]:
    found = [dict(row) for row in rows if str(row.get("predicate")) == predicate and str(row.get("candidate_key")) == key]
    return (float(found[-1].get("value", 0.5)) if found else 0.5), found


def _pair_value(rows: Sequence[Mapping[str, Any]], left: str, right: str) -> tuple[float, list[dict[str, Any]]]:
    values: list[dict[str, Any]] = []
    for row in rows:
        endpoints = {str(row.get("mention_id")), str(row.get("other_mention_id"))}
        if str(row.get("predicate")) == "Coreference" and endpoints == {left, right}:
            values.append(dict(row))
    return (float(values[-1].get("value", 0.5)) if values else 0.5), values


def _normalized_coreference(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[tuple[str, str], tuple[float, list[dict[str, Any]]]], list[dict[str, Any]]]:
    """Collapse Coreference to one canonical unordered variable per pair.

    A well-formed packet requests a pair only from its lexicographically first
    endpoint.  This second guard also protects offline replay or hand-built
    fixtures: contradictory duplicate orientations are excluded rather than
    allowed to exert asymmetric graph pressure.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        if str(row.get("predicate")) != "Coreference":
            continue
        left, right = sorted((str(row.get("mention_id")), str(row.get("other_mention_id"))))
        if not left or not right or left == right:
            continue
        grouped[(left, right)].append(dict(row))
    normalized: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
    conflicts: list[dict[str, Any]] = []
    for pair, values in sorted(grouped.items()):
        values.sort(key=lambda row: (str(row.get("predicate_id") or ""), stable_hash(row)))
        distinct_values = {round(float(row.get("value", 0.5)), 9) for row in values}
        if len(distinct_values) > 1:
            conflicts.append({
                "pair": list(pair),
                "predicate": "Coreference",
                "reason": "contradictory_duplicate_orientations",
                "rows": values,
            })
            continue
        evidence_ids = sorted({str(evidence_id) for row in values for evidence_id in row.get("evidence_ids", [])})
        normalized[pair] = (float(values[0].get("value", 0.5)), [{**values[0], "evidence_ids": evidence_ids}])
    return normalized, conflicts


def infer_graph(graph: Mapping[str, Any], llm_predicates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cases = [dict(row) for row in graph.get("cases", [])]
    case_by_id = {str(row.get("mention_id")): row for row in cases}
    llm_by_mention: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in llm_predicates:
        llm_by_mention[str(row.get("mention_id"))].append(dict(row))
    base_scores: dict[str, dict[str, float]] = {}
    vetoes: dict[str, set[str]] = {}
    traces: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for case in cases:
        mention_id = str(case.get("mention_id"))
        base_scores[mention_id] = {}
        vetoes[mention_id] = set(str(key) for key in (case.get("psl1_hard_vetoes") or {}))
        traces[mention_id] = collections.defaultdict(list)
        llm_rows = llm_by_mention.get(mention_id, [])
        for candidate in case.get("candidates", []):
            key = str(candidate.get("candidate_key"))
            base_scores[mention_id][key] = 0.0
            for deterministic in _deterministic_rows(case, key):
                predicate = str(deterministic.get("predicate"))
                value = float(deterministic.get("value", 0.5))
                if predicate == "TimeCompatible" and value <= 0:
                    vetoes[mention_id].add(key)
                # TimeCompatible and SameStory deliberately do not contribute
                # Link pressure in PSL1.
                if predicate in {"AliasMatch", "OfficeCompatible", "KinshipCompatible"}:
                    contribution = (value - 0.5) * 2.0 * RULE_WEIGHTS[predicate]
                    base_scores[mention_id][key] += contribution
                    traces[mention_id][key].append({**deterministic, "contribution": contribution})
            for row in llm_rows:
                if str(row.get("candidate_key")) != key or str(row.get("predicate")) not in {"IdentityContextSupport", "CrossStoryIdentitySupport", "IdentityContradiction"}:
                    continue
                predicate = str(row.get("predicate"))
                value = float(row.get("value", 0.5))
                contribution = max(0.0, value - 0.5) * 2.0 * RULE_WEIGHTS[predicate]
                # IdentityContradiction is a strength-of-contradiction
                # predicate, rather than a signed support value.  Only a
                # value above neutral suppresses a candidate; lack of a
                # contradiction is not positive identity evidence.
                if predicate == "IdentityContradiction":
                    contribution = max(0.0, value - 0.5) * 2.0 * RULE_WEIGHTS[predicate] * -1.0
                    if value >= 0.9 and row.get("evidence_ids"):
                        vetoes[mention_id].add(key)
                base_scores[mention_id][key] += contribution
                traces[mention_id][key].append({**row, "contribution": contribution})
    # Explicit local distinctness is a pair-level hard veto.  It never merely
    # penalizes a shared candidate: both mentions cannot link to the same
    # person.  If one side already has source-grounded identity support, keep
    # that supported side and veto the shared candidate only for the other
    # side.  This preserves an established ``劉尹 -> 劉惔`` mapping while
    # preventing ``王長史 -> 劉惔`` in 02-yanyu-054.  If neither side is
    # specifically supported (or both claim the same person), veto both and
    # leave the conflict for review rather than choosing by surface order.
    for pair in graph.get("distinct_pairs", []):
        left_id, right_id = str(pair.get("left_mention_id")), str(pair.get("right_mention_id"))
        left_case, right_case = case_by_id.get(left_id), case_by_id.get(right_id)
        if not left_case or not right_case:
            continue
        left_nodes = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in left_case.get("candidates", [])}
        right_nodes = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in right_case.get("candidates", [])}
        for node in set(left_nodes) & set(right_nodes):
            left_key, right_key = left_nodes[node], right_nodes[node]
            left_supported = any(
                str(row.get("predicate")) in DIRECT_IDENTITY_PREDICATES
                and float(row.get("value", 0.5)) > 0.5
                and bool(row.get("evidence_ids"))
                for row in traces[left_id].get(left_key, [])
            )
            right_supported = any(
                str(row.get("predicate")) in DIRECT_IDENTITY_PREDICATES
                and float(row.get("value", 0.5)) > 0.5
                and bool(row.get("evidence_ids"))
                for row in traces[right_id].get(right_key, [])
            )
            left_hard = left_key in vetoes[left_id]
            right_hard = right_key in vetoes[right_id]
            if left_supported and not right_supported and not left_hard:
                vetoes[right_id].add(right_key)
                traces[right_id][right_key].append({
                    "predicate": "Distinct",
                    "value": 1.0,
                    "evidence_ids": list(pair.get("evidence_ids", [])),
                    "other_mention_id": left_id,
                    "reason": pair.get("reason"),
                    "hard_veto": True,
                })
            elif right_supported and not left_supported and not right_hard:
                vetoes[left_id].add(left_key)
                traces[left_id][left_key].append({
                    "predicate": "Distinct",
                    "value": 1.0,
                    "evidence_ids": list(pair.get("evidence_ids", [])),
                    "other_mention_id": right_id,
                    "reason": pair.get("reason"),
                    "hard_veto": True,
                })
            else:
                vetoes[left_id].add(left_key)
                vetoes[right_id].add(right_key)
                for mention_id, key, other_id in ((left_id, left_key, right_id), (right_id, right_key, left_id)):
                    traces[mention_id][key].append({
                        "predicate": "Distinct",
                        "value": 1.0,
                        "evidence_ids": list(pair.get("evidence_ids", [])),
                        "other_mention_id": other_id,
                        "reason": pair.get("reason"),
                        "hard_veto": True,
                    })
    links = {mention_id: _softmax(scores, vetoes[mention_id]) for mention_id, scores in base_scores.items()}
    coref_values, coref_conflicts = _normalized_coreference(llm_predicates)
    known_edges: list[dict[str, Any]] = []
    for case in cases:
        known_edges.extend(dict(row) for row in case.get("known_relation_predicates", []))
    for _ in range(ITERATIONS):
        scores = {mention_id: dict(values) for mention_id, values in base_scores.items()}
        for (left_id, right_id), (value, _) in sorted(coref_values.items()):
            left_case, right_case = case_by_id.get(left_id), case_by_id.get(right_id)
            if not left_case or not right_case:
                continue
            left_nodes = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in left_case.get("candidates", [])}
            right_nodes = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in right_case.get("candidates", [])}
            for node in set(left_nodes) & set(right_nodes):
                left_key, right_key = left_nodes[node], right_nodes[node]
                scores[left_id][left_key] += (value - 0.5) * 2.0 * RULE_WEIGHTS["Coreference"] * links[right_id].get(right_key, 0.0)
                scores[right_id][right_key] += (value - 0.5) * 2.0 * RULE_WEIGHTS["Coreference"] * links[left_id].get(left_key, 0.0)
        for edge in known_edges:
            left_id, right_id = str(edge.get("mention_id")), str(edge.get("other_mention_id"))
            left_key, right_key = str(edge.get("candidate_key")), str(edge.get("other_candidate_key"))
            if left_id not in links or right_id not in links:
                continue
            scores[left_id][left_key] += RULE_WEIGHTS["KnownRelation"] * links[right_id].get(right_key, 0.0)
            scores[right_id][right_key] += RULE_WEIGHTS["KnownRelation"] * links[left_id].get(left_key, 0.0)
        links = {mention_id: _softmax(scores[mention_id], vetoes[mention_id]) for mention_id in scores}
    # Add collective traces after the final iteration for audit.  These are
    # predicate evidence traces, not materialized Relations.
    for (left_id, right_id), (value, evidence_rows) in sorted(coref_values.items()):
        left_case, right_case = case_by_id.get(left_id), case_by_id.get(right_id)
        if not left_case or not right_case or value <= 0.5:
            continue
        left_nodes = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in left_case.get("candidates", [])}
        right_nodes = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in right_case.get("candidates", [])}
        for node in set(left_nodes) & set(right_nodes):
            for mention_id, key in ((left_id, left_nodes[node]), (right_id, right_nodes[node])):
                traces[mention_id][key].append({
                    "predicate": "Coreference",
                    "value": value,
                    "evidence_ids": list(evidence_rows[0].get("evidence_ids", [])),
                    "contribution": (value - 0.5) * 2.0 * RULE_WEIGHTS["Coreference"],
                    "collective": True,
                    "other_mention_id": right_id if mention_id == left_id else left_id,
                })
    for edge in known_edges:
        left_id, right_id = str(edge.get("mention_id")), str(edge.get("other_mention_id"))
        left_key, right_key = str(edge.get("candidate_key")), str(edge.get("other_candidate_key"))
        if links.get(left_id, {}).get(left_key, 0.0) <= 0 or links.get(right_id, {}).get(right_key, 0.0) <= 0:
            continue
        for mention_id, key, other_id, other_key in ((left_id, left_key, right_id, right_key), (right_id, right_key, left_id, left_key)):
            traces[mention_id][key].append({
                "predicate": "KnownRelation",
                "value": 1.0,
                "evidence_ids": list(edge.get("evidence_ids", [])),
                "contribution": RULE_WEIGHTS["KnownRelation"] * links.get(other_id, {}).get(other_key, 0.0),
                "collective": True,
                "other_mention_id": other_id,
                "other_candidate_key": other_key,
            })
    records: list[dict[str, Any]] = []
    for case in cases:
        mention_id = str(case.get("mention_id"))
        candidates = {str(row.get("candidate_key")): row for row in case.get("candidates", [])}
        rankings: list[dict[str, Any]] = []
        for key, link in links.get(mention_id, {}).items():
            candidate = candidates[key]
            rows = list(traces[mention_id].get(key, []))
            supporting = [row for row in rows if str(row.get("predicate")) != "IdentityContradiction" and float(row.get("value", 0.5)) > 0.5]
            contradicting = [
                row for row in rows
                if (
                    str(row.get("predicate")) == "IdentityContradiction"
                    and float(row.get("value", 0.5)) > 0.5
                ) or (
                    str(row.get("predicate")) == "Coreference"
                    and float(row.get("value", 0.5)) < 0.5
                ) or (
                    str(row.get("predicate")) == "Distinct"
                    and float(row.get("value", 0.5)) > 0.5
                )
            ]
            rankings.append({
                "candidate_key": key,
                "candidate": candidate.get("display_name"),
                "candidate_person_id": candidate.get("person_id"),
                "candidate_node_id": candidate.get("candidate_node_id"),
                "link": round(float(link), 6),
                "raw_score": round(float(base_scores[mention_id].get(key, 0.0)), 6),
                "supporting_predicates": supporting,
                "contradicting_predicates": contradicting,
                "hard_conflict": key in vetoes.get(mention_id, set()),
            })
        rankings.sort(key=lambda row: (-float(row.get("link") or 0), -float(row.get("raw_score") or 0), str(row.get("candidate_key"))))
        viable = [row for row in rankings if not row.get("hard_conflict")]
        top = viable[0] if viable else None
        second = viable[1] if len(viable) > 1 else None
        margin = (float(top["link"]) - float(second["link"])) if top and second else (float(top["link"]) if top else 0.0)
        support_preds = [str(row.get("predicate")) for row in (top or {}).get("supporting_predicates", [])]
        direct = bool(set(support_preds) & DIRECT_IDENTITY_PREDICATES)
        relational = set(support_preds) & RELATIONAL_SUPPORT_FAMILIES
        strong = bool(
            top
            and float(top.get("link") or 0) >= HIGH_LINK_THRESHOLD
            and margin >= HIGH_MARGIN_THRESHOLD
            and float(top.get("raw_score") or 0) >= HIGH_RAW_SCORE_THRESHOLD
            and (direct or len(relational) >= 2)
            and not top.get("hard_conflict")
        )
        structural = str(case.get("psl_occurrence_type") or case.get("occurrence_type") or "") in COMPOSITIONAL_TYPES
        if strong and not structural:
            state = "stable_entity_resolved" if str(top.get("candidate_node_id") or "").startswith(("person:", "ruler:")) else "local_candidate_resolved"
        elif structural:
            state = "structural_reference"
        elif not top or float(top.get("link") or 0) < 0.45:
            state = "genuinely_unresolved"
        else:
            state = "review_required"
        collective = sorted(set(support_preds) & {"Coreference", "KnownRelation", "CrossStoryIdentitySupport"})
        records.append({
            "mention_id": mention_id,
            "occurrence_id": case.get("occurrence_id"),
            "story_id": case.get("story_id"),
            "surface": case.get("target_surface"),
            "current_status": case.get("current_status"),
            "occurrence_type": case.get("psl_occurrence_type") or case.get("occurrence_type"),
            "candidate_rankings": rankings,
            "top_candidate": top.get("candidate") if top else None,
            "top_candidate_key": top.get("candidate_key") if top else None,
            "top_candidate_person_id": top.get("candidate_person_id") if top else None,
            "margin": round(margin, 6),
            "result_state": state,
            "direct_identity_support": direct,
            "relational_support_families": sorted(relational),
            "collective_support_predicates": collective,
            "collective_gain_candidate": bool(state in {"stable_entity_resolved", "local_candidate_resolved"} and collective),
            "hard_veto_count": len(vetoes.get(mention_id, set())),
            "coreference_pair_conflicts": [row for row in coref_conflicts if mention_id in row.get("pair", [])],
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-decisions-v1",
        "selection_hash": graph.get("selection_hash"),
        "iterations": ITERATIONS,
        "rule_weights": RULE_WEIGHTS,
        "coreference_pair_conflicts": coref_conflicts,
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def apply_reviewer(decisions: Mapping[str, Any], reviewer_rows: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {str(row.get("mention_id")): dict(row) for row in reviewer_rows}
    case_by_id = {str(row.get("mention_id")): row for row in graph.get("cases", [])}
    result: list[dict[str, Any]] = []
    for original in decisions.get("records", []):
        row = dict(original)
        review = by_id.get(str(row.get("mention_id")))
        if not review or review.get("validation", {}).get("valid") is not True:
            result.append(row)
            continue
        payload = review.get("payload") or {}
        verdict = payload.get("verdict")
        accepted = payload.get("accepted_candidate_key")
        ranking = {str(item.get("candidate_key")): item for item in row.get("candidate_rankings", [])}
        safe_accept = accepted in ranking and not ranking[accepted].get("hard_conflict") and bool(payload.get("direct_identity_support"))
        if verdict in {"resolve", "reject_top_candidate"} and safe_accept:
            candidate = ranking[accepted]
            node = str(candidate.get("candidate_node_id") or "")
            row["top_candidate_key"] = accepted
            row["top_candidate"] = candidate.get("candidate")
            row["top_candidate_person_id"] = candidate.get("candidate_person_id")
            row["result_state"] = "stable_entity_resolved" if node.startswith(("person:", "ruler:")) else "local_candidate_resolved"
            row["reviewer_resolved"] = True
        elif verdict == "genuinely_unresolved":
            row["result_state"] = "genuinely_unresolved"
        row["reviewer_verdict"] = verdict
        row["reviewer_accepted_candidate_key"] = accepted
        row["reviewer_direct_identity_support"] = list(payload.get("direct_identity_support", []))
        row["reviewer_identity_contradictions"] = list(payload.get("identity_contradictions", []))
        row["reviewer_rejected_top_candidate"] = verdict == "reject_top_candidate"
        row["reviewer_reason_types"] = list(payload.get("reason_types", []))
        row["candidate_only"] = True
        row["canonical_write_back"] = False
        result.append(row)
    return {
        "schema": "hdb2-psl1-final-decisions-v1",
        "selection_hash": decisions.get("selection_hash"),
        "records": result,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def compare_regression(psl1: Mapping[str, Any], lj0_decisions: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    old = {str(row.get("occurrence_id")): row for row in lj0_decisions.get("records", [])}
    current = {str(row.get("occurrence_id")): row for row in graph.get("cases", [])}
    rows: list[dict[str, Any]] = []
    for row in psl1.get("records", []):
        occurrence_id = str(row.get("occurrence_id"))
        prior = old.get(occurrence_id, {})
        prior_resolved = str(prior.get("result_state")) == "high_confidence_contextual"
        now_resolved = str(row.get("result_state")) in {"stable_entity_resolved", "local_candidate_resolved"}
        rows.append({
            "occurrence_id": occurrence_id,
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "hdb2_current_status": current.get(occurrence_id, {}).get("current_status"),
            "lj0_state": prior.get("result_state"),
            "lj0_top_candidate": (prior.get("ranked_candidates") or [{}])[0].get("candidate") if prior.get("ranked_candidates") else None,
            "psl1_state": row.get("result_state"),
            "psl1_top_candidate": row.get("top_candidate"),
            "psl1_top_candidate_key": row.get("top_candidate_key"),
            "changed": prior_resolved != now_resolved or (prior.get("ranked_candidates") or [{}])[0].get("candidate") != row.get("top_candidate"),
            "change_reason": "resolved_status_changed" if prior_resolved != now_resolved else "top_candidate_or_threshold_changed",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-regression-comparison-v1",
        "records": rows,
        "lj0_resolved_count": sum(str(row.get("result_state")) == "high_confidence_contextual" for row in old.values()),
        "psl1_resolved_count": sum(str(row.get("result_state")) in {"stable_entity_resolved", "local_candidate_resolved"} for row in psl1.get("records", [])),
        "changed_count": sum(bool(row.get("changed")) for row in rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _state_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("result_state")) for row in records).items()))


def aggregate_metrics(
    *,
    regression_decisions: Mapping[str, Any],
    holdout_decisions: Mapping[str, Any],
    initial_regression: Mapping[str, Any],
    initial_holdout: Mapping[str, Any],
    reviewer_rows: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    validation_failures: Sequence[Mapping[str, Any]],
    graph_regression: Mapping[str, Any],
    graph_holdout: Mapping[str, Any],
    lj0_decisions: Mapping[str, Any],
) -> dict[str, Any]:
    all_final = [*regression_decisions.get("records", []), *holdout_decisions.get("records", [])]
    all_initial = [*initial_regression.get("records", []), *initial_holdout.get("records", [])]
    state_counts = collections.Counter(str(row.get("result_state")) for row in all_final)
    initial_counts = collections.Counter(str(row.get("result_state")) for row in all_initial)
    review_valid = [row for row in reviewer_rows if (row.get("validation") or {}).get("valid") is True]
    latencies = [float(row.get("elapsed_seconds") or 0) for row in call_records if row.get("elapsed_seconds") is not None]
    psl1_regression = {str(row.get("occurrence_id")): row for row in regression_decisions.get("records", [])}
    lj0_by_id = {str(row.get("occurrence_id")): row for row in lj0_decisions.get("records", [])}
    collective_gain = sum(
        str(row.get("result_state")) in {"stable_entity_resolved", "local_candidate_resolved"}
        and str(lj0_by_id.get(str(row.get("occurrence_id")), {}).get("result_state")) != "high_confidence_contextual"
        and bool(row.get("collective_gain_candidate"))
        for row in psl1_regression.values()
    )
    hard_veto_count = sum(int(row.get("hard_veto_count") or 0) for row in all_initial)
    contradiction_count = sum(
        1
        for row in all_initial
        for ranking in row.get("candidate_rankings", [])
        for predicate in ranking.get("contradicting_predicates", [])
        if str(predicate.get("predicate")) == "IdentityContradiction"
    )
    return {
        "schema": "hdb2-psl1-metrics-v1",
        "regression_count": len(regression_decisions.get("records", [])),
        "holdout_count": len(holdout_decisions.get("records", [])),
        "initial_result_states": _state_counts(all_initial),
        "result_states": dict(sorted(state_counts.items())),
        "stable_entity_resolved": state_counts.get("stable_entity_resolved", 0),
        "local_candidate_resolved": state_counts.get("local_candidate_resolved", 0),
        "review_required": state_counts.get("review_required", 0),
        "genuinely_unresolved": state_counts.get("genuinely_unresolved", 0),
        "structural_reference": state_counts.get("structural_reference", 0),
        "reviewer_resolved": sum(bool(row.get("reviewer_resolved")) for row in all_final),
        "reviewer_rejected_top_candidate": sum(bool(row.get("reviewer_rejected_top_candidate")) for row in all_final),
        "collective_gain": collective_gain,
        "candidate_recall": None,
        "candidate_recall_note": "No truth-labelled identity gold set is available; recall is not asserted.",
        "hard_veto_count": hard_veto_count,
        "llm_psl_contradiction_count": contradiction_count,
        "candidate_key_invalid": sum("candidate" in str(error).lower() and "invalid" in str(error).lower() for row in validation_failures for error in row.get("errors", [])),
        "evidence_reference_invalid": sum("evidence_reference_invalid" in str(error) for row in validation_failures for error in row.get("errors", [])),
        "validation_failures": len(validation_failures),
        "contextual_llm_calls": sum(str(row.get("call_type")) == "predicate_evaluation" for row in call_records),
        "reviewer_llm_calls": sum(str(row.get("call_type")) == "adversarial_review" for row in call_records),
        "llm_calls": len(call_records),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in call_records),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in call_records),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in call_records),
        "median_latency_seconds": __import__("statistics").median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "candidate_only": True,
        "canonical_write_back": False,
        "rule_weights": RULE_WEIGHTS,
        "iterations": ITERATIONS,
        "initial_review_count": sum(str(row.get("result_state")) == "review_required" for row in all_initial),
        "reviewer_cases": len(review_valid),
        "regression_initial_states": _state_counts(initial_regression.get("records", [])),
        "holdout_initial_states": _state_counts(initial_holdout.get("records", [])),
        "regression_final_states": _state_counts(regression_decisions.get("records", [])),
        "holdout_final_states": _state_counts(holdout_decisions.get("records", [])),
        "regression_graph_hard_vetoes": sum(len(row.get("psl1_hard_vetoes", {})) for row in graph_regression.get("cases", [])),
        "holdout_graph_hard_vetoes": sum(len(row.get("psl1_hard_vetoes", {})) for row in graph_holdout.get("cases", [])),
    }


def safety_metrics(graphs: Sequence[Mapping[str, Any]], decisions: Sequence[Mapping[str, Any]], validation_failures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # A surface may legitimately have several occurrence-local nodes.  The
    # safety condition is the opposite: one local node must not be reused by
    # multiple occurrences merely because their display surfaces match.
    local_node_mentions: dict[str, set[str]] = collections.defaultdict(set)
    case_by_id = {str(case.get("mention_id")): case for graph in graphs for case in graph.get("cases", [])}
    for graph in graphs:
        for case in graph.get("cases", []):
            for candidate in case.get("candidates", []):
                node = str(candidate.get("candidate_node_id") or "")
                if node.startswith("local:"):
                    local_node_mentions[node].add(str(case.get("mention_id")))
    shared_no_id_nodes = sum(len(mentions) > 1 for mentions in local_node_mentions.values())
    compositional = 0
    nonperson = 0
    self_relation_edges: set[tuple[str, str, str]] = set()
    for graph in graphs:
        for case in graph.get("cases", []):
            for edge in case.get("known_relation_predicates", []) or []:
                left_node = str(edge.get("candidate_node_id") or "")
                right_node = str(edge.get("other_candidate_node_id") or "")
                if left_node and left_node == right_node:
                    self_relation_edges.add((
                        str(case.get("mention_id")),
                        str(edge.get("other_mention_id")),
                        left_node,
                    ))
    self_relations = len(self_relation_edges)
    invalid_candidate_key_payloads = sum(
        any("candidate" in str(error).lower() and "invalid" in str(error).lower() for error in row.get("errors", []))
        for row in validation_failures
    )
    invalid_candidate_key_violations = sum(
        1
        for row in validation_failures
        for error in row.get("errors", [])
        if "candidate" in str(error).lower() and "invalid" in str(error).lower()
    )
    invalid_evidence_payloads = sum(
        1
        for row in validation_failures
        for error in row.get("errors", [])
        if "evidence_reference_invalid" in str(error)
    )
    for row in decisions:
        case = case_by_id.get(str(row.get("mention_id")), {})
        typ = str(case.get("psl_occurrence_type") or case.get("occurrence_type") or "")
        top = next((candidate for candidate in row.get("candidate_rankings", []) if candidate.get("candidate_key") == row.get("top_candidate_key")), None)
        if typ in COMPOSITIONAL_TYPES and top:
            base = matching(lj0._base_surface(str(case.get("target_surface") or "")))
            if base and matching(top.get("candidate")) == base:
                compositional += 1
        if typ in {"generic_or_non_person_reference", "not_person", "collective_persons"} and top and top.get("candidate_person_id"):
            nonperson += 1
        for ranking in row.get("candidate_rankings", []):
            for predicate in ranking.get("supporting_predicates", []):
                if str(predicate.get("predicate")) != "identity_equivalence" and ranking.get("candidate_person_id") and ranking.get("candidate_person_id") == row.get("top_candidate_person_id") and ranking.get("candidate_key") == row.get("top_candidate_key"):
                    # No relation is materialized by this module; this field
                    # remains a conservative audit placeholder.
                    pass
    return {
        "same_surface_automatic_merges": shared_no_id_nodes,
        "compositional_base_person_collapses": compositional,
        "nonperson_person_id_anomalies": nonperson,
        "non_identity_self_relations": self_relations,
        "hard_veto_promotions": sum(
            str(row.get("result_state")) in {"stable_entity_resolved", "local_candidate_resolved"}
            and any(bool(item.get("hard_conflict")) for item in row.get("candidate_rankings", []) if item.get("candidate_key") == row.get("top_candidate_key"))
            for row in decisions
        ),
        # These two fields describe rejected payloads for experiment
        # diagnostics.  Rejected model data is never fed to inference, so it
        # is not itself a safety violation or a false promotion.
        "invalid_candidate_key_payloads": invalid_candidate_key_payloads,
        "invalid_candidate_key_violations": invalid_candidate_key_violations,
        "invalid_evidence_reference_payloads": invalid_evidence_payloads,
        "invalid_candidate_keys": 0,
        "invalid_evidence_references": 0,
        "confidence_only_resolutions": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }
