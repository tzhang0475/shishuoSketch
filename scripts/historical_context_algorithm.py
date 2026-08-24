#!/usr/bin/env python3
"""The consolidated HNG2 historical-context extraction contract.

This module is deliberately small and side-effect free.  It defines one
strict DeepSeek card, validates its source spans item by item, and projects
the surviving observations through the existing Python resolver.  It does
not retrieve, search, expand a frontier, or write canonical data.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import historical_entity_resolver as resolver
import historical_entity_schema as schema


ROOT = Path(__file__).resolve().parents[1]
FUNCTION_NAME = "submit_historical_context_card"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"

RELATION_CLASSES = {
    "kinship",
    "marriage",
    "institutional",
    "interaction",
    "identity_name",
    "other",
}
TEMPORAL_TYPES = {
    "exact_date",
    "exact_year",
    "reign_period",
    "event_bound",
    "before",
    "after",
    "office_period",
    "other",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
LOCAL_ENTITY = re.compile(r"^e[0-9]+$")
LOCAL_RELATION = re.compile(r"^r[0-9]+$")
LOCAL_TEMPORAL = re.compile(r"^t[0-9]+$")
FORBIDDEN_ID_FIELDS = {
    "person_id",
    "candidate_key",
    "provisional_person_id",
    "graph_id",
    "relation_graph_id",
}

RELATION_MARKERS = (
    "父", "母", "子", "女", "兄", "弟", "從", "叔", "舅", "妻", "婿",
    "辟", "除", "拜", "任", "與", "詣", "討", "攻", "同", "為", "爲",
)
TEMPORAL_MARKERS = (
    "年", "元年", "時", "后", "後", "初", "末", "永和", "太康", "建武",
    "大興", "永昌", "嘉平", "咸和", "太元", "興寧", "隆安",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _enum(values: set[str], description: str) -> dict[str, Any]:
    return {
        "type": "string",
        "enum": sorted(values),
        "description": description + " 不得使用同义词或其他字符串。",
    }


def _array(items: Mapping[str, Any], description: str) -> dict[str, Any]:
    return {"type": "array", "items": dict(items), "description": description}


def _object(properties: Mapping[str, Mapping[str, Any]], description: str) -> dict[str, Any]:
    props = {str(key): dict(value) for key, value in properties.items()}
    return {
        "type": "object",
        "description": description,
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def _entity_schema() -> dict[str, Any]:
    return _object(
        {
            "entity_key": _string(
                "本次回答内部使用的局部实体编号，如 e0。它不是 Person ID、candidate key 或 graph ID。"
            ),
            "surface": _string(
                "史料中实际出现、需要解释的文字形式，例如庾太尉、炎、元規或喜弟預女。保留原文。"
            ),
            "entity_kind": _enum(
                schema.ENTITY_KINDS,
                "该表达在当前语境中的人物语义类别；使用系统已有 entity_kind 枚举。"
            ),
            "reference_form": _enum(
                schema.REFERENCE_FORMS,
                "该表达通过什么语言形式指向人物；这是语言形式，不是最终身份决定。"
            ),
            "evidence_ref": _string(
                "实体出现的系统 source passage ref，必须逐字复制输入中的 ref，不得自行生成。"
            ),
            "exact_span": _string(
                "能够证明该实体解释的最短连续原文；必须原样存在于 evidence_ref 的输入文本中。"
            ),
        },
        "只记录当前 target 所需的实体表达和直接原文证据，不做全文人物抽取，不创建数据库身份。",
    )


def _relation_schema() -> dict[str, Any]:
    return _object(
        {
            "relation_id": _string(
                "本次回答内部使用的局部断言编号，如 r0。它不是 canonical relation ID。"
            ),
            "subject_entity_key": _string(
                "关系主体；必须引用 entities 中已有的 eN key。"
            ),
            "object_entity_key": _string(
                "关系客体；必须引用 entities 中已有的 eN key。没有明确客体时填写空字符串。"
            ),
            "relation_surface": _string(
                "原文中表达关系的历史措辞，例如父、弟、妻、婿、辟、除、拜、從、與語或詣；尽量保留原文。"
            ),
            "relation_class": _enum(
                RELATION_CLASSES,
                "关系的宽分类。kinship 是亲属，marriage 是婚姻/姻亲，institutional 是任用或制度性关系，interaction 是明确互动，identity_name 是同一名称关系，other 是无法更细分但原文明确的关系。不要把一次互动升级为友谊或政治联盟。"
            ),
            "evidence_ref": _string(
                "直接支持关系的 source passage ref，必须逐字复制输入中的 ref。"
            ),
            "exact_span": _string(
                "直接证明关系的最短连续原文；必须原样存在于 evidence_ref 的输入文本中。共现本身不是关系证据。"
            ),
            "confidence": _enum(
                CONFIDENCE_LEVELS,
                "模型对原文是否直接表达该关系的信心，不是数据库事实真实性。"
            ),
        },
        "只记录原文明确支持的宽关系和证据，不管理 Person、Relation 或图谱状态。",
    )


def _temporal_schema() -> dict[str, Any]:
    return _object(
        {
            "temporal_id": _string(
                "本次回答内部使用的局部时间断言编号，如 t0。它不是数据库时间事实 ID。"
            ),
            "subject_entity_key": _string(
                "时间表达所涉及的实体 eN；若原文只有无人物绑定的事件时间，可填写空字符串。"
            ),
            "temporal_surface": _string(
                "史料中实际出现的时间、年代、先后或时代表达，例如永和九年、元帝时或乱后。"
            ),
            "temporal_type": _enum(
                TEMPORAL_TYPES,
                "时间表达的文字类别；只描述原文，不生成叙事性的时代解释。"
            ),
            "reference_surface": _string(
                "若时间表达绑定到另一个原文实体，填写该实体的原文形式；否则填写空字符串。"
            ),
            "evidence_ref": _string(
                "直接支持时间断言的 source passage ref，必须逐字复制输入中的 ref。"
            ),
            "exact_span": _string(
                "直接证明时间信息的最短连续原文；必须原样存在于 evidence_ref 的输入文本中。"
            ),
            "confidence": _enum(
                CONFIDENCE_LEVELS,
                "模型对原文是否直接表达该时间信息的信心，不是对后续年代换算的信心。"
            ),
        },
        "只记录史料明确给出的时间表达；后续年代归一化由 Python 依据 H0A 完成。",
    )


def card_parameters_schema() -> dict[str, Any]:
    return _object(
        {
            "entities": _array(
                _entity_schema(),
                "当前 target 必需的实体表达；尽量少而完整，不抽取无关人物。",
            ),
            "relations": _array(
                _relation_schema(),
                "当前 target 必需的明确人物关系；共现、推测和未写出的长期关系不得填入。",
            ),
            "temporal_assertions": _array(
                _temporal_schema(),
                "当前 target 必需的明确时间表达；不要把后文结果倒推为前文时间。",
            ),
        },
        "Historical Evidence Card：模型只读给定史料并返回最小的实体、宽关系和时间证据。Python 随后负责验证和归一化。",
    )


def function_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "提交当前 target 的最小 Historical Evidence Card；只记录 supplied passages 中可逐字验证的文本语义。",
            "strict": True,
            "parameters": card_parameters_schema(),
        },
    }


def tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": FUNCTION_NAME}}


def schema_hash() -> str:
    raw = json.dumps(
        card_parameters_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _source_text(row: Mapping[str, Any]) -> str:
    return _text(row.get("text") or row.get("supplied_text") or row.get("original_text"))


def _contains(ref: str, span: str, passages: Mapping[str, Mapping[str, Any]]) -> bool:
    return bool(ref and span and ref in passages and span in _source_text(passages[ref]))


def _forbidden_ids(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_ID_FIELDS:
                found.append(f"{path}.{key_text}" if path else key_text)
            found.extend(_forbidden_ids(child, f"{path}.{key_text}" if path else key_text))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_ids(child, f"{path}[{index}]"))
    return found


def _item_error(bucket: list[dict[str, Any]], index: int, reason: str, item: Any) -> None:
    bucket.append({"index": index, "reason": reason, "item": item})


def validate_card(payload: Any, passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Validate a card item by item; valid siblings survive invalid items."""

    top_errors: list[str] = []
    rejected_entities: list[dict[str, Any]] = []
    rejected_relations: list[dict[str, Any]] = []
    rejected_temporal: list[dict[str, Any]] = []
    valid_entities: list[dict[str, Any]] = []
    valid_relations: list[dict[str, Any]] = []
    valid_temporal: list[dict[str, Any]] = []

    if not isinstance(payload, Mapping):
        return {
            "valid": False,
            "usable": False,
            "top_errors": ["payload_not_object"],
            "valid_entities": [],
            "valid_relations": [],
            "valid_temporal_assertions": [],
            "rejected_entities": [],
            "rejected_relations": [],
            "rejected_temporal_assertions": [],
            "forbidden_id_attempts": [],
        }

    expected = {"entities", "relations", "temporal_assertions"}
    top_errors.extend(f"unknown_top_field:{key}" for key in sorted(set(payload) - expected))
    top_errors.extend(f"missing_top_field:{key}" for key in sorted(expected - set(payload)))
    forbidden = _forbidden_ids(payload)

    entities = payload.get("entities")
    if not isinstance(entities, list):
        top_errors.append("entities_not_array")
        entities = []
    seen_keys: set[str] = set()
    for index, item in enumerate(entities):
        if not isinstance(item, Mapping):
            _item_error(rejected_entities, index, "not_object", item)
            continue
        keys = {
            "entity_key", "surface", "entity_kind", "reference_form",
            "evidence_ref", "exact_span",
        }
        if set(item) != keys:
            _item_error(rejected_entities, index, "field_set_mismatch", item)
            continue
        key = _text(item.get("entity_key"))
        surface = _text(item.get("surface"))
        ref = _text(item.get("evidence_ref"))
        span = _text(item.get("exact_span"))
        if not LOCAL_ENTITY.fullmatch(key):
            _item_error(rejected_entities, index, "invalid_entity_key", item)
        elif key in seen_keys:
            _item_error(rejected_entities, index, "duplicate_entity_key", item)
        elif not surface:
            _item_error(rejected_entities, index, "empty_surface", item)
        elif item.get("entity_kind") not in schema.ENTITY_KINDS:
            _item_error(rejected_entities, index, "invalid_entity_kind", item)
        elif item.get("reference_form") not in schema.REFERENCE_FORMS:
            _item_error(rejected_entities, index, "invalid_reference_form", item)
        elif not _contains(ref, span, passages):
            _item_error(rejected_entities, index, "evidence_span_not_found", item)
        elif surface not in span:
            _item_error(rejected_entities, index, "surface_not_in_exact_span", item)
        else:
            seen_keys.add(key)
            valid_entities.append(dict(item))

    relations = payload.get("relations")
    if not isinstance(relations, list):
        top_errors.append("relations_not_array")
        relations = []
    for index, item in enumerate(relations):
        if not isinstance(item, Mapping):
            _item_error(rejected_relations, index, "not_object", item)
            continue
        keys = {
            "relation_id", "subject_entity_key", "object_entity_key",
            "relation_surface", "relation_class", "evidence_ref",
            "exact_span", "confidence",
        }
        if set(item) != keys:
            _item_error(rejected_relations, index, "field_set_mismatch", item)
            continue
        rid = _text(item.get("relation_id"))
        subject = _text(item.get("subject_entity_key"))
        object_key = _text(item.get("object_entity_key"))
        relation_surface = _text(item.get("relation_surface"))
        ref = _text(item.get("evidence_ref"))
        span = _text(item.get("exact_span"))
        reason = ""
        if not LOCAL_RELATION.fullmatch(rid):
            reason = "invalid_relation_id"
        elif subject not in seen_keys:
            reason = "unknown_subject_entity"
        elif object_key and object_key not in seen_keys:
            reason = "unknown_object_entity"
        elif not object_key:
            reason = "missing_object_entity"
        elif subject == object_key and item.get("relation_class") != "identity_name":
            reason = "self_relation"
        elif item.get("relation_class") not in RELATION_CLASSES:
            reason = "invalid_relation_class"
        elif item.get("confidence") not in CONFIDENCE_LEVELS:
            reason = "invalid_confidence"
        elif not relation_surface:
            reason = "empty_relation_surface"
        elif not _contains(ref, span, passages):
            reason = "evidence_span_not_found"
        elif relation_surface not in span:
            reason = "relation_surface_not_in_exact_span"
        if reason:
            _item_error(rejected_relations, index, reason, item)
        else:
            valid_relations.append(dict(item))

    temporal = payload.get("temporal_assertions")
    if not isinstance(temporal, list):
        top_errors.append("temporal_assertions_not_array")
        temporal = []
    for index, item in enumerate(temporal):
        if not isinstance(item, Mapping):
            _item_error(rejected_temporal, index, "not_object", item)
            continue
        keys = {
            "temporal_id", "subject_entity_key", "temporal_surface",
            "temporal_type", "reference_surface", "evidence_ref",
            "exact_span", "confidence",
        }
        if set(item) != keys:
            _item_error(rejected_temporal, index, "field_set_mismatch", item)
            continue
        tid = _text(item.get("temporal_id"))
        subject = _text(item.get("subject_entity_key"))
        temporal_surface = _text(item.get("temporal_surface"))
        ref = _text(item.get("evidence_ref"))
        span = _text(item.get("exact_span"))
        reason = ""
        if not LOCAL_TEMPORAL.fullmatch(tid):
            reason = "invalid_temporal_id"
        elif subject and subject not in seen_keys:
            reason = "unknown_subject_entity"
        elif item.get("temporal_type") not in TEMPORAL_TYPES:
            reason = "invalid_temporal_type"
        elif item.get("confidence") not in CONFIDENCE_LEVELS:
            reason = "invalid_confidence"
        elif not temporal_surface:
            reason = "empty_temporal_surface"
        elif not _contains(ref, span, passages):
            reason = "evidence_span_not_found"
        elif temporal_surface not in span:
            reason = "temporal_surface_not_in_exact_span"
        if reason:
            _item_error(rejected_temporal, index, reason, item)
        else:
            valid_temporal.append(dict(item))

    valid = not top_errors and not forbidden
    return {
        "valid": valid,
        "usable": valid and bool(valid_entities or valid_relations or valid_temporal),
        "top_errors": top_errors,
        "forbidden_id_attempts": forbidden,
        "valid_entities": valid_entities,
        "valid_relations": valid_relations,
        "valid_temporal_assertions": valid_temporal,
        "rejected_entities": rejected_entities,
        "rejected_relations": rejected_relations,
        "rejected_temporal_assertions": rejected_temporal,
        "item_rejection_count": len(rejected_entities) + len(rejected_relations) + len(rejected_temporal),
    }


def _matching_form(value: str) -> str:
    return resolver.matching_normalize(value)


def _case_candidate_forms(case: Mapping[str, Any]) -> list[str]:
    rows = case.get("candidates") or []
    if isinstance(rows, Mapping):
        rows = list(rows.values())
    result: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in ("canonical_name", "known_forms"):
            value = row.get(key)
            if isinstance(value, str):
                result.add(value)
            elif isinstance(value, Sequence):
                result.update(_text(item) for item in value if _text(item))
    return sorted(result, key=lambda item: (-len(_matching_form(item)), _matching_form(item), item))


def _case_candidate_match(
    surface: str,
    case: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Use an existing frozen candidate row only as a Python projection hint."""

    rows = case.get("candidates") or []
    if isinstance(rows, Mapping):
        rows = list(rows.values())
    folded = _matching_form(surface)
    matches: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or not _text(row.get("person_id")):
            continue
        forms = row.get("known_forms") or []
        if isinstance(forms, str):
            forms = [forms]
        forms = list(forms) if isinstance(forms, Sequence) else []
        forms = [str(row.get("canonical_name") or ""), *[str(value) for value in forms]]
        if any(_matching_form(value) == folded for value in forms if _text(value)):
            matches.append(dict(row))
    if len(matches) == 1:
        return matches[0]
    return None


def _anchor_positions(raw: str, anchors: Sequence[str]) -> list[tuple[int, int, str]]:
    positions: list[tuple[int, int, str]] = []
    for anchor in sorted({_text(x) for x in anchors if _text(x)}, key=lambda x: (-len(x), x)):
        start = 0
        while True:
            index = raw.find(anchor, start)
            if index < 0:
                break
            positions.append((index, len(anchor), anchor))
            start = index + 1
    return positions


def _compact_window(raw: str, anchors: Sequence[str], limit: int) -> tuple[str, list[str]]:
    if len(raw) <= limit:
        return raw, ["full_passage"]
    positions = _anchor_positions(raw, anchors)
    if positions:
        # Prefer the longest known full form, then the first stable occurrence.
        center, length, anchor = sorted(positions, key=lambda row: (-row[1], row[0], row[2]))[0]
        center += max(1, length // 2)
        start = max(0, center - limit // 2)
        end = min(len(raw), start + limit)
        start = max(0, end - limit)
        return raw[start:end], [f"anchor:{anchor}"]
    return raw[:limit], ["prefix_fallback"]


def _passage_score(
    row: Mapping[str, Any],
    target: str,
    exact_span: str,
    candidate_forms: Sequence[str],
) -> tuple[int, list[str]]:
    raw = _source_text(row)
    score = 0
    reasons: list[str] = []
    if target and target in raw:
        score += 100
        reasons.append("target")
    if exact_span and exact_span in raw:
        score += 80
        reasons.append("observation_span")
    matched_forms = [form for form in candidate_forms if form and form in raw]
    if matched_forms:
        score += 30 + max(len(form) for form in matched_forms)
        reasons.append("catalogue_or_case_form")
    relation_hits = sum(raw.count(marker) for marker in RELATION_MARKERS)
    temporal_hits = sum(raw.count(marker) for marker in TEMPORAL_MARKERS)
    if relation_hits:
        score += min(18, relation_hits)
        reasons.append("relation_marker")
    if temporal_hits:
        score += min(18, temporal_hits)
        reasons.append("temporal_marker")
    source_form = _text(row.get("source_form"))
    if source_form == "punctuated":
        score += 4
        reasons.append("punctuated")
    return score, reasons


def select_evidence_bundle(
    case: Mapping[str, Any],
    passages: Mapping[str, Mapping[str, Any]],
    *,
    max_passages: int = 4,
    max_chars: int = 900,
) -> dict[str, Any]:
    """Select compact windows from already-known frozen passage results."""

    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    target = _text(observation.get("surface"))
    exact_span = _text(observation.get("exact_span"))
    candidate_forms = _case_candidate_forms(case)
    scored: list[tuple[int, str, dict[str, Any], list[str]]] = []
    for ref, row in sorted(passages.items()):
        if not isinstance(row, Mapping):
            continue
        score, reasons = _passage_score(row, target, exact_span, candidate_forms)
        compact, compact_reasons = _compact_window(
            _source_text(row),
            [target, exact_span, *candidate_forms],
            max_chars,
        )
        scored.append(
            (
                score,
                str(ref),
                {
                    "ref": str(ref),
                    "work": row.get("work") or row.get("source_work") or observation.get("source_work"),
                    "layer": row.get("layer") or row.get("source_layer"),
                    "source_form": row.get("source_form") or "legacy_local",
                    "text": compact,
                    "original_chars": len(_source_text(row)),
                    "selected_chars": len(compact),
                    "selection_score": score,
                    "selection_reasons": sorted(set(reasons + compact_reasons)),
                },
                reasons,
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for _, _, row, _ in scored:
        digest = hashlib.sha256(_text(row["text"]).encode("utf-8")).hexdigest()
        if digest in seen_texts:
            continue
        seen_texts.add(digest)
        selected.append(row)
        if len(selected) >= max_passages:
            break
    return {
        "target_surface": target,
        "max_passages": max_passages,
        "max_chars_per_passage": max_chars,
        "passages": selected,
        "original_total_chars": sum(len(_source_text(row)) for row in passages.values() if isinstance(row, Mapping)),
        "selected_total_chars": sum(len(row["text"]) for row in selected),
    }


def prompt_payload(case: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, Any]:
    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    return {
        "target": {
            "surface": observation.get("surface"),
            "exact_span": observation.get("exact_span"),
            "source_work": observation.get("source_work"),
        },
        "source_passages": [
            {
                "ref": row.get("ref"),
                "work": row.get("work"),
                "layer": row.get("layer"),
                "source_form": row.get("source_form"),
                "text": row.get("text"),
            }
            for row in bundle.get("passages", [])
        ],
    }


SYSTEM_PROMPT = (
    "只阅读给定的历史史料原文，理解当前 target，并提交最小 Historical Evidence Card。"
    "只抽取与 target 直接相关、由原文明确支持的实体、人物关系和时间表达，保留历史措辞。"
    "每条证据都必须使用输入中的 ref 和连续原文；共现本身不是关系。"
    "保持 target 与上下文人物分开；引书作者或注家不是自动的事件参与者；不要用后文结果给前文场景倒推时间。"
    "不确定时保留空数组或保守表达。不要创建 Person ID、candidate ID、relation graph ID，不做检索建议，不决定 canonical truth。"
    "只通过被强制调用的 submit_historical_context_card 工具返回，不输出助手 prose。"
)


def _contextual_registry(catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    try:
        return resolver.build_contextual_identity_registry(catalog=catalog)
    except Exception:
        return []


def _entity_seed(case: Mapping[str, Any]) -> dict[str, Any]:
    seed = case.get("seed") if isinstance(case.get("seed"), Mapping) else {}
    return dict(seed)


def _normalization_status(
    entity: Mapping[str, Any],
    result: Mapping[str, Any],
) -> str:
    kind = _text(entity.get("entity_kind"))
    if kind == "structural_kinship_expression":
        return "not_single_person"
    if kind in {"not_person", "generic_role", "collective_persons"}:
        return "not_person"
    if result.get("resolution_status") == "resolved_existing_person" and result.get("resolved_person_id"):
        return "resolved_existing"
    if result.get("resolution_status") == "ambiguous":
        return "ambiguous"
    if kind == "named_person" and len(_matching_form(_text(entity.get("surface")))) >= 2:
        return "resolved_new_candidate"
    return "unresolved"


def normalize_card(
    validation: Mapping[str, Any],
    *,
    case: Mapping[str, Any],
    bundle: Mapping[str, Any],
    known_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
    index: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Project validated text observations into candidate-only Python output."""

    catalog = catalog or hng02.person_catalog()
    index = index or hng02.forms_index(catalog)
    evidence_rows = {
        str(row.get("ref")): dict(row)
        for row in bundle.get("passages", [])
        if isinstance(row, Mapping) and row.get("ref")
    }
    context = "\n".join(_source_text(row) for row in evidence_rows.values())
    registry = _contextual_registry(catalog)
    seed = _entity_seed(case)
    entity_results: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    pid_to_key: dict[str, str] = {}
    candidates: list[dict[str, Any]] = []

    def ensure_existing_candidate(pid: str, result: Mapping[str, Any]) -> str:
        existing = pid_to_key.get(pid)
        if existing:
            return existing
        candidate_key = f"c{len(candidates)}"
        pid_to_key[pid] = candidate_key
        person = catalog.get(pid, {})
        candidates.append(
            {
                "candidate_key": candidate_key,
                "person_id": pid,
                "canonical_name": person.get("canonical_name") or result.get("resolved_label"),
                "known_forms": resolver.catalog_forms(person),
                "candidate_source": "python_existing_catalogue",
            }
        )
        return candidate_key

    for entity in validation.get("valid_entities", []):
        result = resolver.resolve_identity(
            surface=_text(entity.get("surface")),
            seed=seed,
            context=context,
            evidence=evidence_rows,
            catalog=catalog,
            index=index,
            contextual_registry=registry,
            evidence_refs=[_text(entity.get("evidence_ref"))],
        )
        frozen_match = None
        if not result.get("resolved_person_id"):
            frozen_match = _case_candidate_match(_text(entity.get("surface")), case)
            if frozen_match:
                result = {
                    **dict(result),
                    "resolved_person_id": frozen_match.get("person_id"),
                    "resolved_label": frozen_match.get("canonical_name"),
                    "resolution_status": "resolved_existing_person",
                    "resolution_method": "frozen_case_candidate",
                    "confidence": "medium",
                    "candidate_set": [frozen_match.get("person_id")],
                    "context_signals": [*(result.get("context_signals") or []), "existing_case_candidate"],
                }
        status = _normalization_status(entity, result)
        pid = _text(result.get("resolved_person_id")) or None
        candidate_key = pid_to_key.get(pid) if pid else None
        if pid and candidate_key is None:
            candidate_key = ensure_existing_candidate(pid, result)
        elif not pid and status == "resolved_new_candidate":
            candidate_key = f"c{len(candidates)}"
            candidates.append(
                {
                    "candidate_key": candidate_key,
                    "person_id": None,
                    "canonical_name": _text(entity.get("surface")),
                    "known_forms": [_text(entity.get("surface"))],
                    "candidate_source": "python_local_candidate_projection",
                }
            )
        row = {
            "entity_key": entity.get("entity_key"),
            "surface": entity.get("surface"),
            "entity_kind": entity.get("entity_kind"),
            "reference_form": entity.get("reference_form"),
            "evidence_ref": entity.get("evidence_ref"),
            "exact_span": entity.get("exact_span"),
            "identity_status": status,
            "resolved_person_id": pid,
            "candidate_key": candidate_key,
            "resolution_method": result.get("resolution_method"),
            "confidence": result.get("confidence"),
            "candidate_set": result.get("candidate_set", []),
            "context_signals": result.get("context_signals", []),
            "resolver_result": dict(result),
        }
        entity_results.append(row)
        by_key[_text(entity.get("entity_key"))] = row

    # Identity-name relations are textual normalization evidence.  If one
    # entity already resolved uniquely, Python may propagate that identity to
    # the other local entity; the model still never supplies a Person ID.
    for relation in validation.get("valid_relations", []):
        if _text(relation.get("relation_class")) != "identity_name":
            continue
        subject = by_key.get(_text(relation.get("subject_entity_key")))
        object_row = by_key.get(_text(relation.get("object_entity_key")))
        if not subject or not object_row:
            continue
        resolved = [row for row in (subject, object_row) if row.get("resolved_person_id")]
        if len(resolved) != 1:
            continue
        source_row = resolved[0]
        target_row = object_row if source_row is subject else subject
        pid = _text(source_row.get("resolved_person_id"))
        target_row.update(
            {
                "identity_status": "resolved_existing",
                "resolved_person_id": pid,
                "candidate_key": ensure_existing_candidate(pid, source_row.get("resolver_result") or {}),
                "resolution_method": "identity_name_assertion",
                "confidence": relation.get("confidence"),
                "candidate_set": [pid],
                "context_signals": [
                    *(target_row.get("context_signals") or []),
                    "binary_identity_propagation",
                ],
                "identity_propagation": {
                    "relation_id": relation.get("relation_id"),
                    "source_entity_key": source_row.get("entity_key"),
                    "target_entity_key": target_row.get("entity_key"),
                    "evidence_ref": relation.get("evidence_ref"),
                    "exact_span": relation.get("exact_span"),
                },
            }
        )

    relations: list[dict[str, Any]] = []
    known_evidence = known_evidence or {}
    for relation in validation.get("valid_relations", []):
        subject = by_key.get(_text(relation.get("subject_entity_key")))
        object_row = by_key.get(_text(relation.get("object_entity_key")))
        if not subject or not object_row:
            continue
        relation_class = _text(relation.get("relation_class"))
        semantic_level = "hard_relation" if relation_class in {"kinship", "marriage", "identity_name"} else "documented_interaction"
        ref = _text(relation.get("evidence_ref"))
        matching = ref in known_evidence
        relations.append(
            {
                "relation_id": relation.get("relation_id"),
                "person_a": subject.get("resolved_person_id"),
                "person_b": object_row.get("resolved_person_id"),
                "subject_entity_key": subject.get("entity_key"),
                "object_entity_key": object_row.get("entity_key"),
                "relation_surface": relation.get("relation_surface"),
                "relation_class": relation_class,
                "semantic_level": semantic_level,
                "evidence_ref": ref,
                "exact_span": relation.get("exact_span"),
                "confidence": relation.get("confidence"),
                "graph_candidate": relation_class not in {"identity_name"},
                "matches_existing_evidence_ref": matching,
                "canonical_write_back": False,
            }
        )

    temporal: list[dict[str, Any]] = []
    era_index = _load_era_index()
    for item in validation.get("valid_temporal_assertions", []):
        subject = by_key.get(_text(item.get("subject_entity_key"))) if _text(item.get("subject_entity_key")) else None
        normalized = normalize_temporal_surface(_text(item.get("temporal_surface")), era_index)
        temporal.append(
            {
                "temporal_id": item.get("temporal_id"),
                "subject_entity_key": item.get("subject_entity_key"),
                "subject_person_id": subject.get("resolved_person_id") if subject else None,
                "temporal_surface": item.get("temporal_surface"),
                "temporal_type": item.get("temporal_type"),
                "reference_surface": item.get("reference_surface"),
                "evidence_ref": item.get("evidence_ref"),
                "exact_span": item.get("exact_span"),
                "confidence": item.get("confidence"),
                "normalized": normalized,
                "h0a": h0a_compatibility(item, case),
                "canonical_write_back": False,
            }
        )

    return {
        "entities": entity_results,
        "relations": relations,
        "temporal_assertions": temporal,
        "candidates": candidates,
        "candidate_projection_only": True,
        "canonical_write_back": False,
    }


def _chinese_number(value: str) -> int | None:
    digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    value = _text(value)
    if value == "元":
        return 1
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[1:], 0)
    if value.endswith("十"):
        return digits.get(value[:-1], 0) * 10
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 0) * 10 + digits.get(right, 0)
    return digits.get(value)


def _load_era_index() -> dict[str, list[dict[str, Any]]]:
    path = ROOT / "data/annotation/era-cards-e0.json"
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for record in document.get("records", []):
        for era in record.get("era_names", []) if isinstance(record, Mapping) else []:
            if not isinstance(era, Mapping):
                continue
            name = _text((era.get("name") or {}).get("original") if isinstance(era.get("name"), Mapping) else era.get("name"))
            start = era.get("start_year_ce")
            end = era.get("end_year_ce")
            if name and isinstance(start, int):
                result.setdefault(name, []).append({"start_year": start, "end_year": end, "reign_period_id": era.get("reign_period_id")})
    return result


def normalize_temporal_surface(surface: str, era_index: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    for era_name, records in sorted(era_index.items(), key=lambda item: -len(item[0])):
        if era_name not in surface:
            continue
        match = re.search(re.escape(era_name) + r"([元一二三四五六七八九十百]+)年", surface)
        for record in records:
            if match:
                number = _chinese_number(match.group(1))
                if number is not None:
                    year = int(record["start_year"]) + number - 1
                    return {
                        "status": "normalized_by_h0a_era",
                        "era_name": era_name,
                        "year": year,
                        "reign_period_id": record.get("reign_period_id"),
                    }
            return {
                "status": "reign_period_only",
                "era_name": era_name,
                "start_year": record.get("start_year"),
                "end_year": record.get("end_year"),
                "reign_period_id": record.get("reign_period_id"),
            }
    return {"status": "unresolved_expression"}


def _story_id_from_ref(ref: str) -> str | None:
    match = re.search(r"hng[0-9]+-shishuo-([0-9]{2}-[a-z]+-[0-9]{3})", ref)
    return match.group(1) if match else None


def h0a_compatibility(item: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    story_id = _story_id_from_ref(_text(item.get("evidence_ref")))
    if not story_id:
        return {"status": "not_applicable", "reason": "source is not a Story-linked H0A ref"}
    path = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
    if not path.is_file():
        return {"status": "unknown", "reason": "H0A evidence file unavailable"}
    try:
        records = json.loads(path.read_text(encoding="utf-8")).get("records", [])
    except Exception:
        return {"status": "unknown", "reason": "H0A evidence unreadable"}
    matches = [row for row in records if isinstance(row, Mapping) and row.get("story_id") == story_id]
    if not matches:
        return {"status": "not_applicable", "reason": "no H0A evidence for Story"}
    span = _text(item.get("exact_span"))
    surface = _text(item.get("temporal_surface"))
    for row in matches:
        raw = _text(row.get("raw_surface"))
        if raw and (raw in span or surface in raw or raw in surface):
            return {
                "status": "compatible",
                "evidence_id": row.get("evidence_record_id"),
                "raw_surface": raw,
            }
    return {"status": "unknown", "reason": "H0A Story evidence exists but no direct surface match"}


def json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FUNCTION_NAME",
    "STRICT_ENDPOINT",
    "RELATION_CLASSES",
    "TEMPORAL_TYPES",
    "SYSTEM_PROMPT",
    "card_parameters_schema",
    "function_definition",
    "tool_choice",
    "schema_hash",
    "validate_card",
    "select_evidence_bundle",
    "prompt_payload",
    "normalize_card",
    "normalize_temporal_surface",
    "h0a_compatibility",
    "json_hash",
]
