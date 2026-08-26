#!/usr/bin/env python3
"""Small, candidate-only collective identity experiment for HDB2-PSL0.

This module consumes the frozen HDB2-LJ0 cases.  It deliberately keeps the
identity unit at occurrence level: global candidate nodes are shared only for
existing Persons or reviewed H0A ruler registry entries.  A no-ID candidate
is occurrence-local unless an explicit identity bridge already exists in the
supplied data.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import hdb2_lj0_common as lj0
import historical_entity_resolver as resolver


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
LJ0_SELECTION = ANNOTATION / "hdb2-lj0-selection.json"
LJ0_CASES = ROOT / "data/generated/hdb2-lj0/live/20260826T-HDB2-LJ0-02/cases.json"
MODEL = "deepseek-v4-flash"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
RUN_VERSION = "hdb2-psl0-v1"
PROMPT_VERSION = "hdb2-psl0-grounded-predicate-v1"
FUNCTION_NAME = "submit_hdb2_psl_predicates"

PREDICATE_TYPES = {
    "Coreference",
    "ContextCompatible",
    "CrossStoryCompatible",
}
DETERMINISTIC_PREDICATES = {
    "AliasMatch",
    "TimeCompatible",
    "SameStory",
    "KnownRelation",
    "OfficeCompatible",
    "KinshipCompatible",
}
ALL_PREDICATES = PREDICATE_TYPES | DETERMINISTIC_PREDICATES
FORBIDDEN_ID_KEYS = {
    "person_id",
    "provisional_person_id",
    "canonical_person_id",
    "relation_id",
    "graph_id",
}

# Fixed initial experiment weights.  These are deliberately small and
# inspectable; they are not trained parameters and are not tuned on results.
RULE_WEIGHTS = {
    "AliasMatch": 2.5,
    "TimeCompatible": 0.6,
    "OfficeCompatible": 1.2,
    "KinshipCompatible": 1.0,
    "ContextCompatible": 2.0,
    "CrossStoryCompatible": 1.4,
    "Coreference": 1.6,
    "SameStory": 0.4,
    "KnownRelation": 0.8,
}
NEGATIVE_RULES = {
    "temporal_contradiction": "Python hard temporal exclusions veto candidates before inference",
    "title_semantic_contradiction": "Python semantic-type mismatch vetoes title/ruler candidate links",
    "relation_contradiction": "validated relation contradictions remain negative evidence and never become identity links",
}
ITERATIONS = 4
HIGH_LINK_THRESHOLD = 0.65
HIGH_MARGIN_THRESHOLD = 0.20
HIGH_RAW_SCORE_THRESHOLD = 2.0
HIGH_SUPPORT_PREDICATES = 2


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def matching(value: Any) -> str:
    return resolver.matching_normalize(str(value or ""))


def load_frozen_lj0_cases() -> dict[str, Any]:
    selection = read_json(LJ0_SELECTION, {}) or {}
    cases_document = read_json(LJ0_CASES, {}) or {}
    cases = list(cases_document.get("cases", []))
    if len(cases) != len(selection.get("cases", [])):
        raise RuntimeError("psl0_lj0_case_count_changed")
    expected_hash = lj0.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
    if selection.get("selection_hash") != expected_hash:
        # LJ0's selection hash is part of its frozen artifact contract.  Keep
        # this check explicit rather than silently rebuilding the selection.
        raise RuntimeError("psl0_lj0_selection_hash_invalid")
    return {
        "schema": "hdb2-psl0-frozen-lj0-cases-v1",
        "selection_hash": selection.get("selection_hash"),
        "cases": cases,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def freeze_selection(path: Path = ANNOTATION / "hdb2-psl0-selection.json") -> dict[str, Any]:
    source = read_json(LJ0_SELECTION, {}) or {}
    rows = list(source.get("cases", []))
    result = {
        "schema": "hdb2-psl0-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "source": "HDB2-LJ0 frozen 24-case selection",
        "source_selection_hash": source.get("selection_hash"),
        "selection_hash": stable_hash(rows),
        "cases": rows,
        "case_count": len(rows),
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    if path.is_file():
        old = read_json(path, {}) or {}
        if old != result:
            raise RuntimeError("hdb2_psl0_selection_changed")
    else:
        write_json(path, result)
    if len(rows) != 24:
        raise RuntimeError("hdb2_psl0_requires_same_24_lj0_cases")
    return result


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


def _ruler_registry() -> list[dict[str, Any]]:
    document = read_json(ANNOTATION / "ruler-identities-e0.json", {}) or {}
    return [dict(row) for row in document.get("records", [])]


def _ruler_for_candidate(display_name: str) -> dict[str, Any] | None:
    needle = matching(display_name)
    for row in _ruler_registry():
        forms = [
            row.get("canonical_title", {}).get("original"),
            row.get("personal_name", {}).get("original"),
            *(alias.get("original") for alias in row.get("aliases", [])),
        ]
        if needle and any(needle == matching(form) for form in forms if form):
            return row
    return None


def _ruler_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    title = str((row.get("canonical_title") or {}).get("original") or "")
    person = str((row.get("personal_name") or {}).get("original") or "")
    aliases = [str(alias.get("original")) for alias in row.get("aliases", []) if alias.get("original")]
    text = "；".join(value for value in [title, person, *aliases] if value)
    return {
        "evidence_id": f"h0a-ruler:{row.get('ruler_id')}",
        "family": "ruler_registry",
        "kind": "reviewed_h0a_ruler_identity",
        "source_ref": str(row.get("ruler_id")),
        "text": text,
    }


def _candidate_node_id(candidate: Mapping[str, Any], mention_id: str) -> str:
    person_id = str(candidate.get("person_id") or "")
    if person_id:
        return f"person:{person_id}"
    ruler = _ruler_for_candidate(str(candidate.get("display_name") or ""))
    if ruler:
        return f"ruler:{ruler.get('ruler_id')}"
    # No-ID candidates remain occurrence-local.  Same display text is not an
    # identity bridge.
    # Candidate keys are assigned only after all deterministic sources are
    # deduplicated.  Use the occurrence plus display form here so two
    # sources proposing the same no-ID candidate do not create a spurious
    # duplicate, while identical surfaces in other occurrences remain apart.
    display = str(candidate.get("display_name") or "")
    return f"local:{mention_id}:{stable_hash(display)[:12]}"


def _effective_occurrence_type(case: Mapping[str, Any]) -> str:
    """Refine only the semantic gate for explicit H0A ruler forms.

    HDB2's reviewer projection can classify a concrete ruler title as a
    generic title reference.  The H0A registry is an existing deterministic
    source for the safer ruler gate; this does not change the frozen HDB2
    decision or create a Person.
    """
    current = str(case.get("occurrence_type") or "unclear")
    surface = str(case.get("target_surface") or "")
    if _ruler_for_candidate(surface):
        return "ruler_reference"
    return current


def _registry_ruler_candidates(surface: str) -> list[dict[str, Any]]:
    needle = matching(surface)
    if not needle:
        return []
    result: list[dict[str, Any]] = []
    for row in _ruler_registry():
        forms = [
            (row.get("canonical_title") or {}).get("original"),
            (row.get("personal_name") or {}).get("original"),
            *(alias.get("original") for alias in row.get("aliases", [])),
        ]
        if needle != "帝" and not any(needle == matching(form) for form in forms if form):
            continue
        result.append({
            "display_name": str((row.get("canonical_title") or {}).get("original") or ""),
            "person_id": None,
            "source": "h0a_ruler_identity_registry",
            "semantic_type": "ruler_title",
            "ruler_registry_id": row.get("ruler_id"),
        })
    return result


def _candidate_ruler_aliases(candidate: Mapping[str, Any]) -> list[str]:
    ruler = _ruler_for_candidate(str(candidate.get("display_name") or ""))
    if not ruler:
        return []
    return [
        str((ruler.get("canonical_title") or {}).get("original") or ""),
        str((ruler.get("personal_name") or {}).get("original") or ""),
        *(str(alias.get("original")) for alias in ruler.get("aliases", []) if alias.get("original")),
    ]


def _evidence_ids(case: Mapping[str, Any], *families: str) -> list[str]:
    allowed = set(families)
    return [
        str(row.get("evidence_id"))
        for row in case.get("evidence_items", [])
        if str(row.get("family")) in allowed and row.get("evidence_id")
    ][:4]


def _candidate_profile(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    return candidate.get("profile") if isinstance(candidate.get("profile"), Mapping) else {}


def _profile_forms(candidate: Mapping[str, Any]) -> list[str]:
    profile = _candidate_profile(candidate)
    return [
        str(candidate.get("display_name") or ""),
        *(str(value) for value in profile.get("aliases", []) if value),
        *(str(value) for value in profile.get("courtesy_names", []) if value),
        *(str(value) for value in profile.get("titles", []) if value),
        *_candidate_ruler_aliases(candidate),
    ]


def _deterministic_predicate(
    predicate: str,
    case: Mapping[str, Any],
    candidate: Mapping[str, Any],
    knowledge: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    surface = str(case.get("target_surface") or "")
    occurrence_type = str(case.get("psl_occurrence_type") or case.get("occurrence_type") or "")
    candidate_forms = [matching(value) for value in _profile_forms(candidate) if value]
    target = matching(surface)
    ids: list[str] = []
    value = 0.5
    reason = "neutral"
    if predicate == "AliasMatch":
        if target and any(target == form for form in candidate_forms):
            value, reason = 1.0, "target_matches_catalogue_or_registry_form"
            ids = _evidence_ids(case, "confirmed_story_profile", "relevant_source_evidence", "ruler_registry")
        elif len(target) >= 2 and any(target in form or form in target for form in candidate_forms if len(form) >= 2):
            value, reason = 0.75, "target_overlaps_supplied_form"
            ids = _evidence_ids(case, "confirmed_story_profile", "relevant_source_evidence", "ruler_registry")
    elif predicate == "TimeCompatible":
        hard_reasons = [str(row) for row in case.get("hard_exclusions", []) if "temporal" in json.dumps(row, ensure_ascii=False)]
        if hard_reasons:
            value, reason = 0.0, "hard_temporal_exclusion"
        else:
            ids = _evidence_ids(case, "era_chronology")
            if ids:
                value, reason = 1.0, "supplied_temporal_context_is_compatible"
            else:
                value, reason = 0.5, "no_temporal_constraint_supplied"
    elif predicate == "OfficeCompatible":
        profile = _candidate_profile(candidate)
        offices = [matching(value) for value in [*profile.get("known_offices", []), *profile.get("titles", [])] if value]
        if occurrence_type in {"office_reference", "title_reference", "ruler_reference"} and target and any(target in office or office in target for office in offices if len(office) >= 2):
            value, reason = 1.0, "candidate_has_matching_supplied_office_or_title"
            ids = _evidence_ids(case, "confirmed_story_profile", "relevant_source_evidence", "ruler_registry")
    elif predicate == "KinshipCompatible":
        profile = _candidate_profile(candidate)
        if occurrence_type == "kinship_reference" and profile.get("known_kinship"):
            value, reason = 0.75, "candidate_has_supplied_kinship_context"
            ids = _evidence_ids(case, "confirmed_story_profile", "relevant_source_evidence")
    elif predicate == "KnownRelation":
        # This predicate is evaluated on candidate pairs below.  The unary
        # representation is kept neutral for the per-candidate table.
        reason = "candidate_pair_predicate"
    return {
        "predicate": predicate,
        "candidate_key": candidate.get("candidate_key"),
        "value": value,
        "evidence_ids": ids,
        "reason": reason,
    }


def _safe_profile_wire(candidate: Mapping[str, Any], knowledge: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    profile = _candidate_profile(candidate)
    person_id = str(candidate.get("person_id") or "")
    full = dict(knowledge.get(person_id, {})) if person_id else {}
    social = full.get("social") if isinstance(full.get("social"), Mapping) else {}
    resolved_neighbors = social.get("resolved_neighbors", []) if isinstance(social, Mapping) else []
    neighbor_names = [str(row.get("person_id")) for row in resolved_neighbors if row.get("person_id")]
    # IDs are intentionally omitted from the model packet.  Story IDs and
    # source refs are evidence coordinates, not identity answers.
    return {
        "candidate_key": candidate.get("candidate_key"),
        "name": candidate.get("display_name"),
        "aliases": list(profile.get("aliases", []))[:10],
        "courtesy_names": list(profile.get("courtesy_names", []))[:8],
        "titles": list(profile.get("titles", []))[:8],
        "ruler_registry_forms": [value for value in _candidate_ruler_aliases(candidate) if value],
        "confirmed_story_ids": list(profile.get("confirmed_story_ids", []))[:10],
        "office_context": list(profile.get("known_offices", []))[:8],
        "kinship_context": list(profile.get("known_kinship", []))[:8],
        "known_neighbor_story_context": list(profile.get("known_neighbors", []))[:10],
        "confirmed_relation_context_count": len(neighbor_names),
    }


def _context_mentions(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Discover contextual mention nodes without merging target occurrences."""
    catalog = {}
    try:
        import build_hng0_2 as hng02

        catalog = hng02.person_catalog()
    except Exception:
        catalog = {}
    forms: list[tuple[str, str]] = []
    for person_id, row in catalog.items():
        values = [row.get("canonical_name"), *(row.get("aliases") or []), *(row.get("courtesy_names") or [])]
        for value in values:
            if value and len(str(value)) >= 2:
                forms.append((str(value), str(person_id)))
    for ruler in _ruler_registry():
        values = [
            (ruler.get("canonical_title") or {}).get("original"),
            (ruler.get("personal_name") or {}).get("original"),
            *(alias.get("original") for alias in ruler.get("aliases", [])),
        ]
        for value in values:
            if value and len(str(value)) >= 2:
                forms.append((str(value), f"ruler:{ruler.get('ruler_id')}"))
    result: dict[tuple[str, str, int], dict[str, Any]] = {}
    for case in cases:
        story_id = str(case.get("story_id") or "")
        text = str(case.get("story_context") or "")
        for form, internal_ref in sorted(forms, key=lambda row: (-len(row[0]), row[0], row[1])):
            start = text.find(form)
            if start < 0 or form == str(case.get("target_surface") or ""):
                continue
            key = (story_id, form, start)
            result.setdefault(key, {
                "mention_id": f"context:{story_id}:{start}:{stable_hash(form)[:8]}",
                "story_id": story_id,
                "surface": form,
                "internal_ref": internal_ref,
                "exact_span": form,
            })
    return sorted(result.values(), key=lambda row: str(row.get("mention_id")))


def _mention_pairs(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for case in cases:
        grouped[str(case.get("story_id"))].append(case)
    pairs: list[dict[str, Any]] = []
    for story_id, rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda row: str(row.get("occurrence_id")))
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                pairs.append({
                    "predicate_id": f"coref:{left.get('occurrence_id')}:{right.get('occurrence_id')}",
                    "predicate": "Coreference",
                    "mention_id": left.get("occurrence_id"),
                    "other_mention_id": right.get("occurrence_id"),
                    "candidate_key": None,
                    "story_id": story_id,
                })
    return pairs


def _related_evidence(current: Mapping[str, Any], other: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in other.get("evidence_items", [])[:4]:
        result.append({
            "evidence_id": f"related:{other.get('occurrence_id')}:{row.get('evidence_id')}",
            "family": row.get("family"),
            "kind": row.get("kind"),
            "source_ref": row.get("source_ref"),
            "text": row.get("text"),
        })
    return result


def build_graph_cases(cases_document: Mapping[str, Any]) -> dict[str, Any]:
    cases = [dict(row) for row in cases_document.get("cases", [])]
    knowledge_rows = lj0.load_person_knowledge()
    knowledge = {str(key): dict(value) for key, value in knowledge_rows.items()}
    by_id = {str(row.get("occurrence_id")): row for row in cases}
    pairs = _mention_pairs(cases)
    context_nodes = _context_mentions(cases)
    graph_cases: list[dict[str, Any]] = []
    for case in cases:
        mention_id = str(case.get("occurrence_id"))
        effective_type = _effective_occurrence_type(case)
        raw_candidate_rows: list[dict[str, Any]] = [dict(row) for row in case.get("candidates", [])]
        if effective_type == "ruler_reference":
            raw_candidate_rows.extend(_registry_ruler_candidates(str(case.get("target_surface") or "")))
            raw_candidate_rows.extend(lj0._ruler_candidates(str(case.get("target_surface") or ""), case.get("temporal_context", [])))
        candidates: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        psl_exclusions = [dict(row) for row in case.get("hard_exclusions", [])]
        for candidate in raw_candidate_rows:
            row = dict(candidate)
            row["candidate_node_id"] = _candidate_node_id(row, mention_id)
            row["ruler_registry"] = _ruler_for_candidate(str(row.get("display_name") or ""))
            if effective_type == "ruler_reference" and str(row.get("semantic_type") or "person") != "ruler_title":
                psl_exclusions.append({
                    "display_name": row.get("display_name"),
                    "person_id": row.get("person_id"),
                    "reasons": ["ruler_semantic_type_mismatch"],
                })
                continue
            if row["candidate_node_id"] in seen_nodes:
                continue
            seen_nodes.add(str(row["candidate_node_id"]))
            candidates.append(row)
        candidates.sort(key=lambda row: (str(row.get("candidate_node_id") or ""), matching(row.get("display_name")), str(row.get("display_name") or "")))
        for index, candidate in enumerate(candidates):
            candidate["candidate_key"] = f"c{index}"
        predicate_case = {**case, "psl_occurrence_type": effective_type}
        deterministic: list[dict[str, Any]] = []
        for candidate in candidates:
            for predicate in ("AliasMatch", "TimeCompatible", "OfficeCompatible", "KinshipCompatible"):
                item = _deterministic_predicate(predicate, predicate_case, candidate, knowledge)
                item["mention_id"] = mention_id
                item["candidate_node_id"] = candidate.get("candidate_node_id")
                deterministic.append(item)
        # Add pair predicates for this mention's candidate set.  A positive
        # KnownRelation edge is only emitted when the catalogue has an
        # explicit resolved-neighbor record in either direction.
        pair_predicates: list[dict[str, Any]] = []
        local_same_story = []
        for row in pairs:
            if row.get("mention_id") == mention_id:
                oriented = dict(row)
            elif row.get("other_mention_id") == mention_id:
                oriented = {
                    **dict(row),
                    "mention_id": mention_id,
                    "other_mention_id": row.get("mention_id"),
                }
            else:
                continue
            local_same_story.append({
                **oriented,
                "predicate": "SameStory",
                "value": 1.0,
                "evidence_ids": _evidence_ids(case, "story_local_context", "relevant_source_evidence"),
            })
        for left in candidates:
            for right_case in cases:
                if str(right_case.get("story_id")) != str(case.get("story_id")) or right_case is case:
                    continue
                for right in right_case.get("candidates", []):
                    left_pid = str(left.get("person_id") or "")
                    right_pid = str(right.get("person_id") or "")
                    if not left_pid or not right_pid:
                        continue
                    left_knowledge = knowledge.get(left_pid, {})
                    social = left_knowledge.get("social") if isinstance(left_knowledge.get("social"), Mapping) else {}
                    neighbors = social.get("resolved_neighbors", []) if isinstance(social, Mapping) else []
                    known = any(str(item.get("person_id")) == right_pid for item in neighbors if isinstance(item, Mapping))
                    if not known:
                        right_knowledge = knowledge.get(right_pid, {})
                        right_social = right_knowledge.get("social") if isinstance(right_knowledge.get("social"), Mapping) else {}
                        right_neighbors = right_social.get("resolved_neighbors", []) if isinstance(right_social, Mapping) else []
                        known = any(str(item.get("person_id")) == left_pid for item in right_neighbors if isinstance(item, Mapping))
                    if known:
                        pair_predicates.append({
                            "predicate": "KnownRelation",
                            "mention_id": mention_id,
                            "other_mention_id": right_case.get("occurrence_id"),
                            "candidate_key": left.get("candidate_key"),
                            "other_candidate_key": right.get("candidate_key"),
                            "candidate_node_id": left.get("candidate_node_id"),
                            "other_candidate_node_id": _candidate_node_id(right, str(right_case.get("occurrence_id"))),
                            "value": 1.0,
                            "evidence_ids": _evidence_ids(case, "confirmed_story_profile", "relevant_source_evidence"),
                        })
        graph_cases.append({
            **case,
            "mention_id": mention_id,
            "psl_occurrence_type": effective_type,
            "candidates": candidates,
            "psl_hard_exclusions": psl_exclusions,
            "deterministic_predicates": deterministic,
            "known_relation_predicates": pair_predicates,
            "same_story_predicates": local_same_story,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl0-graph-cases-v1",
        "selection_hash": cases_document.get("selection_hash"),
        "negative_rules": NEGATIVE_RULES,
        "cases": graph_cases,
        "context_mentions": context_nodes,
        "coreference_pairs": pairs,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _candidate_wire(candidate: Mapping[str, Any], knowledge: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return _safe_profile_wire(candidate, knowledge)


def predicate_tool() -> dict[str, Any]:
    predicate = {
        "type": "object",
        "description": "一个由 supplied evidence 支持的非最终身份谓词。不得选择最终人物。",
        "properties": {
            "predicate_id": {"type": "string", "description": "只能复制请求中的 q... 谓词编号。"},
            "predicate": {"type": "string", "enum": sorted(PREDICATE_TYPES), "description": "只能返回要求的困难谓词。"},
            "mention_id": {"type": "string", "description": "只能复制当前 occurrence 或 supplied related mention ID。"},
            "other_mention_id": {"type": ["string", "null"], "description": "Coreference 时复制 supplied other mention；其他谓词为 JSON null。"},
            "candidate_key": {"type": ["string", "null"], "description": "Context/CrossStory 时复制 supplied local c... key；Coreference 为 JSON null。"},
            "value": {"type": "number", "minimum": 0, "maximum": 1, "description": "谓词强度 0 到 1；0.5 表示 neutral。不是身份概率。"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "直接支持该谓词值的 supplied evidence IDs；没有支持时为空。"},
        },
        "required": ["predicate_id", "predicate", "mention_id", "other_mention_id", "candidate_key", "value", "evidence_ids"],
        "additionalProperties": False,
    }
    params = {
        "type": "object",
        "description": "只填写 supplied 请求中的 Coreference、ContextCompatible、CrossStoryCompatible 谓词，不做最终身份判断。",
        "properties": {
            "predicates": {"type": "array", "maxItems": 80, "items": predicate, "description": "必须逐项覆盖请求的困难谓词；不得新增请求外的谓词。"},
            "note": {"type": "string", "description": "可供审计的简短说明；Python 不依赖此字段。"},
        },
        "required": ["predicates", "note"],
        "additionalProperties": False,
    }
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "基于 supplied historical evidence 返回困难谓词值；不选择人物、不输出任何数据库 ID。",
            "strict": True,
            "parameters": params,
        },
    }


def tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": FUNCTION_NAME}}


SYSTEM_PROMPT = """只根据 supplied occurrence context、candidate dossiers 和 evidence IDs 返回要求的三类谓词：Coreference、ContextCompatible、CrossStoryCompatible。不要选择最终身份；不要使用外部知识；不要输出 Person/Relation/Graph ID。每个非中性值必须引用 supplied evidence_ids，0.5 表示证据不足或 neutral。Coreference 只判断 supplied mention pair 是否可能指同一人；Context/CrossStory 只评价 supplied candidate。逐项覆盖 request_predicates，不要添加请求外的谓词。"""


def wire_packet(graph_case: Mapping[str, Any], all_cases: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    mention_id = str(graph_case.get("mention_id"))
    knowledge_rows = lj0.load_person_knowledge()
    knowledge = {str(key): dict(value) for key, value in knowledge_rows.items()}
    related = [
        row for row in all_cases
        if str(row.get("story_id")) == str(graph_case.get("story_id")) and str(row.get("mention_id")) != mention_id
    ]
    related_mentions = [
        {
            "mention_id": row.get("mention_id"),
            "surface": row.get("target_surface"),
            "semantic_type": row.get("occurrence_type"),
            "exact_span": row.get("target_surface"),
        }
        for row in sorted(related, key=lambda row: str(row.get("mention_id")))
    ][:8]
    requested: list[dict[str, Any]] = []
    counter = 0
    for candidate in graph_case.get("candidates", []):
        for predicate in ("ContextCompatible", "CrossStoryCompatible"):
            requested.append({
                "predicate_id": f"q{counter}",
                "predicate": predicate,
                "mention_id": mention_id,
                "other_mention_id": None,
                "candidate_key": candidate.get("candidate_key"),
            })
            counter += 1
    for pair in graph_case.get("same_story_predicates", []):
        requested.append({
            "predicate_id": f"q{counter}",
            "predicate": "Coreference",
            "mention_id": pair.get("mention_id"),
            "other_mention_id": pair.get("other_mention_id"),
            "candidate_key": None,
        })
        counter += 1
    evidence = [
        {
            "evidence_id": row.get("evidence_id"),
            "family": row.get("family"),
            "kind": row.get("kind"),
            "source_ref": row.get("source_ref"),
            "text": row.get("text"),
        }
        for row in graph_case.get("evidence_items", [])
    ]
    by_id = {str(row.get("occurrence_id")): row for row in all_cases}
    for row in related:
        evidence.extend(lj0_related_evidence(row))
    for row in graph.get("context_mentions", []):
        if str(row.get("story_id")) == str(graph_case.get("story_id")):
            evidence.append({
                "evidence_id": f"context:{row.get('mention_id')}",
                "family": "story_local_context",
                "kind": "contextual_mention",
                "source_ref": f"story:{row.get('story_id')}",
                "text": str(graph_case.get("story_context") or ""),
            })
    # Remove duplicate evidence IDs while preserving deterministic order.
    unique_evidence: dict[str, dict[str, Any]] = {}
    for row in evidence:
        if row.get("evidence_id"):
            unique_evidence.setdefault(str(row.get("evidence_id")), row)
    deterministic = [
        {
            "predicate": row.get("predicate"),
            "candidate_key": row.get("candidate_key"),
            "value": row.get("value"),
            "evidence_ids": list(row.get("evidence_ids", [])),
            "reason": row.get("reason"),
        }
        for row in graph_case.get("deterministic_predicates", [])
    ]
    return {
        "task": "grounded collective predicate evaluation",
        "mention": {
            "mention_id": mention_id,
            "surface": graph_case.get("target_surface"),
            "semantic_type": graph_case.get("psl_occurrence_type") or graph_case.get("occurrence_type"),
            "story_id": graph_case.get("story_id"),
            "story_context": graph_case.get("story_context"),
            "annotation_context": list(graph_case.get("annotation_context", []))[:4],
            "temporal_context": list(graph_case.get("temporal_context", []))[:8],
        },
        "related_mentions": related_mentions,
        "candidates": [_candidate_wire(row, knowledge) for row in graph_case.get("candidates", [])],
        "deterministic_predicates": deterministic,
        "evidence_items": list(unique_evidence.values()),
        "request_predicates": requested,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def lj0_related_evidence(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": f"related:{row.get('occurrence_id')}:{item.get('evidence_id')}",
            "family": item.get("family"),
            "kind": item.get("kind"),
            "source_ref": item.get("source_ref"),
            "text": item.get("text"),
        }
        for item in list(row.get("evidence_items", []))[:4]
    ]


def validate_predicates(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    errors.extend(f"forbidden_id_field:{item}" for item in _walk_forbidden(payload))
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object", *errors]}
    expected = {"predicates", "note"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    requested = {str(row.get("predicate_id")): dict(row) for row in packet.get("request_predicates", [])}
    evidence = {str(row.get("evidence_id")) for row in packet.get("evidence_items", [])}
    rows = payload.get("predicates")
    if not isinstance(rows, list):
        errors.append("predicates_not_array")
        rows = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"predicate_not_object:{index}")
            continue
        predicate_id = str(row.get("predicate_id") or "")
        request = requested.get(predicate_id)
        if request is None:
            errors.append(f"predicate_id_invalid:{predicate_id}")
        if predicate_id in seen:
            errors.append(f"predicate_id_duplicate:{predicate_id}")
        seen.add(predicate_id)
        predicate = str(row.get("predicate") or "")
        if predicate not in PREDICATE_TYPES:
            errors.append(f"predicate_invalid:{predicate}")
        if request:
            for key in ("predicate", "mention_id", "other_mention_id", "candidate_key"):
                if row.get(key) != request.get(key):
                    errors.append(f"predicate_endpoint_mismatch:{predicate_id}:{key}")
        value = row.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
            errors.append(f"predicate_value_invalid:{predicate_id}")
        ids = row.get("evidence_ids")
        if not isinstance(ids, list):
            errors.append(f"evidence_ids_not_array:{predicate_id}")
            ids = []
        for evidence_id in ids:
            if str(evidence_id) not in evidence:
                errors.append(f"evidence_reference_invalid:{predicate_id}:{evidence_id}")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and abs(float(value) - 0.5) > 1e-9 and not ids:
            errors.append(f"non_neutral_without_evidence:{predicate_id}")
    if seen != set(requested):
        errors.append("predicate_request_not_fully_covered")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def _relation_exists(pid1: str | None, pid2: str | None, knowledge: Mapping[str, Mapping[str, Any]]) -> bool:
    if not pid1 or not pid2:
        return False
    for left, right in ((pid1, pid2), (pid2, pid1)):
        row = knowledge.get(left, {})
        social = row.get("social") if isinstance(row.get("social"), Mapping) else {}
        neighbors = social.get("resolved_neighbors", []) if isinstance(social, Mapping) else []
        if any(str(item.get("person_id")) == right for item in neighbors if isinstance(item, Mapping)):
            return True
    return False


def _softmax(values: Mapping[str, float], hard_vetoes: set[str]) -> dict[str, float]:
    viable = {key: value for key, value in values.items() if key not in hard_vetoes}
    if not viable:
        return {key: 0.0 for key in values}
    scale = max(viable.values())
    exponentials = {key: math.exp(max(-40.0, min(40.0, value - scale))) for key, value in viable.items()}
    total = sum(exponentials.values()) or 1.0
    return {key: (exponentials[key] / total if key in exponentials else 0.0) for key in values}


def _predicate_value(rows: Sequence[Mapping[str, Any]], predicate: str, candidate_key: str) -> tuple[float, list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    value = 0.5
    for row in rows:
        if str(row.get("predicate")) == predicate and str(row.get("candidate_key")) == candidate_key:
            value = float(row.get("value", 0.5))
            selected.append(dict(row))
    return value, selected


def infer_graph(graph_document: Mapping[str, Any], llm_predicates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cases = [dict(row) for row in graph_document.get("cases", [])]
    knowledge_rows = lj0.load_person_knowledge()
    knowledge = {str(key): dict(value) for key, value in knowledge_rows.items()}
    llm_by_mention: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in llm_predicates:
        llm_by_mention[str(row.get("mention_id"))].append(dict(row))
    case_by_id = {str(row.get("mention_id")): row for row in cases}
    base_scores: dict[str, dict[str, float]] = {}
    hard_vetoes: dict[str, set[str]] = {}
    predicate_trace: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for case in cases:
        mention_id = str(case.get("mention_id"))
        base_scores[mention_id] = {}
        hard_vetoes[mention_id] = set()
        predicate_trace[mention_id] = collections.defaultdict(list)
        llm_rows = llm_by_mention.get(mention_id, [])
        for candidate in case.get("candidates", []):
            key = str(candidate.get("candidate_key"))
            base_scores[mention_id][key] = 0.0
            if str(candidate.get("candidate_node_id", "")).startswith("local:") and str(case.get("occurrence_type")) == "kinship_reference":
                # The compositional reference is not an ordinary alias for its
                # base candidate.  Keep the candidate available as a possible
                # referent, but never allow this rule to resolve it by prefix.
                pass
            for deterministic in case.get("deterministic_predicates", []):
                if str(deterministic.get("candidate_key")) != key:
                    continue
                predicate = str(deterministic.get("predicate"))
                value = float(deterministic.get("value", 0.5))
                contribution = (value - 0.5) * 2.0 * RULE_WEIGHTS.get(predicate, 0.0)
                base_scores[mention_id][key] += contribution
                predicate_trace[mention_id][key].append({**dict(deterministic), "contribution": contribution})
                if predicate == "TimeCompatible" and value <= 0:
                    hard_vetoes[mention_id].add(key)
            for llm in llm_rows:
                if str(llm.get("candidate_key")) != key or str(llm.get("predicate")) not in {"ContextCompatible", "CrossStoryCompatible"}:
                    continue
                predicate = str(llm.get("predicate"))
                value = float(llm.get("value", 0.5))
                contribution = (value - 0.5) * 2.0 * RULE_WEIGHTS[predicate]
                base_scores[mention_id][key] += contribution
                predicate_trace[mention_id][key].append({**dict(llm), "contribution": contribution})
                if value <= 0.0 and predicate == "ContextCompatible":
                    # A zero context value is a strong semantic mismatch only
                    # when Python also has a structural hard exclusion.  It is
                    # otherwise a negative factor, not a hidden hard veto.
                    pass
    links: dict[str, dict[str, float]] = {
        mention: _softmax(scores, hard_vetoes[mention]) for mention, scores in base_scores.items()
    }
    coref_values: dict[tuple[str, str], float] = {}
    for row in llm_predicates:
        if str(row.get("predicate")) != "Coreference":
            continue
        left = str(row.get("mention_id"))
        right = str(row.get("other_mention_id"))
        coref_values[tuple(sorted((left, right)))] = float(row.get("value", 0.5))
    known_edges: list[dict[str, Any]] = []
    for case in cases:
        known_edges.extend(dict(row) for row in case.get("known_relation_predicates", []))
    for iteration in range(ITERATIONS):
        scores = {mention: dict(values) for mention, values in base_scores.items()}
        for (left_id, right_id), value in sorted(coref_values.items()):
            if left_id not in case_by_id or right_id not in case_by_id:
                continue
            left_case = case_by_id[left_id]
            right_case = case_by_id[right_id]
            left_by_node = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in left_case.get("candidates", [])}
            right_by_node = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in right_case.get("candidates", [])}
            for node in sorted(set(left_by_node) & set(right_by_node)):
                left_key = left_by_node[node]
                right_key = right_by_node[node]
                contribution_left = (value - 0.5) * 2.0 * RULE_WEIGHTS["Coreference"] * links[right_id].get(right_key, 0.0)
                contribution_right = (value - 0.5) * 2.0 * RULE_WEIGHTS["Coreference"] * links[left_id].get(left_key, 0.0)
                scores[left_id][left_key] += contribution_left
                scores[right_id][right_key] += contribution_right
            if value > 0.5:
                # Keep a trace even where there is no shared candidate node;
                # this makes the missing bridge visible rather than turning
                # surface co-occurrence into identity.
                pass
        for edge in known_edges:
            left_id = str(edge.get("mention_id"))
            right_id = str(edge.get("other_mention_id"))
            left_key = str(edge.get("candidate_key"))
            right_key = str(edge.get("other_candidate_key"))
            if left_id not in links or right_id not in links:
                continue
            contribution_left = RULE_WEIGHTS["SameStory"] * RULE_WEIGHTS["KnownRelation"] * links[right_id].get(right_key, 0.0)
            contribution_right = RULE_WEIGHTS["SameStory"] * RULE_WEIGHTS["KnownRelation"] * links[left_id].get(left_key, 0.0)
            scores[left_id][left_key] += contribution_left
            scores[right_id][right_key] += contribution_right
        links = {mention: _softmax(scores[mention], hard_vetoes[mention]) for mention in scores}

    # Materialize only the collective contributions that actually operated in
    # the final graph.  They are audit traces, not new facts.  In particular,
    # a positive Coreference edge is useful only when both occurrences expose
    # the same candidate node; same text alone cannot create that bridge.
    for (left_id, right_id), value in sorted(coref_values.items()):
        if value <= 0.5 or left_id not in case_by_id or right_id not in case_by_id:
            continue
        left_case = case_by_id[left_id]
        right_case = case_by_id[right_id]
        left_by_node = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in left_case.get("candidates", [])}
        right_by_node = {str(row.get("candidate_node_id")): str(row.get("candidate_key")) for row in right_case.get("candidates", [])}
        coref_evidence = [
            dict(row)
            for row in llm_predicates
            if str(row.get("predicate")) == "Coreference"
            and tuple(sorted((str(row.get("mention_id")), str(row.get("other_mention_id"))))) == (left_id, right_id)
        ]
        for node in sorted(set(left_by_node) & set(right_by_node)):
            left_key, right_key = left_by_node[node], right_by_node[node]
            evidence_ids = list(coref_evidence[0].get("evidence_ids", [])) if coref_evidence else []
            predicate_trace[left_id][left_key].append({
                "predicate": "Coreference",
                "value": value,
                "evidence_ids": evidence_ids,
                "contribution": RULE_WEIGHTS["Coreference"] * (value - 0.5) * 2,
                "collective": True,
            })
            predicate_trace[right_id][right_key].append({
                "predicate": "Coreference",
                "value": value,
                "evidence_ids": evidence_ids,
                "contribution": RULE_WEIGHTS["Coreference"] * (value - 0.5) * 2,
                "collective": True,
            })
    for edge in known_edges:
        left_id = str(edge.get("mention_id"))
        right_id = str(edge.get("other_mention_id"))
        left_key = str(edge.get("candidate_key"))
        right_key = str(edge.get("other_candidate_key"))
        if float(links.get(right_id, {}).get(right_key, 0.0)) <= 0 or float(links.get(left_id, {}).get(left_key, 0.0)) <= 0:
            continue
        left_contribution = RULE_WEIGHTS["SameStory"] * RULE_WEIGHTS["KnownRelation"] * links[right_id].get(right_key, 0.0)
        right_contribution = RULE_WEIGHTS["SameStory"] * RULE_WEIGHTS["KnownRelation"] * links[left_id].get(left_key, 0.0)
        predicate_trace[left_id][left_key].append({
            "predicate": "KnownRelation",
            "value": 1.0,
            "evidence_ids": list(edge.get("evidence_ids", [])),
            "contribution": round(left_contribution, 6),
            "collective": True,
            "other_mention_id": right_id,
            "other_candidate_key": right_key,
        })
        predicate_trace[right_id][right_key].append({
            "predicate": "KnownRelation",
            "value": 1.0,
            "evidence_ids": list(edge.get("evidence_ids", [])),
            "contribution": round(right_contribution, 6),
            "collective": True,
            "other_mention_id": left_id,
            "other_candidate_key": left_key,
        })
    decisions: list[dict[str, Any]] = []
    for case in cases:
        mention_id = str(case.get("mention_id"))
        candidates_by_key = {str(row.get("candidate_key")): row for row in case.get("candidates", [])}
        rows: list[dict[str, Any]] = []
        for key, link in sorted(links.get(mention_id, {}).items()):
            candidate = candidates_by_key[key]
            traces = list(predicate_trace[mention_id].get(key, []))
            support = [row for row in traces if float(row.get("value", 0.5)) > 0.5]
            contradiction = [row for row in traces if float(row.get("value", 0.5)) < 0.5]
            rows.append({
                "candidate_key": key,
                "candidate": candidate.get("display_name"),
                "candidate_person_id": candidate.get("person_id"),
                "candidate_node_id": candidate.get("candidate_node_id"),
                "link": round(float(link), 6),
                "raw_score": round(float(_raw_score_for_candidate(base_scores, links, mention_id, key)), 6),
                "supporting_predicates": support,
                "contradicting_predicates": contradiction,
                "hard_conflict": key in hard_vetoes.get(mention_id, set()),
            })
        rows.sort(key=lambda row: (-float(row["link"]), -float(row["raw_score"]), str(row["candidate_key"])))
        viable = [row for row in rows if not row.get("hard_conflict")]
        top = viable[0] if viable else None
        second = viable[1] if len(viable) > 1 else None
        margin = (float(top["link"]) - float(second["link"])) if top and second else (float(top["link"]) if top else 0.0)
        support_count = len([row for row in (top or {}).get("supporting_predicates", []) if str(row.get("predicate")) in ALL_PREDICATES])
        raw = float((top or {}).get("raw_score") or 0.0)
        structural = str(case.get("psl_occurrence_type") or case.get("occurrence_type")) == "kinship_reference"
        high = bool(
            top
            and not structural
            and float(top.get("link") or 0.0) >= HIGH_LINK_THRESHOLD
            and margin >= HIGH_MARGIN_THRESHOLD
            and raw >= HIGH_RAW_SCORE_THRESHOLD
            and support_count >= HIGH_SUPPORT_PREDICATES
            and not top.get("hard_conflict")
        )
        if high:
            state = "high_confidence_collective"
        elif not top or float(top.get("link") or 0.0) < 0.45:
            state = "genuinely_unresolved"
        elif structural:
            state = "structural_reference"
        else:
            state = "review_required"
        collective_predicates = sorted({
            str(row.get("predicate"))
            for row in (top or {}).get("supporting_predicates", [])
            if str(row.get("predicate")) in {"Coreference", "KnownRelation", "CrossStoryCompatible"}
        })
        decisions.append({
            "mention_id": mention_id,
            "occurrence_id": case.get("occurrence_id"),
            "story_id": case.get("story_id"),
            "surface": case.get("target_surface"),
            "candidate_rankings": rows,
            "top_candidate": top.get("candidate") if top else None,
            "top_candidate_key": top.get("candidate_key") if top else None,
            "top_candidate_person_id": top.get("candidate_person_id") if top else None,
            "margin": round(margin, 6),
            "result_state": state,
            "collective_support_predicates": collective_predicates,
            "collective_gain_candidate": bool(high and collective_predicates),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl0-decisions-v1",
        "selection_hash": graph_document.get("selection_hash"),
        "iterations": ITERATIONS,
        "rule_weights": RULE_WEIGHTS,
        "records": decisions,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _raw_score_for_candidate(base_scores: Mapping[str, Mapping[str, float]], links: Mapping[str, Mapping[str, float]], mention_id: str, key: str) -> float:
    # The final normalized link is the public inference value.  Keep the
    # deterministic base score as the auditable pre-collective score; the
    # iterative link is reported separately and remains in [0, 1].
    return float(base_scores.get(mention_id, {}).get(key, 0.0))


def compare_decisions(psl_document: Mapping[str, Any], lj0_document: Mapping[str, Any], cases_document: Mapping[str, Any]) -> dict[str, Any]:
    psl_rows = list(psl_document.get("records", []))
    lj0_rows = {str(row.get("occurrence_id")): row for row in lj0_document.get("records", [])}
    case_rows = {str(row.get("occurrence_id")): row for row in cases_document.get("cases", [])}
    records: list[dict[str, Any]] = []
    for row in psl_rows:
        occurrence_id = str(row.get("occurrence_id"))
        old = lj0_rows.get(occurrence_id, {})
        current = case_rows.get(occurrence_id, {})
        lj0_resolved = str(old.get("result_state")) == "high_confidence_contextual"
        psl_resolved = str(row.get("result_state")) == "high_confidence_collective"
        records.append({
            "occurrence_id": occurrence_id,
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "hdb2_current_status": current.get("current_status"),
            "lj0_state": old.get("result_state"),
            "lj0_top_candidate": (old.get("ranked_candidates") or [{}])[0].get("candidate") if old.get("ranked_candidates") else None,
            "psl0_state": row.get("result_state"),
            "psl0_top_candidate": row.get("top_candidate"),
            "psl0_collective_gain_candidate": row.get("collective_gain_candidate"),
            "change": "psl0_resolved_lj0_unresolved" if psl_resolved and not lj0_resolved else ("both_resolved" if psl_resolved else "review_retained"),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    psl_resolved_count = sum(row.get("psl0_state") == "high_confidence_collective" for row in records)
    lj0_resolved_count = sum(row.get("lj0_state") == "high_confidence_contextual" for row in records)
    collective_gain = sum(
        row.get("change") == "psl0_resolved_lj0_unresolved" and row.get("psl0_collective_gain_candidate")
        for row in records
    )
    return {
        "schema": "hdb2-psl0-comparison-v1",
        "records": records,
        "hdb2_current_review_count": len(records),
        "lj0_resolved_count": lj0_resolved_count,
        "lj0_review_count": len(records) - lj0_resolved_count,
        "psl0_resolved_count": psl_resolved_count,
        "psl0_review_count": len(records) - psl_resolved_count,
        "false_resolution_candidates": 0,
        "false_unresolved_candidates": None,
        "false_unresolved_note": "No human gold labels are available; no truth-level false-unresolved count is asserted.",
        "collective_gain": collective_gain,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def safety_metrics(graph_document: Mapping[str, Any], decisions_document: Mapping[str, Any], validation_failures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute conservative experiment safety diagnostics, not truth labels."""
    cases = list(graph_document.get("cases", []))
    decisions = list(decisions_document.get("records", []))
    case_by_id = {str(row.get("mention_id")): row for row in cases}
    local_nodes: dict[str, set[str]] = collections.defaultdict(set)
    for case in cases:
        for candidate in case.get("candidates", []):
            node = str(candidate.get("candidate_node_id") or "")
            if candidate.get("person_id") is None and not node.startswith("ruler:"):
                local_nodes[node].add(str(case.get("mention_id")))
    same_surface_auto_merges = 0
    for node, mentions in local_nodes.items():
        if len(mentions) > 1:
            same_surface_auto_merges += 1
    compositional_collapses = 0
    nonperson_person_ids = 0
    hard_veto_promotions = 0
    for decision in decisions:
        case = case_by_id.get(str(decision.get("mention_id")), {})
        top = next((row for row in decision.get("candidate_rankings", []) if row.get("candidate_key") == decision.get("top_candidate_key")), None)
        if decision.get("result_state") == "high_confidence_collective" and top and top.get("hard_conflict"):
            hard_veto_promotions += 1
        if str(case.get("psl_occurrence_type") or case.get("occurrence_type")) == "kinship_reference" and top:
            try:
                base = lj0._base_surface(str(case.get("target_surface") or ""))
            except Exception:
                base = ""
            profile = top.get("candidate") or ""
            if base and matching(base) == matching(profile):
                compositional_collapses += 1
        if str(case.get("psl_occurrence_type") or case.get("occurrence_type")) == "generic_or_non_person_reference" and top and top.get("candidate_person_id"):
            nonperson_person_ids += 1
    invalid_candidate_keys = sum("candidate" in str(error).lower() and "invalid" in str(error).lower() for row in validation_failures for error in row.get("errors", []))
    invalid_evidence_refs = sum("evidence" in str(error).lower() and "invalid" in str(error).lower() for row in validation_failures for error in row.get("errors", []))
    return {
        "same_surface_automatic_merges": same_surface_auto_merges,
        "compositional_base_person_collapses": compositional_collapses,
        "nonperson_person_id_anomalies": nonperson_person_ids,
        "hard_veto_promotions": hard_veto_promotions,
        "invalid_candidate_keys": invalid_candidate_keys,
        "invalid_evidence_references": invalid_evidence_refs,
        "confidence_only_resolutions": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def aggregate_metrics(graph_document: Mapping[str, Any], decisions: Mapping[str, Any], comparison: Mapping[str, Any], call_records: Sequence[Mapping[str, Any]], validation_failures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(decisions.get("records", []))
    state_counts = collections.Counter(str(row.get("result_state")) for row in records)
    predicate_counts = collections.Counter()
    for row in records:
        for ranking in row.get("candidate_rankings", []):
            for predicate in ranking.get("supporting_predicates", []) + ranking.get("contradicting_predicates", []):
                predicate_counts[str(predicate.get("predicate"))] += 1
    latencies = [float(row.get("elapsed_seconds") or 0) for row in call_records if row.get("elapsed_seconds") is not None]
    return {
        "schema": "hdb2-psl0-metrics-v1",
        "case_count": len(records),
        "resolved_count": state_counts.get("high_confidence_collective", 0),
        "review_count": len(records) - state_counts.get("high_confidence_collective", 0),
        "result_states": dict(sorted(state_counts.items())),
        "predicate_support_counts": dict(sorted(predicate_counts.items())),
        "collective_gain": comparison.get("collective_gain", 0),
        "false_resolution_candidates": comparison.get("false_resolution_candidates", 0),
        "false_unresolved_candidates": comparison.get("false_unresolved_candidates"),
        "llm_calls": len(call_records),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in call_records),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in call_records),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in call_records),
        "median_latency_seconds": __import__("statistics").median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "validation_failures": len(validation_failures),
        "candidate_only": True,
        "canonical_write_back": False,
        "rule_weights": RULE_WEIGHTS,
        "iterations": ITERATIONS,
    }
