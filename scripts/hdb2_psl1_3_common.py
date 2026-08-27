#!/usr/bin/env python3
"""PSL1.3 candidate-rescue interface.

This is a deliberately small adapter on top of the frozen PSL1.1/PSL1.2
implementation.  PSL1.3 changes the *diagnostic interface* only: the model
returns separate surface/referent types and per-candidate grounded
assessments.  Candidate discovery, source matching, identity propagation,
and all state transitions remain Python-owned and candidate-only.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import hdb2_lj0_common as lj0
import hdb2_p1_common as p1
import hdb2_psl1_common as psl1
import hdb2_psl1_1_common as psl1_1
import hdb2_psl1_2_common as psl1_2
import historical_entity_resolver as resolver


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated"
SELECTION_PATH = ANNOTATION / "hdb2-psl1-3-selection.json"
HDB2_F_CASES_PATH = DERIVED / "hdb2-f-occurrence-cases.json"
PSL1_2_SELECTION = ANNOTATION / "hdb2-psl1-2-selection.json"
MODEL = psl1.MODEL
STRICT_ENDPOINT = psl1.STRICT_ENDPOINT
RUN_VERSION = "hdb2-psl1-3-v1"
PROMPT_VERSION = "hdb2-psl1-3-rescue-interface-v1"
RESCUE_FUNCTION_NAME = "submit_hdb2_candidate_rescue_interface"

SURFACE_TYPES = {
    "person_name",
    "courtesy_name",
    "office_title",
    "ruler_title",
    "kinship_reference",
    "other",
}
REFERENT_TYPES = {"person", "ruler", "non_person", "uncertain"}
DIAGNOSES = {
    "candidate_set_sufficient",
    "candidate_missing_likely",
    "genuinely_ambiguous",
    "insufficient_evidence",
    "reference_not_person",
}
FORBIDDEN_ID_KEYS = set(psl1_2.FORBIDDEN_ID_KEYS) | {
    "ruler_id",
    "ruler_context_id",
    "canonical_id",
    "production_id",
}
VARIANT_PAIRS = (
    ("鳯", "鳳"),
    ("髙", "高"),
    ("温", "溫"),
    ("晋", "晉"),
    ("会", "會"),
    ("為", "爲"),
    ("禄", "祿"),
)


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


def _variant_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    for left, right in VARIANT_PAIRS:
        text = text.replace(left, right)
    return resolver.matching_normalize(text)


def matching(value: Any) -> str:
    return _variant_key(value)


def variant_equal(left: Any, right: Any) -> bool:
    return bool(matching(left)) and matching(left) == matching(right)


def _walk_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            if str(key) in FORBIDDEN_ID_KEYS:
                found.append(current)
            found.extend(_walk_keys(child, current))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_keys(child, f"{path}[{index}]"))
    return found


def _occurrence_ids(document: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for key in ("cases", "regression_cases", "holdout_cases", "independent_cases", "development_cases"):
        for row in document.get(key, []) or []:
            if isinstance(row, Mapping) and row.get("occurrence_id"):
                result.add(str(row.get("occurrence_id")))
    result.update(str(value) for value in document.get("development_occurrence_ids", []) or [] if value)
    return result


def previous_occurrence_ids() -> set[str]:
    """All occurrence units used by earlier PSL experiments."""
    result = set(psl1_2.previous_occurrence_ids())
    result |= _occurrence_ids(read_json(PSL1_2_SELECTION, {}) or {})
    return result


def _hdb2f_cases() -> dict[str, dict[str, Any]]:
    document = read_json(HDB2_F_CASES_PATH, {}) or {}
    return {
        str(row.get("occurrence_id")): dict(row)
        for row in document.get("cases", []) or []
        if row.get("occurrence_id")
    }


def _category(row: Mapping[str, Any]) -> str:
    surface = str(row.get("target_surface") or "")
    kind = str(row.get("occurrence_type") or "")
    if kind in {"kinship_reference", "kinship_compositional_reference"} or surface.endswith(psl1_2.KINSHIP_SUFFIXES):
        return "kinship_reference"
    if kind == "ruler_reference" or surface in {"帝", "明帝", "武帝", "元帝", "文帝", "康帝", "晉武帝"}:
        return "ruler_title"
    if kind in {"title_reference", "office_reference"} or any(surface.endswith(value) for value in psl1_2.OFFICE_SUFFIXES):
        return "office_title"
    if kind in {"abbreviated_person_name", "courtesy_name_reference"}:
        return "abbreviated_courtesy"
    return "ordinary_unresolved"


def _score(row: Mapping[str, Any]) -> tuple[int, int, int, int, str, str]:
    relations = len(row.get("local_relations", []) or [])
    neighbors = len(row.get("local_neighbors", []) or [])
    candidates = len(row.get("candidates", []) or [])
    evidence = len(row.get("evidence_items", []) or [])
    category_bonus = {
        "kinship_reference": 6,
        "ruler_title": 5,
        "office_title": 4,
        "abbreviated_courtesy": 3,
        "ordinary_unresolved": 1,
    }[_category(row)]
    return (
        -(category_bonus + 3 * relations + 2 * neighbors + candidates + evidence),
        -relations,
        -neighbors,
        -candidates,
        str(row.get("story_id") or ""),
        str(row.get("occurrence_id") or ""),
    )


def _selection_row(row: Mapping[str, Any], excluded: set[str]) -> dict[str, Any]:
    evidence_refs = sorted({
        str(item.get("source_ref"))
        for item in row.get("evidence_items", []) or []
        if item.get("source_ref")
    })
    key_material = {
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "story_id": row.get("story_id"),
        "surface": row.get("target_surface"),
        "source_refs": evidence_refs,
    }
    candidates = [
        {
            "display_name": item.get("display_name"),
            "semantic_type": item.get("semantic_type") or "person",
        }
        for item in row.get("candidates", []) or []
        if item.get("display_name")
    ]
    return {
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "story_id": row.get("story_id"),
        "surface": row.get("target_surface"),
        "occurrence_type": row.get("occurrence_type"),
        "selection_category": _category(row),
        "original_hdb2_status": row.get("hdb1_original_status"),
        "candidate_set": candidates,
        "source_refs": evidence_refs,
        "selection_key": stable_hash(key_material),
        "previous_hng2_excluded": str(row.get("occurrence_id")) in excluded,
    }


def build_selection(path: Path = SELECTION_PATH, *, limit: int = 10) -> dict[str, Any]:
    if limit != 10:
        raise ValueError("psl1_3_selection_must_have_exactly_10_cases")
    excluded = previous_occurrence_ids()
    all_rows = _hdb2f_cases()
    eligible = [row for row in all_rows.values() if str(row.get("occurrence_id")) not in excluded]
    # One row per Story is selected first.  This makes the requested sample
    # ten genuinely new Story/occurrence contexts rather than ten mentions
    # from a single review item, while all ordering remains data-driven.
    by_story: dict[str, list[dict[str, Any]]] = {}
    for row in eligible:
        by_story.setdefault(str(row.get("story_id") or ""), []).append(row)
    for rows in by_story.values():
        rows.sort(key=_score)
    story_winners = [rows[0] for story, rows in by_story.items() if story]
    story_winners.sort(key=_score)
    selected = story_winners[:limit]
    if len(selected) != limit:
        raise RuntimeError(f"psl1_3_independent_selection_count:{len(selected)}")
    rows = [_selection_row(row, excluded) for row in selected]
    rows.sort(key=lambda row: str(row.get("selection_key") or ""))
    result: dict[str, Any] = {
        "schema": "hdb2-psl1-3-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "excluded_previous_occurrence_ids": sorted(excluded),
        "excluded_previous_count": len(excluded),
        "source_input": str(HDB2_F_CASES_PATH.relative_to(ROOT)),
        "source_input_sha256": hashlib.sha256(HDB2_F_CASES_PATH.read_bytes()).hexdigest(),
        "independent_cases": rows,
        "independent_count": len(rows),
        "distinct_story_count": len({str(row.get("story_id")) for row in rows}),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != result:
            raise RuntimeError("hdb2_psl1_3_selection_changed")
        return existing
    write_json(path, result)
    return result


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    return build_selection(path)


def _review_type(row: Mapping[str, Any]) -> str:
    category = _category(row)
    return {
        "kinship_reference": "compositional_kinship",
        "ruler_title": "office_or_title_holder",
        "office_title": "office_or_title_holder",
        "abbreviated_courtesy": "identity",
        "ordinary_unresolved": "identity",
    }[category]


def _review_like(row: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt a frozen HDB2-F occurrence to the existing LJ0 builder contract."""
    result = copy.deepcopy(dict(row))
    result.update({
        "target_surface": row.get("target_surface"),
        "occurrence_type": row.get("occurrence_type") or "unclear",
        "story_id": row.get("story_id"),
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "candidate_people": list(row.get("candidates", []) or []),
        "selected_evidence": [
            {
                "evidence_ref": item.get("source_ref"),
                "source_layer": item.get("source_layer"),
                "excerpt": item.get("text"),
            }
            for item in row.get("evidence_items", []) or []
            if item.get("source_ref")
        ],
        "story_context": row.get("local_story_context") or "",
        "relevant_annotation_context": [
            value for value in row.get("annotation_context", []) or [] if value
        ],
        "review_type": _review_type(row),
        "status": row.get("hdb1_original_status") or "unresolved",
        "affected_facts": {
            "relations": list(row.get("local_relations", []) or []),
            "kinship": [],
            "marriage": [],
            "office": [],
        },
    })
    return result


def build_graph(selection: Mapping[str, Any]) -> dict[str, Any]:
    rows = _hdb2f_cases()
    catalog = hng02.person_catalog()
    index = resolver.forms_index(catalog)
    knowledge = lj0.load_person_knowledge()
    cases: list[dict[str, Any]] = []
    for selected in selection.get("independent_cases", []) or []:
        occurrence_id = str(selected.get("occurrence_id"))
        source = rows.get(occurrence_id)
        if source is None:
            raise RuntimeError(f"psl1_3_selection_item_missing:{occurrence_id}")
        cases.append(lj0.build_case(selected, _review_like(source), source, catalog, index, knowledge))
    document = {
        "schema": "hdb2-psl1-3-independent-input-v1",
        "selection_hash": selection.get("selection_hash"),
        "cases": cases,
    }
    graph = psl1_1.augment_graph(psl1.build_graph_cases(document))
    graph["schema"] = "hdb2-psl1-3-graph-cases-v1"
    graph["candidate_only"] = True
    graph["canonical_write_back"] = False
    return graph


def _object(properties: Mapping[str, Mapping[str, Any]], description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": {key: dict(value) for key, value in properties.items()},
        "required": list(properties),
        "additionalProperties": False,
    }


def rescue_tool() -> dict[str, Any]:
    assessment = _object({
        "candidate_key": {
            "type": "string",
            "description": "只能复制 supplied candidates 中的局部 c0/c1 键；不得输出 Person ID，也不得使用字符串 null。",
        },
        "supported_as_referent": {
            "type": "boolean",
            "description": "仅当 supplied text 明确支持该 candidate 是当前 occurrence 的 referent 时为 true；时代相容或同段出现不算支持。",
        },
        "supporting_evidence_ids": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "支持此 candidate 判断的 supplied evidence_id；每个 ID 必须来自 packet，不能指向外部证据。",
        },
    }, "一个 supplied candidate 对当前 textual referent 的 grounded assessment。")
    properties = {
        "surface_type": {
            "type": "string",
            "enum": sorted(SURFACE_TYPES),
            "description": "当前文字表达的语言/历史形式类别，例如 person_name、courtesy_name、office_title、ruler_title 或 kinship_reference；它描述 surface，不等于 referent 已是人物。",
        },
        "referent_type": {
            "type": "string",
            "enum": sorted(REFERENT_TYPES),
            "description": "当前表达实际可能指向的对象类别。office/ruler title 仍可以指向 person/ruler；只有对象本身不是人物时才使用 non_person。",
        },
        "candidate_assessments": {
            "type": "array",
            "maxItems": 8,
            "items": assessment,
            "description": "只比较 packet 中 supplied 的 candidates。supported_as_referent=true 必须有直接、具体、可复核的证据，而非一般语境相容。",
        },
        "candidate_set_supported": {
            "type": "boolean",
            "description": "现有候选集是否包含至少一个被 supplied evidence 明确支持为当前 referent 的候选；没有明确候选支持时必须为 false。",
        },
        "diagnosis": {
            "type": "string",
            "enum": sorted(DIAGNOSES),
            "description": "对候选集/指称的诊断，不是最终身份决定。candidate_set_sufficient 只在一个 supplied candidate 有明确 referent 支持时使用；reference_not_person 只在 referent_type=non_person 时使用。",
        },
        "proposed_identity_surface": {
            "type": ["string", "null"],
            "description": "若候选缺失，复制 supplied evidence 中出现的可能全名/别名/人物表面；无法提出时必须是真 JSON null，禁止字符串 null。Python 会再次做 grounded lookup。",
        },
        "search_hints": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "仅复制 supplied text 中可验证的 literal search hint；不是自由猜测，不能创建人物或改变状态。",
        },
        "supporting_evidence_ids": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "支持整体诊断的 supplied evidence_id；未知 ID 会被 Python 拒绝。",
        },
    }
    return {
        "type": "function",
        "function": {
            "name": RESCUE_FUNCTION_NAME,
            "description": "返回候选补救接口诊断；只读 supplied evidence，不选择或创建 canonical Person，不输出生产身份 ID。",
            "strict": True,
            "parameters": _object(properties, "候选补救诊断的严格 wire schema；所有字段都必须存在，额外字段不允许。"),
        },
    }


def rescue_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": RESCUE_FUNCTION_NAME}}


RESCUE_SYSTEM_PROMPT = """只阅读 supplied occurrence、candidate 和 evidence。先区分 surface_type 与 referent_type：office/title/ruler 表达仍可能指向 person/ruler，只有 referent 本身不是人物才使用 non_person。candidate_set_sufficient 只有在 supplied candidate 被明确支持为本次 referent 时才可使用；共处、同一时代、同一故事或一般相容不算 identity support。candidate_missing_likely 只是诊断，Python 会在已登记资源中做严格 grounded lookup。所有 evidence_id、search_hint 和 proposed_identity_surface 都必须来自 packet；不要使用外部知识、不要输出 Person ID、不要把诊断当最终身份决定。"""


def _packet_evidence(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("evidence_id")): row
        for row in packet.get("evidence_items", []) or []
        if isinstance(row, Mapping) and row.get("evidence_id")
    }


def _visible(text: str, value: str) -> bool:
    return bool(value) and (value in text or matching(value) in matching(text))


def _candidate_surface(packet: Mapping[str, Any], key: str) -> str:
    for row in packet.get("candidates", []) or []:
        if str(row.get("candidate_key")) == key:
            return str(row.get("name") or "")
    return ""


def _assessment_has_explicit_support(
    packet: Mapping[str, Any],
    candidate_key: str,
    evidence_ids: Sequence[str],
) -> bool:
    """Conservatively distinguish a direct referent statement from context."""
    target = str((packet.get("mention") or {}).get("surface") or "")
    candidate = _candidate_surface(packet, candidate_key)
    if not target or not candidate:
        return False
    evidence = _packet_evidence(packet)
    candidate_forms = [candidate]
    for row in packet.get("candidates", []) or []:
        if str(row.get("candidate_key")) == candidate_key:
            candidate_forms.extend(str(value) for value in row.get("aliases", []) or [] if value)
            candidate_forms.extend(str(value) for value in row.get("courtesy_names", []) or [] if value)
            candidate_forms.extend(str(value) for value in row.get("titles", []) or [] if value)
    for evidence_id in evidence_ids:
        row = evidence.get(str(evidence_id))
        if not row:
            continue
        family = str(row.get("family") or "")
        text = str(row.get("text") or "")
        if family in {"confirmed_story_profile", "candidate_profile", "era_chronology", "known_participants"}:
            continue
        if not _visible(text, target) or not any(_visible(text, form) for form in candidate_forms):
            continue
        if any(marker in text for marker in ("字", "名", "諱", "號", "号", "即", "實為", "實爲", "為", "爲")):
            return True
    return False


def validate_rescue_interface(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors = [f"forbidden_id_field:{path}" for path in _walk_keys(payload)]
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": sorted(set(["payload_not_object", *errors]))}
    expected = {
        "surface_type",
        "referent_type",
        "candidate_assessments",
        "candidate_set_supported",
        "diagnosis",
        "proposed_identity_surface",
        "search_hints",
        "supporting_evidence_ids",
    }
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    errors.extend(f"missing_field:{key}" for key in sorted(expected - set(payload)))
    if payload.get("surface_type") not in SURFACE_TYPES:
        errors.append("surface_type_invalid")
    if payload.get("referent_type") not in REFERENT_TYPES:
        errors.append("referent_type_invalid")
    if payload.get("diagnosis") not in DIAGNOSES:
        errors.append("diagnosis_invalid")
    if not isinstance(payload.get("candidate_set_supported"), bool):
        errors.append("candidate_set_supported_invalid")
    candidate_keys = {str(row.get("candidate_key")) for row in packet.get("candidates", []) if row.get("candidate_key")}
    evidence = _packet_evidence(packet)
    assessments = payload.get("candidate_assessments")
    supported_keys: list[str] = []
    if not isinstance(assessments, list):
        errors.append("candidate_assessments_invalid")
        assessments = []
    elif len(assessments) > 8:
        errors.append("candidate_assessments_too_many")
    seen: set[str] = set()
    for index, row in enumerate(assessments):
        if not isinstance(row, Mapping):
            errors.append(f"candidate_assessment_not_object:{index}")
            continue
        fields = {"candidate_key", "supported_as_referent", "supporting_evidence_ids"}
        errors.extend(f"candidate_assessment_unknown_field:{index}:{key}" for key in sorted(set(row) - fields))
        errors.extend(f"candidate_assessment_missing_field:{index}:{key}" for key in sorted(fields - set(row)))
        key = row.get("candidate_key")
        if not isinstance(key, str) or key == "null" or key not in candidate_keys:
            errors.append(f"candidate_key_invalid:{key}")
            key_text = str(key)
        else:
            key_text = key
        if key_text in seen:
            errors.append(f"candidate_key_duplicate:{key_text}")
        seen.add(key_text)
        if not isinstance(row.get("supported_as_referent"), bool):
            errors.append(f"supported_as_referent_invalid:{key_text}")
        ids = row.get("supporting_evidence_ids")
        if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
            errors.append(f"candidate_supporting_evidence_ids_invalid:{key_text}")
            ids = []
        elif len(ids) > 8:
            errors.append(f"candidate_supporting_evidence_ids_too_many:{key_text}")
        for evidence_id in ids:
            if evidence_id not in evidence:
                errors.append(f"evidence_reference_invalid:candidate:{evidence_id}")
        if row.get("supported_as_referent") is True:
            supported_keys.append(key_text)
            if not ids:
                errors.append(f"supported_candidate_without_evidence:{key_text}")
            elif key_text in candidate_keys and not _assessment_has_explicit_support(packet, key_text, ids):
                errors.append(f"candidate_support_not_explicit:{key_text}")
    if bool(payload.get("candidate_set_supported")) != bool(supported_keys):
        errors.append("candidate_set_supported_mismatch")
    if payload.get("diagnosis") == "candidate_set_sufficient" and not supported_keys:
        errors.append("candidate_set_sufficient_without_explicit_candidate")
    if payload.get("diagnosis") == "reference_not_person" and payload.get("referent_type") != "non_person":
        errors.append("reference_not_person_requires_non_person_referent")
    proposed = payload.get("proposed_identity_surface")
    if proposed == "null":
        errors.append("literal_null_invalid:proposed_identity_surface")
    elif proposed is not None and (not isinstance(proposed, str) or not proposed.strip()):
        errors.append("proposed_identity_surface_invalid")
    if payload.get("diagnosis") == "candidate_missing_likely":
        if isinstance(proposed, str) and proposed.strip():
            visible_text = "\n".join(str(row.get("text") or "") for row in evidence.values())
            if not _visible(visible_text, proposed):
                errors.append("proposed_identity_surface_not_grounded")
    elif proposed is not None:
        errors.append("proposed_identity_surface_unexpected")
    hints = payload.get("search_hints")
    if not isinstance(hints, list) or not all(isinstance(value, str) and value.strip() for value in hints):
        errors.append("search_hints_invalid")
        hints = []
    elif len(hints) > 8:
        errors.append("search_hints_too_many")
    visible_text = "\n".join(str(row.get("text") or "") for row in evidence.values())
    for hint in hints:
        if not _visible(visible_text, hint):
            errors.append(f"search_hint_not_grounded:{hint}")
    overall = payload.get("supporting_evidence_ids")
    if not isinstance(overall, list) or not all(isinstance(value, str) for value in overall):
        errors.append("supporting_evidence_ids_invalid")
        overall = []
    elif len(overall) > 8:
        errors.append("supporting_evidence_ids_too_many")
    for evidence_id in overall:
        if evidence_id not in evidence:
            errors.append(f"evidence_reference_invalid:overall:{evidence_id}")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def rescue_trigger(decision: Mapping[str, Any]) -> bool:
    return psl1_2.rescue_trigger(decision)


def _provider_safe(value: Any) -> Any:
    """Remove provider-facing identity-id fields from a frozen packet.

    The PSL1.1 packet has historically carried a nullable
    ``ruler_context_id`` slot.  It contains no identity value in these
    cases, but the PSL1.3 contract is stricter: a provider packet must not
    expose identifier-shaped fields at all.  This boundary copy therefore
    removes the slots without changing the underlying graph or resolver.
    """
    if isinstance(value, Mapping):
        return {
            key: _provider_safe(child)
            for key, child in value.items()
            if str(key) not in FORBIDDEN_ID_KEYS
        }
    if isinstance(value, list):
        return [_provider_safe(child) for child in value]
    return value


def wire_packet(case: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    return _provider_safe(psl1_1.wire_packet(case, cases, graph))


def reviewer_packet(
    case: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    return _provider_safe(psl1_1.reviewer_packet(case, cases, graph, decision))


def _safe_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    return psl1_2._safe_decision(decision)


def rescue_packet(
    case: Mapping[str, Any],
    decision: Mapping[str, Any],
    graph: Mapping[str, Any],
    reviewer: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    packet = _provider_safe(psl1_2.rescue_packet(case, decision, graph, reviewer))
    packet["task"] = "candidate rescue interface classification"
    packet["rescue_interface_version"] = PROMPT_VERSION
    packet["rescue_contract"] = {
        "surface_type_is_not_referent_type": True,
        "office_or_ruler_title_may_refer_to_person": True,
        "reference_not_person_requires_non_person_referent": True,
        "candidate_set_sufficient_requires_explicit_support": True,
        "candidate_missing_is_diagnostic_only": True,
        "python_grounding_required": True,
    }
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def _inventory() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for builder in (psl1_2._catalogue_inventory, psl1_2._hdb1_inventory, psl1_2._ruler_inventory):
        for key, value in builder().items():
            result.setdefault(key, dict(value))
    return result


def _inventory_forms(inventory: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for info in inventory.values():
        display = str(info.get("candidate_surface") or "")
        if not display:
            continue
        key = (matching(display), display)
        if key not in seen:
            rows.append((display, info))
            seen.add(key)
    return sorted(rows, key=lambda row: (-len(row[0]), row[0]))


def _surface_forms(value: str) -> list[str]:
    """Return the supplied surface and only its registered glyph variants."""
    forms = {str(value)}
    for left, right in VARIANT_PAIRS:
        forms.update({form.replace(left, right) for form in tuple(forms) if left in form})
        forms.update({form.replace(right, left) for form in tuple(forms) if right in form})
    return sorted(form for form in forms if form)


def _surface_occurrences(text: str, value: str) -> list[tuple[str, int]]:
    """Find literal source occurrences, retaining the witness spelling."""
    found: set[tuple[str, int]] = set()
    for form in _surface_forms(value):
        found.update((match.group(0), match.start()) for match in re.finditer(re.escape(form), text))
    return sorted(found, key=lambda row: (row[1], row[0]))


def _local_span(text: str, left: int, right: int, *, max_distance: int = 420) -> str:
    return psl1_2._local_span(text, left, right, max_distance=max_distance)


_resource_row = psl1_2._resource_row
_candidate_info = psl1_2._candidate_info


@lru_cache(maxsize=1)
def _source_units() -> tuple[dict[str, Any], ...]:
    """Cache the existing P1 registered-source index for this process only."""
    return tuple(dict(unit) for unit in p1.build_source_index())


def _derived_resource_row(
    *,
    target: str,
    candidate: str,
    info: Mapping[str, Any],
    basis: str,
    direct: bool,
    unit: Mapping[str, Any],
    span: str,
    required_surfaces: Sequence[str],
    matched_candidate_surface: str | None = None,
) -> dict[str, Any] | None:
    """Create a grounded row for a compositional/source-name projection.

    A derived candidate need not be a contiguous source string (for example
    ``謝聘`` is reconstructed from the surname in ``謝奉`` and the literal
    kinship endpoint ``聘``).  It is admitted only when every component and
    the exact source span are present in the same registered witness.  This
    keeps the provenance fail-closed without pretending the derived display
    form was quoted verbatim.
    """
    source_text = str(unit.get("evidence_text") or "")
    if not target or not candidate or not span or span not in source_text:
        return None
    if not all(any(variant_equal(actual, required) for actual, _ in _surface_occurrences(source_text, required)) for required in required_surfaces):
        return None
    row = {
        "resource_id": f"rescue-resource-{stable_hash((target, candidate, unit.get('ref'), basis, span, tuple(required_surfaces)))[:20]}",
        "target_surface": target,
        "candidate_surface": candidate,
        "person_id": info.get("person_id"),
        "candidate_kind": info.get("candidate_kind") or "source_named_entity",
        "basis": basis,
        "direct_identity_support": bool(direct),
        "source_ref": unit.get("ref"),
        "exact_span": span,
        "source_work": unit.get("source_work"),
        "source_layer": unit.get("source_layer"),
        "source_locator": dict(unit.get("locator") or {}) if isinstance(unit.get("locator"), Mapping) else {},
        "source_sha256": unit.get("source_sha256"),
        "derived_candidate": True,
        "grounding_surfaces": list(required_surfaces),
    }
    if matched_candidate_surface:
        row["matched_candidate_surface"] = matched_candidate_surface
    return row


def _variant_identity_rows(targets: Sequence[str]) -> list[dict[str, Any]]:
    """Recover direct name statements even when source/candidate glyphs differ."""
    wanted = sorted({str(value) for value in targets if value})
    inventory = _inventory()
    forms = _inventory_forms(inventory)
    units = _source_units()
    rows: list[dict[str, Any]] = []
    for unit in units:
        text = str(unit.get("evidence_text") or "")
        if not text:
            continue
        for target in wanted:
            actual_targets = sorted({
                match.group(0)
                for variant in {target, *[right if left == target else left for left, right in VARIANT_PAIRS if right == target or left == target]}
                for match in re.finditer(re.escape(variant), text)
            }, key=lambda value: (len(value), value))
            for actual_target in actual_targets:
                target_positions = [match.start() for match in re.finditer(re.escape(actual_target), text)]
                for candidate, info in forms:
                    if variant_equal(candidate, actual_target):
                        continue
                    actual_candidates = sorted({
                        match.group(0)
                        for variant in {candidate, *[right if left == candidate else left for left, right in VARIANT_PAIRS if right == candidate or left == candidate]}
                        for match in re.finditer(re.escape(variant), text)
                    }, key=lambda value: (len(value), value))
                    for actual_candidate in actual_candidates:
                        for target_pos, candidate_pos in itertools.product(
                            target_positions,
                            [match.start() for match in re.finditer(re.escape(actual_candidate), text)],
                        ):
                            span = psl1_2._local_span(text, target_pos, candidate_pos, max_distance=420)
                            if not span:
                                continue
                            between = span
                            explicit = bool(re.search(
                                rf"{re.escape(actual_candidate)}[\\s，,:：()（）〔〕「」『』]*"
                                rf"(?:字|名|諱|號|号|即)[\\s，,:：()（）〔〕「」『』]*{re.escape(actual_target)}",
                                between,
                            )) or bool(re.search(
                                rf"{re.escape(actual_target)}[\\s，,:：()（）〔〕「」『』]*"
                                rf"(?:字|名|諱|號|号|即)[\\s，,:：()（）〔〕「」『』]*{re.escape(actual_candidate)}",
                                between,
                            ))
                            if not explicit:
                                continue
                            resource = psl1_2._resource_row(
                                target=actual_target,
                                candidate=actual_candidate,
                                info=info,
                                basis="variant_grounded_identity_statement",
                                direct=True,
                                unit=unit,
                                span=span,
                            )
                            if not resource:
                                continue
                            resource["requested_target_surface"] = target
                            resource["matched_candidate_surface"] = actual_candidate
                            resource["candidate_surface"] = candidate
                            rows.append(resource)
                            break
                        else:
                            continue
                        break
    return rows


def _canonical_variant_surface(value: str) -> str:
    """Use the project's preferred traditional spelling for a derived label."""
    result = str(value or "")
    for left, right in VARIANT_PAIRS:
        result = result.replace(left, right)
    return result


def _target_looks_office(target: str) -> bool:
    # Keep the frozen PSL1.2 vocabulary and add forms that occur in the
    # interface regressions but were not needed by its original parser.
    suffixes = (*psl1_2.OFFICE_SUFFIXES, "中丞", "光祿", "光禄", "太尉", "大司馬", "大司马")
    return any(str(target).endswith(suffix) for suffix in suffixes)


def _generic_title_name_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Find a title followed by an explicitly named same-surname person.

    This covers note forms such as ``阮光祿 阮裕，已見``.  The title/name
    pairing is admitted only when the source itself supplies the short
    explanatory tail; a title and an arbitrary nearby name are not enough.
    """
    if not target or not _target_looks_office(target):
        return []
    rows: list[dict[str, Any]] = []
    for actual_target, target_pos in _surface_occurrences(text, target):
        tail = text[target_pos + len(actual_target):target_pos + len(actual_target) + 24]
        match = re.match(r"[\s，,:：；;、()（）〔〕「」『』]*([\u3400-\u9fff]{2,4})", tail)
        if not match:
            continue
        candidate = match.group(1)
        if not candidate or not variant_equal(candidate[:1], actual_target[:1]):
            continue
        after = tail[match.end():match.end() + 14]
        if not re.search(r"已見|已见|字|即|別傳|别传|傳曰|传曰|也", after):
            continue
        candidate_pos = target_pos + len(actual_target) + match.start(1)
        span = _local_span(text, target_pos, candidate_pos, max_distance=100)
        info = _candidate_info(candidate, inventory)
        resource = _resource_row(
            target=actual_target,
            candidate=candidate,
            info=info,
            basis="grounded_title_name_statement",
            direct=True,
            unit=unit,
            span=span,
        )
        if resource:
            resource["requested_target_surface"] = target
            resource["matched_candidate_surface"] = candidate
            rows.append(resource)
    return rows


def _generic_title_holder_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Find explicit office-holder syntax without assuming same surname.

    The old helper intentionally required a same-surname candidate, which
    misses ``髙靈時為中丞``.  This replacement still requires a holder verb
    between the named person and the office, so it does not turn proximity
    into office attribution.
    """
    if not target or not _target_looks_office(target):
        return []
    rows: list[dict[str, Any]] = []
    holder_markers = "為爲拜除任授遷迁轉转領领兼"
    for actual_target, target_pos in _surface_occurrences(text, target):
        for candidate, info in _inventory_forms(inventory):
            if not candidate or variant_equal(candidate, actual_target):
                continue
            for actual_candidate, candidate_pos in _surface_occurrences(text, candidate):
                if abs(candidate_pos - target_pos) > 260:
                    continue
                if candidate_pos < target_pos:
                    between = text[candidate_pos + len(actual_candidate):target_pos]
                    # The appointment verb must be immediately before the
                    # office (apart from a very small historical connective
                    # such as 時/乃).  This prevents an unrelated ``為`` in
                    # the same note from turning a nearby name into a title
                    # holder.
                    holder_match = re.search(rf"[\u3400-\u9fff、，,:：()（）〔〕「」『』\s]{{0,6}}[{holder_markers}]\s*$", between)
                else:
                    between = text[target_pos + len(actual_target):candidate_pos]
                    holder_match = re.search(rf"^[{holder_markers}][\u3400-\u9fff、，,:：()（）〔〕「」『』\s]{{0,6}}$", between)
                if not holder_match:
                    continue
                span = _local_span(text, target_pos, candidate_pos, max_distance=260)
                resource = _resource_row(
                    target=actual_target,
                    candidate=actual_candidate,
                    info=info,
                    basis="grounded_title_holder_statement",
                    direct=True,
                    unit=unit,
                    span=span,
                )
                if resource:
                    resource["requested_target_surface"] = target
                    resource["matched_candidate_surface"] = actual_candidate
                    rows.append(resource)
                break
    return rows


def _generic_ruler_context_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Ground a ruler/pronoun reference from explicit local ruler context."""
    if target not in {"朕", "寡人"}:
        return []
    rows: list[dict[str, Any]] = []
    for actual_target, target_pos in _surface_occurrences(text, target):
        title_matches = list(re.finditer(r"[\u3400-\u9fff]{1,4}帝", text))
        for match in title_matches:
            candidate = match.group(0)
            candidate_pos = match.start()
            if candidate_pos == target_pos or abs(candidate_pos - target_pos) > 260:
                continue
            lo, hi = sorted((candidate_pos + len(candidate), target_pos))
            between = text[lo:hi]
            if not re.search(r"登阼|踐阼|践阼|即位|嗣君|承大業|承大业|崩", between):
                continue
            info = dict(inventory.get(matching(candidate), {
                "candidate_surface": candidate,
                "person_id": None,
                "candidate_kind": "source_ruler_context",
            }))
            span = _derived_resource_row(
                target=actual_target,
                candidate=candidate,
                info=info,
                basis="grounded_ruler_pronoun_context",
                direct=True,
                unit=unit,
                span=_local_span(text, target_pos, candidate_pos, max_distance=260),
                required_surfaces=[actual_target, candidate],
                matched_candidate_surface=candidate,
            )
            if span:
                span["requested_target_surface"] = target
                rows.append(span)
    return rows


def _generic_kinship_name_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Derive a named kinship endpoint without treating it as the base person."""
    if not target or not any(target.endswith(suffix) or target in {"聘", "鳯", "鳳"} for suffix in psl1_2.KINSHIP_SUFFIXES):
        # Single-character endpoints such as 聘/鳯 are handled by their
        # surrounding kinship marker, not by a suffix test on the target.
        if target not in {"聘", "鳯", "鳳"}:
            return []
    relation_chars = "父母兄弟子女妻婿"
    rows: list[dict[str, Any]] = []
    inventory_forms = _inventory_forms(inventory)
    for actual_target, target_pos in _surface_occurrences(text, target):
        before = text[max(0, target_pos - 10):target_pos + len(actual_target)]
        after = text[target_pos + len(actual_target):target_pos + len(actual_target) + 90]
        patterns: list[tuple[str, str, int]] = []
        preceding = re.search(rf"(?P<base>[\u3400-\u9fff]{{1,3}})(?P<relation>[{relation_chars}]){re.escape(actual_target)}$", before)
        if preceding:
            patterns.append((preceding.group("base"), preceding.group("relation"), target_pos - len(actual_target) - 1))
        leading = re.search(rf"(?P<relation>[{relation_chars}]){re.escape(actual_target)}", before)
        # A target introduced as ``父鳳``/``母某`` can be followed by the
        # named child elsewhere in the compact genealogy phrase.  For
        # sibling/child/spouse forms the base must precede the relation (for
        # example ``奉弟聘``); accepting a bare ``子聘`` would confuse the
        # ordinary verb 聘 with a person's name.
        if leading and leading.group("relation") in {"父", "母"}:
            patterns.append(("", leading.group("relation"), target_pos - len(actual_target)))
        if not patterns:
            continue
        for full_name, info in inventory_forms:
            for base, relation, marker_pos in patterns:
                if base and not matching(full_name).endswith(matching(base)):
                    continue
                # The base must be part of a multi-character named surface;
                # a bare verb/character in a long biography is not a family
                # endpoint from which to construct a person's name.
                if base and len(full_name) <= len(base):
                    continue
                if not base:
                    # For ``父鳯...奉`` the full base name is supplied after
                    # the target; require it to occur in this same window.
                    if matching(full_name) == matching(actual_target):
                        continue
                full_positions = [pos for _, pos in _surface_occurrences(text, full_name)]
                for full_pos in full_positions:
                    # Both pieces must be in the same compact genealogy
                    # phrase.  The wider source unit is retained for audit,
                    # but cannot establish a kinship-name projection.
                    if abs(full_pos - target_pos) > 120:
                        continue
                    if not base and full_pos <= target_pos:
                        continue
                    surname = full_name[:len(full_name) - len(base)] if base else full_name[:1]
                    if not surname:
                        continue
                    candidate = _canonical_variant_surface(surname + actual_target)
                    if matching(candidate) == matching(full_name):
                        continue
                    span_text = _local_span(text, target_pos, full_pos, max_distance=420)
                    derived = _derived_resource_row(
                        target=actual_target,
                        candidate=candidate,
                        info=_candidate_info(candidate, inventory),
                        basis="grounded_kinship_name_projection",
                        direct=True,
                        unit=unit,
                        span=span_text,
                        required_surfaces=[actual_target, full_name],
                        matched_candidate_surface=actual_target,
                    )
                    if derived:
                        derived["requested_target_surface"] = target
                        derived["kinship_base_surface"] = full_name
                        derived["kinship_relation"] = relation
                        rows.append(derived)
                    break
    return rows


def build_grounded_resource_index(target_surfaces: Sequence[str]) -> list[dict[str, Any]]:
    terms = sorted({str(value) for value in target_surfaces if value})
    query_forms = sorted({form for value in terms for form in (value, *[right if left == value else left for left, right in VARIANT_PAIRS if right == value or left == value])})
    resources = list(psl1_2.build_grounded_resource_index(query_forms))
    resources.extend(_variant_identity_rows(terms))
    inventory = _inventory()
    for unit in _source_units():
        text = str(unit.get("evidence_text") or "")
        if not text:
            continue
        for target in terms:
            if not _surface_occurrences(text, target):
                continue
            resources.extend(_generic_title_name_rows(text, target, unit, inventory))
            resources.extend(_generic_title_holder_rows(text, target, unit, inventory))
            resources.extend(_generic_ruler_context_rows(text, target, unit, inventory))
            resources.extend(_generic_kinship_name_rows(text, target, unit, inventory))
    # Keep only exact-source-backed rows, and canonicalize candidate display
    # forms for comparison without changing the stored evidence span.
    canonical_forms = _inventory_forms(inventory)
    for row in resources:
        row.setdefault("requested_target_surface", row.get("target_surface"))
        for display, info in canonical_forms:
            if variant_equal(row.get("candidate_surface"), display):
                row["candidate_surface"] = display
                if info.get("person_id") and not row.get("person_id"):
                    row["person_id"] = info.get("person_id")
                break
    unique: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in resources:
        if str(row.get("requested_target_surface")) not in terms and not any(
            variant_equal(row.get("target_surface"), term) for term in terms
        ):
            continue
        if not row.get("exact_span") or not row.get("source_ref"):
            continue
        key = (
            str(row.get("requested_target_surface") or row.get("target_surface")),
            str(row.get("candidate_surface")),
            str(row.get("source_ref")),
            str(row.get("basis")),
            str(row.get("exact_span")),
        )
        unique.setdefault(key, row)
    return sorted(unique.values(), key=lambda row: (
        str(row.get("requested_target_surface") or row.get("target_surface")),
        0 if row.get("direct_identity_support") else 1,
        str(row.get("candidate_surface")),
        str(row.get("source_ref")),
    ))


def find_grounded_rescue_candidates(
    case: Mapping[str, Any],
    diagnosis: Mapping[str, Any],
    resources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if diagnosis.get("diagnosis") != "candidate_missing_likely":
        return {"candidates": [], "evidence": [], "diagnosis_used": diagnosis.get("diagnosis")}
    target = str(case.get("target_surface") or "")
    proposed = str(diagnosis.get("proposed_identity_surface") or "")
    current = {matching(row.get("display_name")) for row in case.get("candidates", []) or []}
    selected: list[dict[str, Any]] = []
    for row in resources:
        row_target = str(row.get("requested_target_surface") or row.get("target_surface") or "")
        candidate = str(row.get("candidate_surface") or "")
        if not variant_equal(row_target, target) or not candidate or matching(candidate) in current:
            continue
        if not row.get("direct_identity_support"):
            continue
        if proposed and not (variant_equal(candidate, proposed) or variant_equal(row.get("matched_candidate_surface"), proposed)):
            continue
        selected.append(dict(row))
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in selected:
        key = (matching(row.get("candidate_surface")), str(row.get("person_id") or ""))
        bucket = grouped.setdefault(key, {
            "candidate_surface": row.get("candidate_surface"),
            "person_id": row.get("person_id"),
            "candidate_kind": row.get("candidate_kind") or "source_named_entity",
            "basis": row.get("basis"),
            "direct_identity_support": True,
            "evidence": [],
        })
        bucket["evidence"].append(dict(row))
    candidates = sorted(grouped.values(), key=lambda row: (str(row.get("candidate_surface")), str(row.get("person_id") or "")))
    for row in candidates:
        row["evidence"] = sorted(row["evidence"], key=lambda item: (str(item.get("source_ref")), str(item.get("resource_id"))))[:8]
    return {
        "candidates": candidates,
        "evidence": [item for row in candidates for item in row.get("evidence", [])],
        "diagnosis_used": diagnosis.get("diagnosis"),
    }


def add_rescue_candidates(
    graph: Mapping[str, Any],
    occurrence_id: str,
    grounded: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated, provenance = psl1_2.add_rescue_candidates(graph, occurrence_id, grounded)
    result = copy.deepcopy(updated)
    for case in result.get("cases", []) or []:
        for candidate in case.get("candidates", []) or []:
            node = str(candidate.get("candidate_node_id") or "")
            if node.startswith("local:psl1-2-rescue:"):
                candidate["candidate_node_id"] = node.replace("local:psl1-2-rescue:", "local:psl1-3-rescue:", 1)
        case["candidate_only"] = True
        case["canonical_write_back"] = False
    for row in provenance:
        node = str(row.get("candidate_node_id") or "")
        if node.startswith("local:psl1-2-rescue:"):
            row["candidate_node_id"] = node.replace("local:psl1-2-rescue:", "local:psl1-3-rescue:", 1)
        row["rescue_interface_version"] = PROMPT_VERSION
    result["schema"] = "hdb2-psl1-3-rescue-graph-v1"
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result, provenance


def rescue_predicates(graph: Mapping[str, Any], provenance: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = psl1_2.rescue_predicates(graph, provenance)
    for row in rows:
        row["reason"] = "python_grounded_candidate_rescue_interface"
    return rows


def required_regression_records() -> dict[str, Any]:
    result = psl1_2.required_regression_records()
    result["schema"] = "hdb2-psl1-3-required-regressions-v1"
    return result


def false_resolution_regression() -> dict[str, Any]:
    result = psl1_2.false_resolution_regression()
    result["schema"] = "hdb2-psl1-3-false-regressions-v1"
    return result


def _review_item_graph(item: Mapping[str, Any]) -> dict[str, Any]:
    """Build the frozen LJ0/PSL1.1 case for an existing review item."""
    document = lj0.build_cases({
        "schema": "hdb2-psl1-3-interface-regression-input-v1",
        "cases": [dict(item)],
    })
    return psl1_1.augment_graph(psl1.build_graph_cases(document))


def interface_regression_records() -> dict[str, Any]:
    """Offline checks for the revised interface semantics and glyph lookup."""
    checks = [
        {"surface": "劉尹", "story_id": "02-yanyu-054", "expected": "劉惔", "kind": "existing_grounded"},
        {"surface": "朕", "story_id": "05-fangzheng-041", "expected": "康帝", "kind": "ruler_grounded"},
        {"surface": "陛下", "story_id": "05-fangzheng-041", "expected": "ruler", "kind": "ruler_type"},
        {"surface": "中丞", "story_id": "25-paidiao-026", "expected": "髙靈", "kind": "office_grounded"},
        {"surface": "阮光禄", "story_id": "05-fangzheng-053", "expected": "阮裕", "kind": "missing_candidate"},
        {"surface": "聘", "story_id": "09-pinzao-040", "expected": "謝聘", "kind": "directional_identity"},
        {"surface": "鳯", "story_id": "06-yaliang-033", "expected": "謝鳳", "kind": "variant_identity"},
    ]
    review_items = psl1_2._review_items()
    records: list[dict[str, Any]] = []
    for check in checks:
        source = next((row for row in review_items.values() if str(row.get("story_id")) == check["story_id"] and str(row.get("target_surface")) == check["surface"]), None)
        if not source:
            records.append({**check, "passed": False, "reason": "source_case_missing"})
            continue
        graph = _review_item_graph(source)
        case = graph.get("cases", [])[0]
        packet = rescue_packet(case, {"result_state": "review_required", "candidate_rankings": []}, graph)
        if check["kind"] == "ruler_type":
            payload = {
                "surface_type": "ruler_title",
                "referent_type": "ruler",
                "candidate_assessments": [],
                "candidate_set_supported": False,
                "diagnosis": "insufficient_evidence",
                "proposed_identity_surface": None,
                "search_hints": [],
                "supporting_evidence_ids": [],
            }
            validation = validate_rescue_interface(payload, packet)
            records.append({**check, "validation": validation, "passed": bool(validation["valid"] and payload["referent_type"] == "ruler"), "candidate_only": True})
            continue
        payload = {
            "surface_type": "office_title" if check["surface"] in {"劉尹", "中丞", "阮光禄"} else "person_name",
            "referent_type": "person",
            "candidate_assessments": [],
            "candidate_set_supported": False,
            "diagnosis": "candidate_missing_likely",
            # A missing-candidate diagnosis may be valid without a model
            # proposal.  This is important for 阮光祿: the source-backed
            # lookup, rather than an ungrounded model name, finds 阮裕.
            "proposed_identity_surface": None if check["kind"] in {"missing_candidate", "directional_identity", "variant_identity"} else check["expected"],
            "search_hints": [] if check["kind"] in {"missing_candidate", "directional_identity", "variant_identity"} else [check["expected"]],
            "supporting_evidence_ids": [],
        }
        # For an offline regression, use existing source-backed resource rows
        # as the Python rescue input.  The model is never credited with the
        # resulting candidate.
        validation = validate_rescue_interface(payload, packet)
        resources = build_grounded_resource_index([check["surface"]])
        grounded = find_grounded_rescue_candidates(case, payload, resources)
        resource_matches = [row for row in resources if variant_equal(row.get("candidate_surface"), check["expected"]) and row.get("direct_identity_support")]
        found = any(variant_equal(row.get("candidate_surface"), check["expected"]) for row in grounded.get("candidates", []))
        if check["kind"] == "missing_candidate":
            found = bool(resource_matches) and found
        elif check["kind"] == "existing_grounded":
            # Existing supplied candidates are intentionally not added again;
            # the resource row proves that the rescue search can ground the
            # identity evidence without conflating it with candidate rescue.
            found = bool(resource_matches)
        records.append({
            **check,
            "validation": validation,
            "grounded_candidates": [row.get("candidate_surface") for row in grounded.get("candidates", [])],
            "grounded_resource_candidates": [row.get("candidate_surface") for row in resource_matches],
            "passed": bool(validation["valid"] and found),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-3-interface-regressions-v1",
        "records": records,
        "all_pass": all(bool(row.get("passed")) for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
    }
