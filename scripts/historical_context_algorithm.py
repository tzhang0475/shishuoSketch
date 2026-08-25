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
PERSON_READ_FUNCTION = "submit_person_evidence_observations"
PERSON_FILL_FUNCTION = "submit_person_card"
TEMPORAL_READ_FUNCTION = "submit_story_temporal_observations"
TEMPORAL_FILL_FUNCTION = "submit_story_temporal_card"
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
PERSON_LIKE_ENTITY_KINDS = {
    "named_person",
    "abbreviated_name",
    "courtesy_name",
    "person_title",
    "person_office_title",
    "kinship_reference",
    "pronoun_reference",
}
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


def _case_candidate_has_hard_conflict(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    candidate_key = _text(candidate.get("candidate_key"))
    person_id = _text(candidate.get("person_id"))
    for check in case.get("constraint_checks") or []:
        if not isinstance(check, Mapping) or check.get("status") != "conflict":
            continue
        check_key = _text(check.get("candidate_key"))
        check_person = _text(check.get("person_id"))
        if (candidate_key and check_key == candidate_key) or (person_id and check_person == person_id):
            return True
    return False


def _source_grounded_identity_expansions(
    validation: Mapping[str, Any],
    *,
    case: Mapping[str, Any],
    evidence_rows: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Recover a full existing name that literally contains the target form.

    This is a textual identity projection, not relation inference.  It is
    allowed only when one frozen existing-Person candidate has a full form
    visibly present in the supplied source and the current target is its
    unique suffix.  The derived identity_name assertion remains provenance
    traceable and is blocked by Python hard conflicts.
    """

    entities = [dict(row) for row in validation.get("valid_entities", [])]
    relations = [dict(row) for row in validation.get("valid_relations", [])]
    target_surface = _text((case.get("observation") or {}).get("surface"))
    target_rows = [
        row for row in entities
        if _text(row.get("surface")) == target_surface
        and _text(row.get("entity_kind")) in PERSON_LIKE_ENTITY_KINDS
    ]
    if not target_surface or len(target_rows) != 1:
        return {**dict(validation), "valid_entities": entities, "valid_relations": relations}, []

    candidates = case.get("candidates") or []
    if isinstance(candidates, Mapping):
        candidates = list(candidates.values())
    matches: list[tuple[dict[str, Any], str, str, str]] = []
    folded_target = _matching_form(target_surface)
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or not _text(candidate.get("person_id")):
            continue
        if _case_candidate_has_hard_conflict(case, candidate):
            continue
        forms = candidate.get("known_forms") or []
        if isinstance(forms, str):
            forms = [forms]
        forms = [str(candidate.get("canonical_name") or ""), *[str(value) for value in forms if _text(value)]]
        for form in sorted(set(forms), key=lambda value: (-len(_matching_form(value)), value)):
            folded_form = _matching_form(form)
            if not form or folded_form == folded_target or not folded_form.endswith(folded_target):
                continue
            occurrences: list[tuple[str, str, str]] = []
            for evidence_ref, evidence_row in evidence_rows.items():
                text = _source_text(evidence_row)
                full_positions = [match.start() for match in re.finditer(re.escape(form), text)]
                target_positions = [match.start() for match in re.finditer(re.escape(target_surface), text)]
                for full_start in full_positions:
                    full_end = full_start + len(form)
                    # A suffix inside the full name is not independent
                    # source-local coreference.  Require a second literal
                    # target occurrence in the same short context.
                    separate = [
                        position for position in target_positions
                        if position < full_start or position >= full_end
                    ]
                    if not separate:
                        continue
                    target_start = min(separate, key=lambda position: (abs(position - full_start), position))
                    span_start = min(full_start, target_start)
                    span_end = max(full_end, target_start + len(target_surface))
                    if span_end - span_start > 300:
                        continue
                    occurrences.append((_text(evidence_ref), text[span_start:span_end], text))
            if occurrences:
                ref, exact_span, _ = occurrences[0]
                matches.append((dict(candidate), form, ref, exact_span))
                break
    unique_people = {_text(candidate.get("person_id")) for candidate, _, _, _ in matches}
    if len(unique_people) != 1:
        return {**dict(validation), "valid_entities": entities, "valid_relations": relations}, []

    candidate, full_form, ref, exact_span = matches[0]
    target = target_rows[0]
    full_entity = next((row for row in entities if _matching_form(_text(row.get("surface"))) == _matching_form(full_form)), None)
    if full_entity is None:
        used_keys = {_text(row.get("entity_key")) for row in entities}
        index = 0
        while f"e{index}" in used_keys:
            index += 1
        full_entity = {
            "entity_key": f"e{index}",
            "surface": full_form,
            "entity_kind": "named_person",
            "reference_form": "full_name",
            "evidence_ref": ref,
            "exact_span": exact_span,
        }
        entities.append(full_entity)
    if any(
        _text(row.get("relation_class")) == "identity_name"
        and {_text(row.get("subject_entity_key")), _text(row.get("object_entity_key"))}
        == {_text(target.get("entity_key")), _text(full_entity.get("entity_key"))}
        for row in relations
    ):
        return {**dict(validation), "valid_entities": entities, "valid_relations": relations}, []

    relation_id = "python-identity-name-expansion-0"
    relation = {
        "relation_id": relation_id,
        "subject_entity_key": target.get("entity_key"),
        "object_entity_key": full_entity.get("entity_key"),
        "relation_surface": full_form,
        "relation_class": "identity_name",
        "evidence_ref": ref,
        "exact_span": exact_span,
        "confidence": "high",
    }
    relations.append(relation)
    derivation = {
        "assertion_id": relation_id,
        "derivation": "target_suffix_within_unique_existing_candidate_form",
        "target_entity_key": target.get("entity_key"),
        "full_name_entity_key": full_entity.get("entity_key"),
        "target_surface": target_surface,
        "full_name_surface": full_form,
        "candidate_key": candidate.get("candidate_key"),
        "person_id": candidate.get("person_id"),
        "evidence_ref": ref,
        "exact_span": exact_span,
        "hard_conflict": False,
        "identity_resolution_basis": "contextual_name_projection",
    }
    return {**dict(validation), "valid_entities": entities, "valid_relations": relations}, [derivation]


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


def _identity_resolution_basis(
    *,
    result: Mapping[str, Any],
    status: str,
    contextual_projection: bool = False,
) -> str:
    """Classify identity provenance without changing the identity decision."""

    if contextual_projection:
        return "contextual_name_projection"
    if status == "resolved_new_candidate":
        return "new_candidate"
    if status in {"unresolved", "ambiguous", "not_person", "not_single_person"}:
        return "unresolved"
    if _text(result.get("resolution_method")) == "identity_name_assertion":
        return "evidence_identity_assertion"
    return "catalogue_exact_match"


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
    validation, identity_expansions = _source_grounded_identity_expansions(
        validation,
        case=case,
        evidence_rows=evidence_rows,
    )
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
        entity_kind = _text(entity.get("entity_kind"))
        person_like = entity_kind in PERSON_LIKE_ENTITY_KINDS
        if person_like:
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
        else:
            result = {
                "surface": _text(entity.get("surface")),
                "resolution_status": "not_applicable",
                "resolution_method": "entity_kind_type_gate",
                "resolved_person_id": None,
                "resolved_label": None,
                "confidence": "unknown",
                "candidate_set": [],
                "context_signals": ["non_person_like_entity_kind"],
            }
        frozen_match = None
        if person_like and not result.get("resolved_person_id"):
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
            "person_resolution": result.get("resolution_status"),
            "resolved_person_id": pid,
            "candidate_key": candidate_key,
            "resolution_method": result.get("resolution_method"),
            "confidence": result.get("confidence"),
            "candidate_set": result.get("candidate_set", []),
            "context_signals": result.get("context_signals", []),
            "resolver_result": dict(result),
        }
        row["identity_resolution_basis"] = _identity_resolution_basis(
            result=result,
            status=status,
        )
        entity_results.append(row)
        by_key[_text(entity.get("entity_key"))] = row

    # Identity-name relations are textual normalization evidence.  If one
    # entity already resolved uniquely, Python may propagate that identity to
    # the other local entity; the model still never supplies a Person ID.
    contextual_projection_targets = {
        _text(row.get("target_entity_key"))
        for row in identity_expansions
        if _text(row.get("target_entity_key"))
    }
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
        if _text(target_row.get("entity_kind")) not in PERSON_LIKE_ENTITY_KINDS:
            continue
        pid = _text(source_row.get("resolved_person_id"))
        contextual_projection = _text(target_row.get("entity_key")) in contextual_projection_targets
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
                "identity_resolution_basis": _identity_resolution_basis(
                    result={"resolution_method": "identity_name_assertion"},
                    status="resolved_existing",
                    contextual_projection=contextual_projection,
                ),
            }
        )

    relations: list[dict[str, Any]] = []
    rejected_normalized_relations: list[dict[str, Any]] = []
    known_evidence = known_evidence or {}
    for relation in validation.get("valid_relations", []):
        subject = by_key.get(_text(relation.get("subject_entity_key")))
        object_row = by_key.get(_text(relation.get("object_entity_key")))
        if not subject or not object_row:
            continue
        relation_class = _text(relation.get("relation_class"))
        subject_person_id = subject.get("resolved_person_id")
        object_person_id = object_row.get("resolved_person_id")
        if (
            relation_class != "identity_name"
            and subject_person_id
            and subject_person_id == object_person_id
        ):
            rejected_normalized_relations.append(
                {
                    "reason": "collapsed_self_relation",
                    "relation": dict(relation),
                    "normalized_subject_person_id": subject_person_id,
                    "normalized_object_person_id": object_person_id,
                    "canonical_write_back": False,
                }
            )
            continue
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
        "rejected_normalized_relations": rejected_normalized_relations,
        "source_grounded_identity_expansions": identity_expansions,
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
    story_id = _text(case.get("story_id")) or _story_id_from_ref(_text(item.get("evidence_ref")))
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


# HNG2-C.1 keeps the consolidated evidence selector and resolver above, but
# splits reading from card filling and separates person work from Story time.
# These wire contracts are intentionally small; all database interpretation
# remains in Python.
PERSON_READ_FUNCTION = "submit_person_evidence_observations"
PERSON_FILL_FUNCTION = "submit_person_card"
TEMPORAL_READ_FUNCTION = "submit_story_temporal_observations"
TEMPORAL_FILL_FUNCTION = "submit_story_temporal_card"

PERSON_OBSERVATION_KINDS = {
    "identity_name", "kinship", "marriage", "office_title",
    "institutional", "interaction", "other",
}
OBSERVATION_CERTAINTY = {"explicit", "probable", "unclear"}
TEMPORAL_OBSERVATION_KINDS = {
    "date", "reign", "era_year", "event", "before_after",
    "person_age", "office_period", "other",
}
TEMPORAL_ROLES = {
    "scene_time", "background_context", "later_outcome",
    "quoted_precedent", "relative_person_time", "office_context",
    "uncertain",
}

# Reporting provenance only; this enum never changes a resolver decision.
IDENTITY_RESOLUTION_BASES = {
    "catalogue_exact_match",
    "evidence_identity_assertion",
    "contextual_name_projection",
    "new_candidate",
    "unresolved",
}

# HNG2-C.2 changes only the READ wire contract.  FILL remains the C.1 card.
PERSON_ATOM_FUNCTION = "submit_person_evidence_atoms"
TEMPORAL_ATOM_FUNCTION = "submit_temporal_evidence_atoms"

PERSON_ATOM_SYSTEM = (
    "只从输入 evidence_text 逐字发现与当前人物 target 直接相关、或解析 target 必需的证据原子。"
    "subject_surface、predicate_surface、object_surface 只要非空，都必须逐字出现在同一 exact_span；"
    "exact_span 必须逐字来自所引 evidence_ref。保留父、弟、妻、辟、拜、除、字、號等史料原词，"
    "不得改写为现代语义标签。atom_kind 可以解释分类；共现不是关系；最多六条。"
)
TEMPORAL_ATOM_SYSTEM = (
    "只从输入 evidence_text 逐字发现与当前 Story 时间理解有关的证据原子，不推断场景年代。"
    "temporal_surface 与 reference_surface 只要非空，都必须逐字出现在同一 exact_span；"
    "exact_span 必须逐字来自所引 evidence_ref。只用 role_hint 区分场景、背景、后事、引典、人物相对时间或官职语境；"
    "后事和引典不得倒推场景时间；最多五条。"
)
PERSON_ATOM_FILL_SYSTEM = (
    "重新阅读给定原文；Python 已验证的 EvidenceAtoms 只是定位原文的指针，不得把 atom_kind 当成既定事实。"
    "只把原文直接支持、与当前 target 有关的信息填入既有 Person Card，不发现无关事实，不创建数据库 ID。"
    "保留关系原词；共现不是关系。最多五个实体、五条关系。"
)
TEMPORAL_ATOM_FILL_SYSTEM = (
    "重新阅读给定 Story 原文；Python 已验证的 TemporalEvidenceAtoms 只是原文指针，不得把 role_hint 当成既定事实。"
    "填入既有 Temporal Card，并区分 scene_time、later_outcome、background_context 与 quoted_precedent；"
    "不修改 H0A。最多四条。"
)
TEMPORAL_ANCHOR_ATOM_SYSTEM = (
    TEMPORAL_ATOM_SYSTEM
    + "输入还包含 Python 机械检出的 visible_temporal_surfaces；它们只是逐字 recall hints，不是历史结论。"
    "必须结合上下文判断其是否构成有意义的时间证据，并区分 scene_time、background_context、later_outcome、"
    "quoted_precedent、relative_person_time、office_context 或 uncertain；不必输出无关 hint。"
)


def _person_atom_schema() -> dict[str, Any]:
    return _object(
        {
            "atom_id": _string("本次回答内部的局部证据原子编号 p0、p1……。"),
            "atom_kind": _enum(
                PERSON_OBSERVATION_KINDS,
                "证据原子的宽类别；这是解释标签，不要求出现在原文中。other 可保留现有分类未覆盖的明示信息。",
            ),
            "subject_surface": _string("主体的史料原词；非空时必须逐字包含在 exact_span 中。"),
            "predicate_surface": _string("关系或身份谓词的史料原词；不得用现代释义改写，非空时必须逐字包含在 exact_span 中。"),
            "object_surface": _string("客体的史料原词；没有明确客体时为空，非空时必须逐字包含在 exact_span 中。"),
            "evidence_ref": _string("必须逐字复制 source_passages 中已有 ref。"),
            "exact_span": _string("包含各非空 surface 的最短连续原文，必须逐字存在于对应 evidence_text。"),
            "certainty": _enum(OBSERVATION_CERTAINTY, "原文表达该证据原子的明确程度。"),
        },
        "Person READ EvidenceAtom。它只保存文本证据，不作数据库身份或关系决定。",
    )


def _temporal_atom_schema() -> dict[str, Any]:
    return _object(
        {
            "atom_id": _string("本次回答内部的局部时间证据原子编号 t0、t1……。"),
            "temporal_surface": _string("史料中的时间原词；非空时必须逐字包含在 exact_span 中。"),
            "reference_surface": _string("时间所绑定的人物、事件或动作原词；非空时必须逐字包含在 exact_span 中。"),
            "role_hint": _enum(TEMPORAL_ROLES, "该原文相对当前 Story 场景的作用提示；不等于 Python 的最终时间判断。"),
            "evidence_ref": _string("必须逐字复制 source_passages 中已有 ref。"),
            "exact_span": _string("包含各非空 surface 的最短连续原文，必须逐字存在于对应 evidence_text。"),
            "certainty": _enum(OBSERVATION_CERTAINTY, "原文表达该时间证据原子的明确程度。"),
        },
        "Temporal READ EvidenceAtom。它只保存文本证据和角色提示，不推断 Story 场景年代。",
    )


def evidence_atom_function_definition(lane: str) -> dict[str, Any]:
    """Return the C.2 READ schema or the unchanged C.1 FILL schema."""

    if lane == "person_read":
        name = PERSON_ATOM_FUNCTION
        parameters = _object(
            {"atoms": _array(_person_atom_schema(), "最多六条 target 相关的逐字证据原子。")},
            "Person READ EvidenceAtom 输出。",
        )
    elif lane == "temporal_read":
        name = TEMPORAL_ATOM_FUNCTION
        parameters = _object(
            {"atoms": _array(_temporal_atom_schema(), "最多五条 Story 时间相关的逐字证据原子。")},
            "Temporal READ EvidenceAtom 输出。",
        )
    elif lane in {"person_fill", "temporal_fill"}:
        return read_fill_function_definition(lane)
    else:
        raise ValueError(f"unknown evidence-atom lane: {lane}")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": parameters["description"],
            "strict": True,
            "parameters": parameters,
        },
    }


def evidence_atom_tool_choice(lane: str) -> dict[str, Any]:
    name = {
        "person_read": PERSON_ATOM_FUNCTION,
        "person_fill": PERSON_FILL_FUNCTION,
        "temporal_read": TEMPORAL_ATOM_FUNCTION,
        "temporal_fill": TEMPORAL_FILL_FUNCTION,
    }[lane]
    return {"type": "function", "function": {"name": name}}


def _person_observation_schema() -> dict[str, Any]:
    return _object(
        {
            "observation_id": _string("局部观察编号 o0、o1……。"),
            "observation_kind": _enum(
                PERSON_OBSERVATION_KINDS,
                "原文信息的宽类别；other 用于原文明示但当前宽分类无法覆盖的信息。",
            ),
            "subject_surface": _string("关系或身份说明的主体原文；必须直接出现在 exact_span 中。"),
            "predicate_surface": _string("原文关系措辞；身份同一可用原文称谓连接方式，无法单独切分时可为空字符串。"),
            "object_surface": _string("关系客体原文；单项官职/身份描述无独立客体时可为空字符串。"),
            "evidence_ref": _string("必须复制 source_passages 中已有 ref。"),
            "exact_span": _string("直接支持观察的最短连续 evidence_text，必须逐字复制。"),
            "certainty": _enum(OBSERVATION_CERTAINTY, "原文表达这一观察的明确程度。"),
        },
        "阅读阶段发现的、与当前 target 直接相关的史料观察；不是数据库事实。",
    )


def _person_fill_entity_schema() -> dict[str, Any]:
    return _object(
        {
            "entity_key": _string("本次回答内部的局部实体编号 e0、e1……。"),
            "surface": _string("史料中实际出现的人物或人物表达。"),
            "entity_kind": _enum(schema.ENTITY_KINDS, "目标或上下文表达在当前原文中的人物语义类别。"),
            "reference_form": _enum(schema.REFERENCE_FORMS, "该表达的语言指称形式，不是数据库身份决定。"),
            "evidence_refs": _array(_string("输入中已有的 source passage ref。"), "实体直接出现的一个或多个 ref。"),
        },
        "Person Fill Card 的局部实体。不得创建 Person ID 或 candidate key。",
    )


def _person_fill_relation_schema() -> dict[str, Any]:
    return _object(
        {
            "relation_id": _string("本次回答内部的局部关系编号 r0、r1……。"),
            "subject_entity_key": _string("关系主体，必须引用本卡 entities 的 eN。"),
            "object_entity_key": _string("关系客体，必须引用本卡 entities 的 eN。"),
            "relation_surface": _string("原文中的关系措辞，例如父、妻、辟、拜、詣、與語。"),
            "relation_class": _enum(RELATION_CLASSES, "宽关系分类；不得升级成持久友谊或政治联盟。"),
            "evidence_ref": _string("直接支持关系的输入 ref。"),
            "exact_span": _string("直接支持关系的最短连续 evidence_text。"),
            "confidence": _enum(CONFIDENCE_LEVELS, "原文是否明确表达该关系的信心。"),
        },
        "仅把经 Python grounding 保留的证据指针重新映射为宽关系卡。",
    )


def _temporal_observation_schema() -> dict[str, Any]:
    return _object(
        {
            "observation_id": _string("局部时间观察编号 t0、t1……。"),
            "temporal_surface": _string("原文中的时间、年号、事件、先后或官职时期表达。"),
            "temporal_kind": _enum(TEMPORAL_OBSERVATION_KINDS, "时间表达的文字类别。"),
            "temporal_role": _enum(
                TEMPORAL_ROLES,
                "该时间相对当前 Story 场景的作用；later_outcome、quoted_precedent 和 background_context 不可用于倒推 scene_time。",
            ),
            "reference_surface": _string("时间表达所绑定的人物、事件或场景原文；没有时可为空字符串。"),
            "evidence_ref": _string("必须复制 source_passages 中已有 ref。"),
            "exact_span": _string("直接支持观察的最短连续 evidence_text，必须逐字复制。"),
            "certainty": _enum(OBSERVATION_CERTAINTY, "原文表达这一时间作用的明确程度。"),
        },
        "只记录与当前 Story/scene 定位有关的时间观察，并区分后果、背景和引述。",
    )


def _temporal_fill_schema() -> dict[str, Any]:
    return _object(
        {
            "temporal_id": _string("本卡内部的局部时间断言编号 t0、t1……。"),
            "temporal_surface": _string("原文中实际出现的时间表达。"),
            "temporal_type": _enum(TEMPORAL_TYPES, "时间表达的宽类型，由 Python 后续映射到 H0A。"),
            "temporal_role": _enum(TEMPORAL_ROLES, "该时间相对 Story 场景的作用。"),
            "reference_surface": _string("时间表达绑定的人物、事件或场景原文；没有时可为空字符串。"),
            "evidence_ref": _string("直接支持断言的输入 ref。"),
            "exact_span": _string("直接支持断言的最短连续 evidence_text。"),
            "confidence": _enum(CONFIDENCE_LEVELS, "原文是否明确表达该时间信息的信心。"),
        },
        "Story Temporal Fill Card 的时间断言；不修改 H0A。",
    )


def read_fill_function_definition(lane: str) -> dict[str, Any]:
    definitions = {
        "person_read": (
            PERSON_READ_FUNCTION,
            _object(
                {"observations": _array(_person_observation_schema(), "最多六条、只涉及当前 target 的阅读观察。")},
                "Person Read 输出；记录史料发现，不做数据库身份决定。",
            ),
        ),
        "person_fill": (
            PERSON_FILL_FUNCTION,
            _object(
                {
                    "entities": _array(_person_fill_entity_schema(), "最多五个必要实体。"),
                    "relations": _array(_person_fill_relation_schema(), "最多五条明确关系。"),
                },
                "Person Fill Card；只把已 grounding 的证据指针映射为局部实体和宽关系。",
            ),
        ),
        "temporal_read": (
            TEMPORAL_READ_FUNCTION,
            _object(
                {"observations": _array(_temporal_observation_schema(), "最多五条与当前 Story 定位有关的时间观察。")},
                "Story Temporal Read 输出。",
            ),
        ),
        "temporal_fill": (
            TEMPORAL_FILL_FUNCTION,
            _object(
                {"temporal_assertions": _array(_temporal_fill_schema(), "最多四条经 grounding 指向的时间断言。")},
                "Story Temporal Fill Card。",
            ),
        ),
    }
    if lane not in definitions:
        raise ValueError(f"unknown read/fill lane: {lane}")
    name, parameters = definitions[lane]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": parameters["description"],
            "strict": True,
            "parameters": parameters,
        },
    }


def read_fill_tool_choice(lane: str) -> dict[str, Any]:
    name = {
        "person_read": PERSON_READ_FUNCTION,
        "person_fill": PERSON_FILL_FUNCTION,
        "temporal_read": TEMPORAL_READ_FUNCTION,
        "temporal_fill": TEMPORAL_FILL_FUNCTION,
    }[lane]
    return {"type": "function", "function": {"name": name}}


PERSON_READ_SYSTEM = (
    "只阅读给定历史原文，发现解决当前人物 target 所必需的明确身份、亲属、婚姻、官职、制度或互动信息。"
    "暂不填写数据库卡，不创建任何 ID，不枚举无关人物或事件。每条观察必须直接涉及 target 或是解析 target 必需的上下文，"
    "并逐字引用输入 evidence_text；共现不是关系，other 可保留当前宽分类无法表达但原文明示的信息。最多六条。"
)
PERSON_FILL_SYSTEM = (
    "重新阅读给定原文，并把 Python 已验证的 observations 仅当作证据指针，不能把其解释预设为真。"
    "只把原文直接支持、与当前 target 有关的信息填入 Person Card，不发现无关新事实，不创建数据库 ID。"
    "保留关系原词；共现不是关系。最多五个实体、五条关系。"
)
TEMPORAL_READ_SYSTEM = (
    "以 Story/scene 而非 Person 为目标，只阅读给定故事和历史上下文，发现用于定位场景时间的明确证据。"
    "严格区分 scene_time、later_outcome、quoted_precedent、background_context、relative_person_time 和 office_context；"
    "后续结果或引文不得倒推场景时间。逐字引用 evidence_text，最多五条，不建立新年代系统。"
)
TEMPORAL_FILL_SYSTEM = (
    "重新阅读给定 Story 原文，并把 Python 已验证的 temporal observations 仅当作证据指针。"
    "将原文支持的时间信息填入小型 Temporal Card，保留其相对场景角色；不把 later_outcome、背景或引文改成 scene_time，"
    "不修改 H0A。最多四条。"
)


def model_visible_evidence_text(raw: str) -> str:
    """Create one deterministic display field without changing source files.

    Existing punctuated Story text should be passed directly.  For legacy
    frozen wikitext windows this conservative projection removes only common
    MediaWiki wrappers while preserving internal historical characters.
    Validation always uses the resulting string, never the raw source.
    """

    value = str(raw or "")
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)

    def template(match: re.Match[str]) -> str:
        body = match.group(1)
        parts = [part.strip() for part in body.split("|")]
        visible = [part for part in parts[1:] if part and "=" not in part]
        return visible[-1] if visible else ""

    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\{\{([^{}]*)\}\}", template, value)
    value = value.replace("'''", "").replace("''", "")
    return value.strip()


def prepare_evidence_window(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = _text(row.get("raw_source") or row.get("text") or row.get("source_text"))
    visible = row.get("evidence_text")
    evidence_text = str(visible) if isinstance(visible, str) else model_visible_evidence_text(raw)
    return {
        "ref": _text(row.get("ref") or row.get("source_ref")),
        "work": row.get("work") or row.get("source_work"),
        "layer": row.get("layer") or row.get("source_layer"),
        "source_form": row.get("source_form") or "legacy_local",
        "locator": row.get("locator"),
        "raw_source": raw,
        "evidence_text": evidence_text,
        "raw_source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "evidence_text_sha256": hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
    }


def evidence_text_map(windows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {
        _text(row.get("ref")): str(row.get("evidence_text") or "")
        for row in windows
        if _text(row.get("ref"))
    }


def _reject(index: int, reason: str, item: Any) -> dict[str, Any]:
    return {"index": index, "reason": reason, "item": item}


def validate_person_read(payload: Any, windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    texts = evidence_text_map(windows)
    rows = payload.get("observations") if isinstance(payload, Mapping) else None
    top_errors = [] if isinstance(rows, list) else ["observations_not_array"]
    rows = rows if isinstance(rows, list) else []
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected = {"observation_id", "observation_kind", "subject_surface", "predicate_surface", "object_surface", "evidence_ref", "exact_span", "certainty"}
    for index, item in enumerate(rows):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != expected:
            reason = "field_set_mismatch"
        else:
            oid = _text(item.get("observation_id")); ref = _text(item.get("evidence_ref")); span = _text(item.get("exact_span"))
            subject = _text(item.get("subject_surface")); obj = _text(item.get("object_surface")); predicate = _text(item.get("predicate_surface"))
            if not re.fullmatch(r"o[0-9]+", oid) or oid in seen:
                reason = "invalid_or_duplicate_observation_id"
            elif item.get("observation_kind") not in PERSON_OBSERVATION_KINDS or item.get("certainty") not in OBSERVATION_CERTAINTY:
                reason = "invalid_enum"
            elif ref not in texts or not span or span not in texts.get(ref, ""):
                reason = "evidence_span_not_found"
            elif not subject or subject not in span:
                reason = "subject_not_grounded"
            elif obj and obj not in span:
                reason = "object_not_grounded"
            elif predicate and predicate not in span:
                reason = "predicate_not_grounded"
            if not reason:
                seen.add(oid)
        if reason:
            rejected.append(_reject(index, reason, item))
        elif len(valid) < 6:
            valid.append(dict(item))
        else:
            rejected.append(_reject(index, "max_observations_exceeded", item))
    return {"valid": not top_errors, "usable": bool(valid) or (not top_errors and not rows), "top_errors": top_errors, "valid_observations": valid, "rejected_observations": rejected}


def validate_person_fill(payload: Any, windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    texts = evidence_text_map(windows)
    top_errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {"valid": False, "usable": False, "top_errors": ["payload_not_object"], "valid_entities": [], "valid_relations": [], "rejected_entities": [], "rejected_relations": []}
    if set(payload) != {"entities", "relations"}:
        top_errors.append("top_field_set_mismatch")
    entities = payload.get("entities") if isinstance(payload.get("entities"), list) else []
    relations = payload.get("relations") if isinstance(payload.get("relations"), list) else []
    valid_entities: list[dict[str, Any]] = []; rejected_entities: list[dict[str, Any]] = []; seen: set[str] = set()
    efields = {"entity_key", "surface", "entity_kind", "reference_form", "evidence_refs"}
    for index, item in enumerate(entities):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != efields:
            reason = "field_set_mismatch"
        else:
            key = _text(item.get("entity_key")); surface = _text(item.get("surface")); refs = item.get("evidence_refs")
            if not LOCAL_ENTITY.fullmatch(key) or key in seen:
                reason = "invalid_or_duplicate_entity_key"
            elif item.get("entity_kind") not in schema.ENTITY_KINDS or item.get("reference_form") not in schema.REFERENCE_FORMS:
                reason = "invalid_enum"
            elif not isinstance(refs, list) or not refs or any(_text(ref) not in texts for ref in refs):
                reason = "invalid_evidence_refs"
            elif not surface or not any(surface in texts[_text(ref)] for ref in refs):
                reason = "surface_not_grounded"
            if not reason:
                seen.add(key)
        if reason:
            rejected_entities.append(_reject(index, reason, item))
        elif len(valid_entities) < 5:
            valid_entities.append(dict(item))
        else:
            rejected_entities.append(_reject(index, "max_entities_exceeded", item))
    valid_relations: list[dict[str, Any]] = []; rejected_relations: list[dict[str, Any]] = []; rseen: set[str] = set()
    rfields = {"relation_id", "subject_entity_key", "object_entity_key", "relation_surface", "relation_class", "evidence_ref", "exact_span", "confidence"}
    for index, item in enumerate(relations):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != rfields:
            reason = "field_set_mismatch"
        else:
            rid = _text(item.get("relation_id")); subject = _text(item.get("subject_entity_key")); obj = _text(item.get("object_entity_key")); ref = _text(item.get("evidence_ref")); span = _text(item.get("exact_span")); surface = _text(item.get("relation_surface"))
            if not LOCAL_RELATION.fullmatch(rid) or rid in rseen:
                reason = "invalid_or_duplicate_relation_id"
            elif subject not in seen or obj not in seen:
                reason = "unknown_entity_key"
            elif subject == obj and item.get("relation_class") != "identity_name":
                reason = "self_relation"
            elif item.get("relation_class") not in RELATION_CLASSES or item.get("confidence") not in CONFIDENCE_LEVELS:
                reason = "invalid_enum"
            elif ref not in texts or not span or span not in texts.get(ref, ""):
                reason = "evidence_span_not_found"
            elif not surface or surface not in span:
                reason = "relation_surface_not_grounded"
            if not reason:
                rseen.add(rid)
        if reason:
            rejected_relations.append(_reject(index, reason, item))
        elif len(valid_relations) < 5:
            valid_relations.append(dict(item))
        else:
            rejected_relations.append(_reject(index, "max_relations_exceeded", item))
    return {"valid": not top_errors, "usable": bool(valid_entities), "top_errors": top_errors, "valid_entities": valid_entities, "valid_relations": valid_relations, "rejected_entities": rejected_entities, "rejected_relations": rejected_relations}


def validate_temporal_read(payload: Any, windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    texts = evidence_text_map(windows)
    rows = payload.get("observations") if isinstance(payload, Mapping) else None
    top_errors = [] if isinstance(rows, list) else ["observations_not_array"]
    rows = rows if isinstance(rows, list) else []
    valid: list[dict[str, Any]] = []; rejected: list[dict[str, Any]] = []; seen: set[str] = set()
    fields = {"observation_id", "temporal_surface", "temporal_kind", "temporal_role", "reference_surface", "evidence_ref", "exact_span", "certainty"}
    for index, item in enumerate(rows):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != fields:
            reason = "field_set_mismatch"
        else:
            oid = _text(item.get("observation_id")); surface = _text(item.get("temporal_surface")); ref = _text(item.get("evidence_ref")); span = _text(item.get("exact_span")); reference = _text(item.get("reference_surface"))
            if not re.fullmatch(r"t[0-9]+", oid) or oid in seen:
                reason = "invalid_or_duplicate_observation_id"
            elif item.get("temporal_kind") not in TEMPORAL_OBSERVATION_KINDS or item.get("temporal_role") not in TEMPORAL_ROLES or item.get("certainty") not in OBSERVATION_CERTAINTY:
                reason = "invalid_enum"
            elif ref not in texts or not span or span not in texts.get(ref, ""):
                reason = "evidence_span_not_found"
            elif not surface or surface not in span:
                reason = "temporal_surface_not_grounded"
            elif reference and reference not in span:
                reason = "reference_surface_not_grounded"
            if not reason:
                seen.add(oid)
        if reason:
            rejected.append(_reject(index, reason, item))
        elif len(valid) < 5:
            valid.append(dict(item))
        else:
            rejected.append(_reject(index, "max_observations_exceeded", item))
    return {"valid": not top_errors, "usable": bool(valid) or (not top_errors and not rows), "top_errors": top_errors, "valid_observations": valid, "rejected_observations": rejected}


def validate_temporal_fill(payload: Any, windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    texts = evidence_text_map(windows)
    rows = payload.get("temporal_assertions") if isinstance(payload, Mapping) else None
    top_errors = [] if isinstance(rows, list) else ["temporal_assertions_not_array"]
    rows = rows if isinstance(rows, list) else []
    valid: list[dict[str, Any]] = []; rejected: list[dict[str, Any]] = []; seen: set[str] = set()
    fields = {"temporal_id", "temporal_surface", "temporal_type", "temporal_role", "reference_surface", "evidence_ref", "exact_span", "confidence"}
    for index, item in enumerate(rows):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != fields:
            reason = "field_set_mismatch"
        else:
            tid = _text(item.get("temporal_id")); surface = _text(item.get("temporal_surface")); ref = _text(item.get("evidence_ref")); span = _text(item.get("exact_span")); reference = _text(item.get("reference_surface"))
            if not LOCAL_TEMPORAL.fullmatch(tid) or tid in seen:
                reason = "invalid_or_duplicate_temporal_id"
            elif item.get("temporal_type") not in TEMPORAL_TYPES or item.get("temporal_role") not in TEMPORAL_ROLES or item.get("confidence") not in CONFIDENCE_LEVELS:
                reason = "invalid_enum"
            elif ref not in texts or not span or span not in texts.get(ref, ""):
                reason = "evidence_span_not_found"
            elif not surface or surface not in span:
                reason = "temporal_surface_not_grounded"
            elif reference and reference not in span:
                reason = "reference_surface_not_grounded"
            if not reason:
                seen.add(tid)
        if reason:
            rejected.append(_reject(index, reason, item))
        elif len(valid) < 4:
            valid.append(dict(item))
        else:
            rejected.append(_reject(index, "max_temporal_assertions_exceeded", item))
    return {"valid": not top_errors, "usable": bool(valid) or (not top_errors and not rows), "top_errors": top_errors, "valid_temporal_assertions": valid, "rejected_temporal_assertions": rejected}


def validate_person_atoms(payload: Any, windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Ground C.2 Person atoms against exactly the displayed evidence_text."""

    texts = evidence_text_map(windows)
    rows = payload.get("atoms") if isinstance(payload, Mapping) else None
    top_errors = [] if isinstance(rows, list) else ["atoms_not_array"]
    rows = rows if isinstance(rows, list) else []
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    fields = {
        "atom_id", "atom_kind", "subject_surface", "predicate_surface",
        "object_surface", "evidence_ref", "exact_span", "certainty",
    }
    for index, item in enumerate(rows):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != fields:
            reason = "field_set_mismatch"
        else:
            atom_id = _text(item.get("atom_id"))
            ref = _text(item.get("evidence_ref"))
            span = str(item.get("exact_span") or "")
            subject = str(item.get("subject_surface") or "")
            predicate = str(item.get("predicate_surface") or "")
            obj = str(item.get("object_surface") or "")
            if not re.fullmatch(r"p[0-9]+", atom_id) or atom_id in seen:
                reason = "invalid_or_duplicate_atom_id"
            elif item.get("atom_kind") not in PERSON_OBSERVATION_KINDS or item.get("certainty") not in OBSERVATION_CERTAINTY:
                reason = "invalid_enum"
            elif not span or ref not in texts or span not in texts[ref]:
                reason = "exact_span_missing"
            elif subject and subject not in span:
                reason = "subject_not_in_span"
            elif predicate and predicate not in span:
                reason = "predicate_not_in_span"
            elif obj and obj not in span:
                reason = "object_not_in_span"
            if not reason:
                seen.add(atom_id)
        if reason:
            rejected.append(_reject(index, reason, item))
        elif len(valid) < 6:
            valid.append(dict(item))
        else:
            rejected.append(_reject(index, "max_atoms_exceeded", item))
    return {
        "valid": not top_errors,
        "usable": bool(valid) or (not top_errors and not rows),
        "top_errors": top_errors,
        "valid_atoms": valid,
        "rejected_atoms": rejected,
    }


def validate_temporal_atoms(payload: Any, windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Ground C.2 Temporal atoms against exactly the displayed evidence_text."""

    texts = evidence_text_map(windows)
    rows = payload.get("atoms") if isinstance(payload, Mapping) else None
    top_errors = [] if isinstance(rows, list) else ["atoms_not_array"]
    rows = rows if isinstance(rows, list) else []
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    fields = {
        "atom_id", "temporal_surface", "reference_surface", "role_hint",
        "evidence_ref", "exact_span", "certainty",
    }
    for index, item in enumerate(rows):
        reason = ""
        if not isinstance(item, Mapping) or set(item) != fields:
            reason = "field_set_mismatch"
        else:
            atom_id = _text(item.get("atom_id"))
            ref = _text(item.get("evidence_ref"))
            span = str(item.get("exact_span") or "")
            surface = str(item.get("temporal_surface") or "")
            reference = str(item.get("reference_surface") or "")
            if not re.fullmatch(r"t[0-9]+", atom_id) or atom_id in seen:
                reason = "invalid_or_duplicate_atom_id"
            elif item.get("role_hint") not in TEMPORAL_ROLES or item.get("certainty") not in OBSERVATION_CERTAINTY:
                reason = "invalid_enum"
            elif not span or ref not in texts or span not in texts[ref]:
                reason = "exact_span_missing"
            elif surface and surface not in span:
                reason = "temporal_surface_not_in_span"
            elif reference and reference not in span:
                reason = "reference_surface_not_in_span"
            if not reason:
                seen.add(atom_id)
        if reason:
            rejected.append(_reject(index, reason, item))
        elif len(valid) < 5:
            valid.append(dict(item))
        else:
            rejected.append(_reject(index, "max_atoms_exceeded", item))
    return {
        "valid": not top_errors,
        "usable": bool(valid) or (not top_errors and not rows),
        "top_errors": top_errors,
        "valid_atoms": valid,
        "rejected_atoms": rejected,
    }


def person_atom_fill_prompt(target: Mapping[str, Any], grounded: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    atoms = list(grounded.get("valid_atoms", []))
    refs = {_text(row.get("evidence_ref")) for row in atoms}
    selected = [dict(row) for row in windows if _text(row.get("ref")) in refs]
    return {
        "target": dict(target),
        "validated_evidence_atoms": atoms,
        "source_passages": _model_windows(selected),
    }


def temporal_atom_fill_prompt(story: Mapping[str, Any], grounded: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    atoms = list(grounded.get("valid_atoms", []))
    refs = {_text(row.get("evidence_ref")) for row in atoms}
    selected = [dict(row) for row in windows if _text(row.get("ref")) in refs]
    return {
        "story": dict(story),
        "validated_temporal_evidence_atoms": atoms,
        "source_passages": _model_windows(selected),
    }


def _original_surface(value: Any) -> str:
    if isinstance(value, Mapping):
        return _text(value.get("original") or value.get("traditional") or value.get("name"))
    return _text(value)


def visible_temporal_anchor_registry() -> dict[str, dict[str, Any]]:
    """Build a lexical-only anchor registry from frozen H0A data."""

    result: dict[str, dict[str, Any]] = {}

    def add(surface: str, kind: str, source: str) -> None:
        surface = _text(surface)
        if len(surface) < 2:
            return
        row = result.setdefault(surface, {"surface": surface, "registry_kinds": [], "registry_sources": []})
        if kind not in row["registry_kinds"]:
            row["registry_kinds"].append(kind)
        if source not in row["registry_sources"]:
            row["registry_sources"].append(source)

    rulers_path = ROOT / "data/annotation/ruler-identities-e0.json"
    if rulers_path.is_file():
        for row in json.loads(rulers_path.read_text(encoding="utf-8")).get("records", []):
            add(_original_surface(row.get("canonical_title")), "ruler_title", "ruler-identities-e0")
            for alias in row.get("aliases", []):
                add(_original_surface(alias), "ruler_title", "ruler-identities-e0")

    evidence_path = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
    if evidence_path.is_file():
        for row in json.loads(evidence_path.read_text(encoding="utf-8")).get("records", []):
            candidate = row.get("normalized_candidate") if isinstance(row.get("normalized_candidate"), Mapping) else {}
            era_name = _text(candidate.get("era_name"))
            if era_name:
                add(era_name, "reign_name", "story-temporal-evidence-h0a")

    events_path = ROOT / "data/annotation/historical-events-h0a.json"
    if events_path.is_file():
        for row in json.loads(events_path.read_text(encoding="utf-8")).get("records", []):
            names = [_text(row.get("canonical_name")), *[_text(value) for value in row.get("aliases", [])]]
            for name in names:
                add(name, "historical_event", "historical-events-h0a")
            canonical = _text(row.get("canonical_name"))
            stem = re.split(r"之[亂难難]", canonical, maxsplit=1)[0]
            if stem and stem != canonical:
                add(stem, "historical_event_actor", "historical-events-h0a")

    return {key: result[key] for key in sorted(result, key=lambda value: (-len(value), value))}


def scan_visible_temporal_anchors(windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Report literal temporal-looking surfaces without assigning semantics."""

    registry = visible_temporal_anchor_registry()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    era_names = [surface for surface, row in registry.items() if "reign_name" in row.get("registry_kinds", [])]
    era_alternation = "|".join(re.escape(value) for value in sorted(era_names, key=lambda value: (-len(value), value)))
    year_number = r"(?:元|[一二三四五六七八九十百千〇零兩两0-9]+)年"
    explicit_date = re.compile(
        (rf"(?:{era_alternation}){year_number}|" if era_alternation else "")
        + year_number
        + r"|(?:歲|岁)在[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"
    )
    for window in windows:
        ref = _text(window.get("ref"))
        text = str(window.get("evidence_text") or "")
        for surface, registry_row in registry.items():
            start = 0
            while True:
                position = text.find(surface, start)
                if position < 0:
                    break
                key = (ref, surface, position)
                if key not in seen:
                    seen.add(key)
                    rows.append(
                        {
                            "surface": surface,
                            "evidence_ref": ref,
                            "exact_occurrence": surface,
                            "char_start": position,
                            "char_end_exclusive": position + len(surface),
                            "lexical_source": "historical_registry",
                            "registry_kinds": registry_row["registry_kinds"],
                        }
                    )
                start = position + len(surface)
        for match in explicit_date.finditer(text):
            surface = match.group(0)
            key = (ref, surface, match.start())
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "surface": surface,
                    "evidence_ref": ref,
                    "exact_occurrence": surface,
                    "char_start": match.start(),
                    "char_end_exclusive": match.end(),
                    "lexical_source": "explicit_date_pattern",
                    "registry_kinds": ["explicit_date_pattern"],
                }
            )
    return sorted(rows, key=lambda row: (_text(row.get("evidence_ref")), int(row.get("char_start") or 0), -len(_text(row.get("surface"))), _text(row.get("surface"))))


def person_fill_prompt(target: Mapping[str, Any], grounded: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    refs = {_text(row.get("evidence_ref")) for row in grounded.get("valid_observations", [])}
    selected = [dict(row) for row in windows if _text(row.get("ref")) in refs] or [dict(row) for row in windows]
    return {"target": dict(target), "validated_observation_pointers": grounded.get("valid_observations", []), "source_passages": _model_windows(selected)}


def temporal_fill_prompt(story: Mapping[str, Any], grounded: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    refs = {_text(row.get("evidence_ref")) for row in grounded.get("valid_observations", [])}
    selected = [dict(row) for row in windows if _text(row.get("ref")) in refs] or [dict(row) for row in windows]
    return {"story": dict(story), "validated_temporal_pointers": grounded.get("valid_observations", []), "source_passages": _model_windows(selected)}


def _model_windows(windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"ref": row.get("ref"), "work": row.get("work"), "layer": row.get("layer"), "source_form": row.get("source_form"), "evidence_text": row.get("evidence_text")}
        for row in windows
    ]


def person_read_prompt(target: Mapping[str, Any], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"target": dict(target), "source_passages": _model_windows(windows)}


def temporal_read_prompt(
    story: Mapping[str, Any],
    windows: Sequence[Mapping[str, Any]],
    visible_temporal_surfaces: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {"story": dict(story), "source_passages": _model_windows(windows)}
    if visible_temporal_surfaces is not None:
        payload["visible_temporal_surfaces"] = [dict(row) for row in visible_temporal_surfaces]
    return payload


def normalize_person_fill(
    validation: Mapping[str, Any], *, case: Mapping[str, Any], windows: Sequence[Mapping[str, Any]], known_evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Adapt the split Person Card to the consolidated candidate projector."""

    texts = evidence_text_map(windows)
    old_entities: list[dict[str, Any]] = []
    for row in validation.get("valid_entities", []):
        ref = next((_text(ref) for ref in row.get("evidence_refs", []) if _text(row.get("surface")) in texts.get(_text(ref), "")), "")
        if not ref:
            continue
        old_entities.append({
            "entity_key": row.get("entity_key"), "surface": row.get("surface"), "entity_kind": row.get("entity_kind"),
            "reference_form": row.get("reference_form"), "evidence_ref": ref, "exact_span": row.get("surface"),
        })
    adapted = {
        "valid_entities": old_entities,
        "valid_relations": list(validation.get("valid_relations", [])),
        "valid_temporal_assertions": [],
    }
    bundle = {"passages": [{"ref": row.get("ref"), "text": row.get("evidence_text"), "work": row.get("work"), "layer": row.get("layer"), "source_form": row.get("source_form")} for row in windows]}
    return normalize_card(adapted, case=case, bundle=bundle, known_evidence=known_evidence or {})


def normalize_story_temporal(validation: Mapping[str, Any], *, story_id: str) -> dict[str, Any]:
    era_index = _load_era_index()
    case = {"story_id": story_id}
    rows: list[dict[str, Any]] = []
    for item in validation.get("valid_temporal_assertions", []):
        role = _text(item.get("temporal_role"))
        normalized = normalize_temporal_surface(_text(item.get("temporal_surface")), era_index)
        h0a_item = dict(item)
        # The canonical Story evidence ref format lets h0a_compatibility reuse
        # the reviewed temporal backbone without changing it.
        h0a = story_temporal_h0a_compatibility(h0a_item, story_id)
        scene_candidate = role == "scene_time" and h0a.get("status") != "conflict"
        rows.append({
            **dict(item),
            "normalized": normalized,
            "h0a": h0a,
            "scene_constraint_candidate": scene_candidate,
            "excluded_from_scene_constraint_reason": None if scene_candidate else ("h0a_conflict" if h0a.get("status") == "conflict" else role),
            "candidate_projection_only": True,
            "canonical_write_back": False,
        })
    return {"story_id": story_id, "temporal_assertions": rows, "candidate_projection_only": True, "h0a_write_back": False, "canonical_write_back": False}


def story_temporal_h0a_compatibility(item: Mapping[str, Any], story_id: str) -> dict[str, Any]:
    """Compare a Story-focused temporal role with the frozen H0A backbone."""

    evidence_path = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
    anchor_path = ROOT / "data/annotation/story-temporal-anchors-h0a.json"
    if not evidence_path.is_file() or not anchor_path.is_file():
        return {"status": "unknown", "reason": "H0A files unavailable"}
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")).get("records", [])
    anchors = json.loads(anchor_path.read_text(encoding="utf-8")).get("records", [])
    span = _text(item.get("exact_span")); surface = _text(item.get("temporal_surface")); role = _text(item.get("temporal_role"))
    evidence_ref = _text(item.get("evidence_ref"))
    ref_section = "main_text" if evidence_ref.endswith("-main") else ("liu_annotation" if "-liu-" in evidence_ref else "")
    annotation_match = re.search(r"-liu-(annotation-[0-9]+)$", evidence_ref)
    ref_annotation = annotation_match.group(1) if annotation_match else None
    matches = []
    for row in evidence:
        if not isinstance(row, Mapping) or row.get("story_id") != story_id:
            continue
        raw = _text(row.get("raw_surface"))
        if raw and (raw in span or surface in raw or raw in surface):
            source_span = row.get("source_span") if isinstance(row.get("source_span"), Mapping) else {}
            source_section = _text(source_span.get("section"))
            source_annotation = _text(source_span.get("annotation_id")) or None
            source_match = bool(
                ref_section
                and source_section == ref_section
                and (ref_section != "liu_annotation" or ref_annotation == source_annotation)
            )
            matches.append((dict(row), source_match, len(raw)))
    role_map = {
        "direct_story_time": {"scene_time"},
        "later_outcome": {"later_outcome"},
        "quoted_ancient_precedent": {"quoted_precedent"},
        "earlier_background": {"background_context"},
        "person_activity_context": {"relative_person_time", "later_outcome", "office_context", "uncertain"},
        "event_context": {"scene_time", "background_context", "uncertain"},
    }
    # Prefer the exact Story layer/annotation and the longest matching H0A
    # surface.  A shorter era-name substring in another annotation must not
    # override an exact era-year expression in the current passage.
    for row, _, _ in sorted(matches, key=lambda value: (-int(value[1]), -value[2], _text(value[0].get("evidence_record_id")))):
        expected = role_map.get(_text(row.get("relation_to_story")), {"uncertain"})
        if role not in expected and role != "uncertain":
            return {
                "status": "conflict",
                "reason": "temporal_role_conflicts_with_h0a",
                "evidence_id": row.get("evidence_record_id"),
                "h0a_relation_to_story": row.get("relation_to_story"),
                "model_temporal_role": role,
            }
        return {
            "status": "compatible",
            "evidence_id": row.get("evidence_record_id"),
            "raw_surface": row.get("raw_surface"),
            "h0a_relation_to_story": row.get("relation_to_story"),
        }
    normalized = normalize_temporal_surface(surface, _load_era_index())
    if role == "scene_time" and normalized.get("year") is not None:
        anchor = next((row for row in anchors if isinstance(row, Mapping) and row.get("story_id") == story_id), None)
        if anchor and anchor.get("start_year_ce") is not None and anchor.get("end_year_ce") is not None:
            year = int(normalized["year"])
            if not int(anchor["start_year_ce"]) <= year <= int(anchor["end_year_ce"]):
                return {"status": "conflict", "reason": "normalized_year_outside_h0a_anchor", "year": year, "anchor": [anchor.get("start_year_ce"), anchor.get("end_year_ce")]}
    return {"status": "unknown", "reason": "no_direct_h0a_surface_match"}


__all__ = [
    "FUNCTION_NAME",
    "PERSON_READ_FUNCTION",
    "PERSON_FILL_FUNCTION",
    "TEMPORAL_READ_FUNCTION",
    "TEMPORAL_FILL_FUNCTION",
    "PERSON_ATOM_FUNCTION",
    "TEMPORAL_ATOM_FUNCTION",
    "IDENTITY_RESOLUTION_BASES",
    "STRICT_ENDPOINT",
    "RELATION_CLASSES",
    "TEMPORAL_TYPES",
    "SYSTEM_PROMPT",
    "PERSON_READ_SYSTEM",
    "PERSON_FILL_SYSTEM",
    "TEMPORAL_READ_SYSTEM",
    "TEMPORAL_FILL_SYSTEM",
    "PERSON_ATOM_SYSTEM",
    "TEMPORAL_ATOM_SYSTEM",
    "PERSON_ATOM_FILL_SYSTEM",
    "TEMPORAL_ATOM_FILL_SYSTEM",
    "TEMPORAL_ANCHOR_ATOM_SYSTEM",
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
    "read_fill_function_definition",
    "read_fill_tool_choice",
    "evidence_atom_function_definition",
    "evidence_atom_tool_choice",
    "model_visible_evidence_text",
    "prepare_evidence_window",
    "evidence_text_map",
    "person_read_prompt",
    "person_fill_prompt",
    "temporal_read_prompt",
    "temporal_fill_prompt",
    "person_atom_fill_prompt",
    "temporal_atom_fill_prompt",
    "visible_temporal_anchor_registry",
    "scan_visible_temporal_anchors",
    "validate_person_read",
    "validate_person_fill",
    "validate_temporal_read",
    "validate_person_atoms",
    "validate_temporal_atoms",
    "validate_temporal_fill",
    "normalize_person_fill",
    "normalize_story_temporal",
    "story_temporal_h0a_compatibility",
]
