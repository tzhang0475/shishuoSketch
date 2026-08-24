#!/usr/bin/env python3
"""DeepSeek strict Function Calling wire contract for HNG2-SC.

The wire contract is a strict-compatible projection of the existing
Historical Entity Schema V1.  It deliberately does not introduce a second
set of historical meanings: enum values are imported from
``historical_entity_schema`` and nullable Python values use an explicit empty
string/object sentinel on the wire.  ``wire_to_controller_payload`` converts
that transport representation back to the controller's existing payload
shape before the normal Python validator runs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import historical_entity_schema as schema


FUNCTION_NAME = "submit_historical_entity_card"
STRICT_ENDPOINT = "https://api.deepseek.com/beta"
STRICT_COMPLETIONS_ENDPOINT = f"{STRICT_ENDPOINT}/chat/completions"


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _enum(values: set[str], description: str, labels: Mapping[str, str] | None = None) -> dict[str, Any]:
    labels = labels or {}
    value_text = "；".join(f"{value}：{labels.get(value, '')}".rstrip("：") for value in sorted(values))
    return {
        "type": "string",
        "enum": sorted(values),
        "description": f"{description} 可用值：{value_text}。不得使用同义词或其他字符串。",
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


def _nullable_wire_string(description: str) -> dict[str, Any]:
    """Strict-compatible nullable string.

    DeepSeek strict mode requires every object property to be required.  The
    wire form therefore uses a required string and reserves ``""`` for the
    Python ``None`` value.  This is a transport convention only; the
    controller receives its existing nullable representation after conversion.
    """

    return {
        "type": "string",
        "description": f"{description} 若语义上不存在，填写空字符串；Python 会将空字符串还原为 null。",
    }


ENTITY_KIND_LABELS = {
    "named_person": "明确姓名",
    "person_title": "帝王、爵号或尊号等人物称号",
    "person_office_title": "官职称谓指人",
    "courtesy_name": "字或字号",
    "abbreviated_name": "简称或历史语境中的省称",
    "kinship_reference": "亲属指代",
    "pronoun_reference": "代词指代",
    "structural_kinship_expression": "结构性亲属表达，不自动视为一个人物",
    "generic_role": "泛称或角色词",
    "collective_persons": "集合性人物表达",
    "not_person": "并非人物表达",
    "unknown": "暂不能判断",
}
REFERENCE_FORM_LABELS = {
    "full_name": "完整姓名",
    "courtesy": "字号",
    "title_only": "单独称号",
    "office_title_only": "单独官职称谓",
    "abbreviated": "简称",
    "kinship_plus_name": "亲属词加姓名或简称",
    "implicit": "隐含指代",
    "anonymous": "匿名人物",
    "unknown": "未知",
}
DISCOURSE_ROLE_LABELS = {
    "event_participant": "事件参与者",
    "speaker": "说话者",
    "referenced_person": "被谈论或指涉的人物",
    "kinship_node": "亲属链中的人物节点",
    "cited_author": "引书、引文所署作者",
    "text_author": "本文作者或史家",
    "commentator": "注家或评论者",
    "office_holder": "官职持有者",
    "unknown": "未知",
}
ASSESSMENT_STATUS_LABELS = {
    "assessed": "可以基于当前文本做判断",
    "insufficient_context": "当前文本不足以进行语义判断",
    "not_applicable": "当前问题不适用该类判断",
    "invalid": "输入本身存在无法解释的问题",
}
SEMANTIC_FIT_LABELS = {
    "strong_support": "文本语义强支持",
    "support": "文本语义支持",
    "compatible": "文本语义相容但不充分",
    "weak": "文本语义弱支持",
    "unknown": "文本语义未知",
    "conflict": "文本语义冲突",
}
CONFIDENCE_LABELS = {
    "high": "模型认为原文明确表达该语义",
    "medium": "模型认为原文有较可靠但非决定性支持",
    "low": "模型认为支持很弱",
    "unknown": "无法判断",
}
RECOMMENDATION_LABELS = {
    "choose_candidate": "现有 candidate 中唯一得到足够语义支持者",
    "new_person_candidate": "原文明显是可独立识别的人物，但候选表中没有对应人物",
    "ambiguous": "两个或更多候选仍有合理可能",
    "unresolved": "知道是人物，但现有证据不足以确定是谁",
    "not_a_single_person": "目标表达不是一个单独人物，例如复杂亲属结构",
    "not_a_person": "目标表达并非人物",
}
ASSERTION_TYPE_LABELS = {
    "identity_equivalence": "原文明确表明两个表达指同一人物，例如武皇帝与炎",
    "alias_of": "一个名称是同一人物的别名或异称",
    "courtesy_name_of": "明确的名—字关系，例如炎，字安世",
    "title_of": "某称号、爵号或尊号明确属于某人物",
    "office_held_by": "某官职明确由某人物担任",
    "parent_child": "原文明确存在父母—子女关系",
    "sibling": "原文明确存在兄弟姊妹关系",
    "kinship_relation": "存在其他明确亲属关系，但不能精确表示为父子或兄弟",
    "participates_in_event": "人物在叙述事件中实际行动或参与，不用于书名作者或旁及人物",
    "temporal_statement": "原文明确给出与人物相关的时代、年份、先后或时间边界",
    "person_mention": "原文明确提及人物，但没有更具体关系可抽取",
}


def evidence_span_schema() -> dict[str, Any]:
    return _object(
        {
            "ref": _string("直接支持判断的系统 source passage ref，必须逐字复制输入中的 ref。"),
            "span": _string("支持判断的最短连续原文，必须原样存在于该 ref 对应文本中。"),
        },
        "一个可由 Python 验证的 source ref 与连续原文片段。",
    )


def evidence_entity_schema() -> dict[str, Any]:
    return _object(
        {
            "entity_key": _string("本次回答内部的局部实体编号，如 e0、e1；不是 Person ID、candidate key 或 graph ID。"),
            "surface": _string("史料中实际出现、需要解释的文字形式，例如庾太尉、炎、元規、喜弟預女。"),
            "entity_kind": _enum(schema.ENTITY_KINDS, "该表达在当前语境中的人物语义类别。", ENTITY_KIND_LABELS),
            "reference_form": _enum(schema.REFERENCE_FORMS, "该表达通过什么语言形式指向人物；这是语言形式，不是最终身份判断。", REFERENCE_FORM_LABELS),
            "evidence_ref": _string("该实体来自哪一条系统提供的 source passage ref；不得自行生成。"),
            "evidence_span": _string("能够证明该实体解释的最短连续原文；不得写解释或改写。"),
        },
        "这部分只记录解决当前 ResearchGap 所必需的史料实体表达，不做全文人物抽取。",
    )


def evidence_assertion_schema() -> dict[str, Any]:
    return _object(
        {
            "assertion_id": _string("本次回答内部的局部断言编号，如 a0、a1。"),
            "assertion_type": _enum(schema.EVIDENCE_ASSERTION_TYPES, "原文明确支持的实体之间语义关系。", ASSERTION_TYPE_LABELS),
            "subject_entity_key": _string("断言主体，必须引用 entities 中已声明的 eN。"),
            "object_entity_key": _nullable_wire_string("断言所涉及的第二实体；没有第二实体时为空字符串"),
            "value": _nullable_wire_string("只有断言需要表达非实体内容时填写，如事件描述或时间信息；不得替代实体。"),
            "direction": _nullable_wire_string("关系存在明确方向时填写，例如 parent_to_child；不确定时为空字符串。"),
            "evidence_ref": _string("直接支持该断言的 source passage ref。"),
            "evidence_span": _string("直接证明该断言的最短连续原文，不得写解释或改写。"),
            "confidence": _enum(schema.CONFIDENCE_LEVELS, "对这段原文是否明确表达该语义的信心，不是数据库最终事实真实性。", CONFIDENCE_LABELS),
        },
        "每个 assertion 都必须由 evidence_span 中的连续原文直接支持；模型断言不是数据库最终事实。",
    )


def evidence_interpretation_schema() -> dict[str, Any]:
    return _object(
        {
            "target_entity_key": _nullable_wire_string("当前 ResearchGap 所研究的目标表达对应的 EvidenceEntity，如庾太尉；不得指向同段其他人物。目标无法表示时为空字符串。"),
            "entities": _array(evidence_entity_schema(), "解决当前问题所必需的人物、称号、简称、亲属表达等，最多抽取必要内容。"),
            "assertions": _array(evidence_assertion_schema(), "原文明确支持的实体关系；每一条都必须有连续原文证据。"),
            "summary": _string("供人工审核阅读的简短史料理解摘要；Python 不使用此字段控制状态。"),
        },
        "这部分记录模型从给定史料原文中直接理解出的结构化语义。它描述‘史料说了什么’，不是数据库最终事实，也不能创建 Person ID。",
    )


def semantic_assessment_schema() -> dict[str, Any]:
    return _object(
        {
            "assessment_status": _enum(schema.ASSESSMENT_STATUSES, "对当前目标表达与候选的语义评估状态。", ASSESSMENT_STATUS_LABELS),
            "semantic_fit": _enum(schema.SEMANTIC_FITS, "从文本语义角度评价目标表达与候选是否相符；不得覆盖 Python hard constraints。", SEMANTIC_FIT_LABELS),
            "observed_role": _enum(schema.DISCOURSE_ROLES, "目标人物在当前 passage 中承担的叙事或引文角色。", DISCOURSE_ROLE_LABELS),
            "evidence_spans": _array(evidence_span_schema(), "直接支持 assessment 的原文片段；不是自由解释。"),
            "summary": _string("供人工审核的简短语义说明；Python 不依赖它做状态决策。"),
        },
        "模型对当前目标表达和候选人物之间语义匹配程度的判断。Python hard constraints 已经给定，模型不得修改它们。",
    )


def new_entity_candidate_schema() -> dict[str, Any]:
    return _object(
        {
            "surface": _string("新人物候选在原文中的文字层表面；若 recommendation 不是 new_person_candidate，填写空字符串。"),
        },
        "仅记录新人物候选的文本层描述，不生成数据库 ID。",
    )


def identity_recommendation_schema() -> dict[str, Any]:
    return _object(
        {
            "decision": _enum(schema.RECOMMENDATION_DECISIONS, "模型根据文本语义给出的身份建议；不是最终 IdentityDecision。", RECOMMENDATION_LABELS),
            "chosen_candidate_key": _nullable_wire_string("只有 choose_candidate 时填写 Python 提供的 c0/c1/...；禁止自行生成，其他情况为空字符串。"),
            "confidence": _enum(schema.CONFIDENCE_LEVELS, "模型对 recommendation 的信心。", CONFIDENCE_LABELS),
            "reason_codes": _array(_string("简短、可机器审核的理由标签，不写长篇推理。"), "支持 recommendation 的短理由标签。"),
            "evidence_spans": _array(evidence_span_schema(), "直接支持 recommendation 的连续原文。"),
            "new_entity_candidate": new_entity_candidate_schema(),
            "new_entity_key": _nullable_wire_string("只有 new_person_candidate 时使用 n0；不能创建 Person ID，其他情况为空字符串。"),
            "unresolved_reason": _string("若 unresolved 或 ambiguous，简要说明当前缺少哪种证据；否则填写空字符串。"),
            "summary": _string("供人工审核的简短建议说明；Python 不依赖它做状态决策。"),
        },
        "模型根据文本语义给出的身份建议。这是 recommendation，不是最终 IdentityDecision；最终决定由 Python 完成。",
    )


def research_gap_schema() -> dict[str, Any]:
    return _object(
        {
            "status": _enum(schema.RESEARCH_GAP_STATUSES, "当前身份研究是否达到停止条件。", {"open": "当前证据不足", "closed": "当前问题已达到停止条件"}),
            "missing_constraints": _array(_string("仍缺少的证据类型，如 title_identity、identity_evidence、kinship、temporal。"), "当前仍缺少的约束或证据类型。"),
            "blocking_question": _string("阻止问题关闭的唯一核心问题，应具体、简短。"),
            "next_best_action": _enum(schema.RESEARCH_ACTIONS, "当前材料不足时的下一步动作；只使用系统已有动作。", {
                "search_kinship_context": "检索亲属上下文",
                "search_title_identity": "检索称号身份",
                "search_temporal_evidence": "检索时间证据",
                "search_biography_context": "检索传记上下文",
                "human_review": "人工审核",
                "none": "不再行动",
            }),
            "candidate_keys": _array(_string("当前 ResearchGap 涉及的已有 candidate key，只能复制 Python 提供的 key。"), "与 gap 直接相关的已有候选。"),
            "stop_condition": _string("可验证的停止条件，而非泛泛研究建议。"),
        },
        "说明当前身份研究是否已经足够，以及如果不足下一步缺什么；服务于 Python 检索控制，不是自由文本研究建议。",
    )


def card_parameters_schema() -> dict[str, Any]:
    return _object(
        {
            "evidence_interpretation": evidence_interpretation_schema(),
            "semantic_assessment": semantic_assessment_schema(),
            "identity_recommendation": identity_recommendation_schema(),
            "research_gap": research_gap_schema(),
        },
        "Historical Entity Schema V1 的严格结构化 EvidenceCard。所有语义必须来自系统提供的 source passages。",
    )


def strict_function_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "提交当前 ResearchGap 所需的结构化历史实体 EvidenceCard；只记录原文可验证语义，不创建数据库身份或图谱 ID。",
            "strict": True,
            "parameters": card_parameters_schema(),
        },
    }


def strict_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": FUNCTION_NAME}}


def wire_to_controller_payload(payload: Any) -> Any:
    """Convert strict wire sentinels to the existing nullable card shape."""

    if not isinstance(payload, Mapping):
        return payload
    result = json.loads(json.dumps(payload, ensure_ascii=False))
    card = result.get("evidence_interpretation")
    if isinstance(card, dict) and card.get("target_entity_key") == "":
        card["target_entity_key"] = None
    if isinstance(card, dict):
        for row in card.get("assertions", []) if isinstance(card.get("assertions"), list) else []:
            if not isinstance(row, dict):
                continue
            for key in ("object_entity_key", "value", "direction"):
                if row.get(key) == "":
                    row[key] = None
    recommendation = result.get("identity_recommendation")
    if isinstance(recommendation, dict):
        for key in ("chosen_candidate_key", "new_entity_key"):
            if recommendation.get(key) == "":
                recommendation[key] = None
        new_candidate = recommendation.get("new_entity_candidate")
        if isinstance(new_candidate, dict) and not str(new_candidate.get("surface") or "").strip():
            recommendation["new_entity_candidate"] = None
    return result


def controller_payload_to_wire(payload: Any) -> Any:
    """Encode an existing controller fixture using the strict wire sentinels."""

    if not isinstance(payload, Mapping):
        return payload
    result = json.loads(json.dumps(payload, ensure_ascii=False))
    card = result.get("evidence_interpretation")
    if isinstance(card, dict) and card.get("target_entity_key") is None:
        card["target_entity_key"] = ""
    if isinstance(card, dict):
        for row in card.get("assertions", []) if isinstance(card.get("assertions"), list) else []:
            if not isinstance(row, dict):
                continue
            for key in ("object_entity_key", "value", "direction"):
                if row.get(key) is None:
                    row[key] = ""
    recommendation = result.get("identity_recommendation")
    if isinstance(recommendation, dict):
        for key in ("chosen_candidate_key", "new_entity_key"):
            if recommendation.get(key) is None:
                recommendation[key] = ""
        if recommendation.get("new_entity_candidate") is None:
            recommendation["new_entity_candidate"] = {"surface": ""}
    return result


def schema_hash() -> str:
    raw = json.dumps(card_parameters_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "FUNCTION_NAME", "STRICT_ENDPOINT", "STRICT_COMPLETIONS_ENDPOINT", "card_parameters_schema", "strict_function_definition",
    "strict_tool_choice", "wire_to_controller_payload", "controller_payload_to_wire", "schema_hash",
]
