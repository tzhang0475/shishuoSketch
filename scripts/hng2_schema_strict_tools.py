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

# The current semantic extraction pass deliberately has a smaller wire
# contract than the original controller card.  Keep this list local to the
# wire contract: the broader Schema V1 assertion vocabulary is still used by
# older replay artifacts and by Python-side projections.
SMALL_ASSERTION_TYPES = {
    "identity_equivalence",
    "alias_of",
    "courtesy_name_of",
    "title_of",
    "parent_child",
    "sibling",
    "kinship_relation",
    "person_mention",
}

SMALL_ASSERTION_TYPE_LABELS = {
    "identity_equivalence": "原文明确表明两个实体表达指同一人物；主体和客体是两个局部表达",
    "alias_of": "原文明确表明主体是客体的别名或异称；两者指同一人物",
    "courtesy_name_of": "原文明确表明主体是客体的字或字号；主体是字号表达，客体是人物表达",
    "title_of": "原文明确表明主体的帝王、爵号、尊号等称号属于客体人物；主体是称号，客体是人物",
    "parent_child": "原文明确表明主体与客体存在父母—子女关系；方向按原文关系填写",
    "sibling": "原文明确表明主体与客体是兄弟姊妹；两者都是人物实体",
    "kinship_relation": "原文明确表明其他亲属关系，但不能精确归入父子或兄弟；主体和客体是亲属链中的实体",
    "person_mention": "原文明确提及主体人物，但没有足够文字支持更具体的实体关系；不凭共现添加关系",
}

UNRESOLVED_OBSERVATION_FIELDS = {"source_ref", "exact_span", "observation", "search_terms"}


def unresolved_observation_schema() -> dict[str, Any]:
    return _object(
        {
            "source_ref": _string("系统提供的 source passage ref；必须逐字复制，不能自行生成。"),
            "exact_span": _string("史料中尚不能安全压缩为当前小断言的连续原文；必须原样存在于 source_ref 对应文本中。"),
            "observation": _string("对当前 target 有关、但当前断言词汇尚不能表达的文字层观察；不是历史事实、身份决定或关系。"),
            "search_terms": _array(_string("只用于一次本地 FIND 的检索提示；不得写外部网址、Person ID 或未经原文支持的历史结论。"), "最多三个简短检索词。"),
        },
        "记录模型在给定原文中看见、但暂时无法用小型 assertion vocabulary 安全表达的直接观察。它不创建任何人物、关系、事实或图谱对象。",
    )


def small_card_with_observations_parameters_schema() -> dict[str, Any]:
    properties = dict(small_card_parameters_schema()["properties"])
    properties["unresolved_observations"] = _array(
        unresolved_observation_schema(),
        "当前 target 的未解决文字观察；最多两个，每条只保留直接锚定原文且可继续本地检索的缺口。",
    )
    return _object(
        properties,
        "SC2 Round 1 的扩展小型 Historical Evidence Card。基础实体和断言字段与 SC1 相同；unresolved_observations 只是检索提示，不是历史事实或 Python 状态。",
    )


def small_card_with_observations_function_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "提交当前目标的最小 Evidence Card，并记录最多两个直接锚定原文、尚不能由小断言表达的观察；不作数据库决定。",
            "strict": True,
            "parameters": small_card_with_observations_parameters_schema(),
        },
    }


ROUND2_FUNCTION_NAME = "submit_historical_evidence_resolution"
ROUND2_FACT_KINDS = {
    "identity", "kinship", "office", "title", "relation", "interaction", "temporal", "event", "other",
}
ROUND2_STATUS = {"resolved", "partially_resolved", "unresolved"}


def round2_resolution_parameters_schema() -> dict[str, Any]:
    finding = _object(
        {
            "subject_surface": _string("新证据中直接出现、与当前 target 或待核查观察相关的主体文字；不填写 Person ID。"),
            "predicate": _string("用简短文字描述 source passage 直接表达的谓词；不得把未写出的历史推论当作谓词。"),
            "object_surface": _string("新证据中直接出现的客体文字；无明确客体时填写空字符串。"),
            "fact_kind": _enum(ROUND2_FACT_KINDS, "该 finding 的文字证据类别；other 用于当前受限词汇无法精确归类但原文明确支持的最小发现。", {
                "identity": "身份或同一表达",
                "kinship": "亲属关系",
                "office": "官职任用或职任",
                "title": "帝王、爵号、尊号等称号",
                "relation": "明确关系",
                "interaction": "明确互动或事件中的行动",
                "temporal": "时间、年代或先后",
                "event": "事件参与或事件事实",
                "other": "其他直接文字发现",
            }),
            "source_ref": _string("直接支持 finding 的输入 source passage ref；必须逐字复制。"),
            "exact_span": _string("直接支持 finding 的最短连续原文；必须原样存在于 source_ref 对应文本中。"),
            "confidence": _enum(schema.CONFIDENCE_LEVELS, "模型对 supplied text 是否直接支持该 finding 的信心，不是数据库事实真实性。", CONFIDENCE_LABELS),
        },
        "一个只由新输入原文直接支持的最小发现；Python 会逐条验证 source_ref 和 exact_span。",
    )
    return _object(
        {
            "status": _enum(ROUND2_STATUS, "对当前观察的证据核查结果。resolved 表示新证据足以支持 findings，partially_resolved 表示只支持部分，unresolved 表示仍不能支持。", {
                "resolved": "新证据足以支持一个或多个最小 finding",
                "partially_resolved": "新证据只支持部分问题",
                "unresolved": "新证据仍不能直接支持可用 finding",
            }),
            "findings": _array(finding, "只填写新 source passages 直接支持的 findings；不要重复无关内容，不创建数据库 ID。"),
        },
        "SC2 Round 2 的小型证据核查卡。它只报告新输入原文直接支持的文字发现，不决定人物身份、关系、事实或图谱动作。",
    )


def round2_resolution_function_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": ROUND2_FUNCTION_NAME,
            "description": "核查一个 Round 1 文字观察，只提交新原文直接支持的最小 findings。",
            "strict": True,
            "parameters": round2_resolution_parameters_schema(),
        },
    }


def round2_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": ROUND2_FUNCTION_NAME}}


def small_evidence_entity_schema() -> dict[str, Any]:
    return _object(
        {
            "entity_key": _string("本次回答内部的局部实体编号，如 e0、e1；它不是 Person ID、candidate key 或 graph ID。"),
            "surface": _string("史料中实际出现、需要解释的最小文字形式；只填写当前目标或理解当前目标所必需的上下文实体。"),
            "entity_kind": _enum(schema.ENTITY_KINDS, "该表达在当前语境中的人物语义类别，不是数据库身份决定。", ENTITY_KIND_LABELS),
            "reference_form": _enum(schema.REFERENCE_FORMS, "该表达通过什么语言形式指向人物；这是语言形式，不是最终身份判断。", REFERENCE_FORM_LABELS),
            "evidence_refs": _array(_string("逐字复制系统提供的 source passage ref；不得自行生成或写入 Person ID。"), "包含该实体原文的输入 passage ref 列表。"),
        },
        "解决当前目标所必需的实体表达。实体字段只记录史料文字层观察，不作数据库身份决定。",
    )


def small_evidence_assertion_schema() -> dict[str, Any]:
    return _object(
        {
            "assertion_id": _string("本次回答内部的局部断言编号，如 a0、a1；它不是 relation ID 或 graph ID。"),
            "assertion_type": _enum(SMALL_ASSERTION_TYPES, "原文直接支持的最小实体断言。", SMALL_ASSERTION_TYPE_LABELS),
            "subject_entity_key": _string("断言主体，必须引用 entities 中已声明的 eN。其语义取决于 assertion_type 的 subject 定义。"),
            "object_entity_key": _nullable_wire_string("涉及第二实体时填写 entities 中已有的 eN；没有第二实体时填写空字符串。"),
            "evidence_refs": _array(_string("逐字复制系统提供的 source passage ref；每个 ref 必须直接支持本断言。"), "直接支持本断言的输入 passage ref 列表；不复制长引文。"),
            "confidence": _enum(schema.CONFIDENCE_LEVELS, "模型对原文是否明确表达该断言的信心，不是数据库最终事实真实性。", CONFIDENCE_LABELS),
        },
        "只记录由输入原文直接支持的最小断言。evidence_refs 是出处指针；Python 负责验证、匹配和生成约束。",
    )


def small_card_parameters_schema() -> dict[str, Any]:
    return _object(
        {
            "target_entity_key": _string("当前 ResearchGap 的目标表达对应的 EvidenceEntity 局部编号，通常为 e0；必须指向 entities 中已声明的目标实体。"),
            "entities": _array(small_evidence_entity_schema(), "只抽取解决当前目标所必需的人物、称号、简称或亲属表达；合并同一局部实体的重复指称。"),
            "assertions": _array(small_evidence_assertion_schema(), "只填写输入史料明确支持的最小实体断言；共现本身不是关系。"),
            "note": _string("供人工审核的简短阅读备注。它不是结构化证据，Python 绝不使用它控制候选、约束、IdentityDecision 或 ResearchGap。"),
        },
        "这是小型 Historical Evidence Card。它记录模型从给定史料中直接读出的最小文字证据，而不是数据库事实、身份决定或图谱动作。模型不创建任何数据库 ID。",
    )


def small_card_function_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "提交当前目标所需的最小 Historical Evidence Card；只记录输入原文直接支持的实体与断言，不作数据库决定。",
            "strict": True,
            "parameters": small_card_parameters_schema(),
        },
    }


def small_card_schema_hash() -> str:
    raw = json.dumps(small_card_parameters_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def small_card_with_observations_schema_hash() -> str:
    raw = json.dumps(small_card_with_observations_parameters_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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


def legacy_strict_function_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "提交当前 ResearchGap 所需的结构化历史实体 EvidenceCard；只记录原文可验证语义，不创建数据库身份或图谱 ID。",
            "strict": True,
            "parameters": card_parameters_schema(),
        },
    }


def strict_function_definition() -> dict[str, Any]:
    """Return the current small semantic card function.

    The previous large card remains available explicitly as
    ``legacy_strict_function_definition`` for immutable replay compatibility.
    """

    return small_card_function_definition()


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


def small_card_to_controller_card(payload: Any) -> Any:
    """Convert the small strict wire card to the controller's legacy card shape.

    This is a transport adapter only.  It does not add a recommendation,
    ResearchGap, candidate key, or evidence span.  The small-card controller
    projection creates those Python-owned values after validation.
    """

    if not isinstance(payload, Mapping):
        return payload
    card = {
        "target_entity_key": str(payload.get("target_entity_key") or "") or None,
        "entities": [],
        "assertions": [],
        "summary": str(payload.get("note") or ""),
    }
    for row in payload.get("entities", []) if isinstance(payload.get("entities"), list) else []:
        if not isinstance(row, Mapping):
            continue
        refs = [str(ref).strip() for ref in row.get("evidence_refs", []) if str(ref).strip()] if isinstance(row.get("evidence_refs"), list) else []
        card["entities"].append({
            "entity_key": str(row.get("entity_key") or ""),
            "surface": str(row.get("surface") or ""),
            "entity_kind": str(row.get("entity_kind") or ""),
            "reference_form": str(row.get("reference_form") or ""),
            "evidence_ref": refs[0] if refs else "",
            "evidence_refs": refs,
            "evidence_span": "",
        })
    for row in payload.get("assertions", []) if isinstance(payload.get("assertions"), list) else []:
        if not isinstance(row, Mapping):
            continue
        refs = [str(ref).strip() for ref in row.get("evidence_refs", []) if str(ref).strip()] if isinstance(row.get("evidence_refs"), list) else []
        object_key = str(row.get("object_entity_key") or "") or None
        card["assertions"].append({
            "assertion_id": str(row.get("assertion_id") or ""),
            "assertion_type": str(row.get("assertion_type") or ""),
            "subject_entity_key": str(row.get("subject_entity_key") or ""),
            "object_entity_key": object_key,
            "value": None,
            "direction": None,
            "evidence_ref": refs[0] if refs else "",
            "evidence_refs": refs,
            "evidence_span": "",
            "confidence": str(row.get("confidence") or ""),
        })
    return card


def schema_hash() -> str:
    raw = json.dumps(card_parameters_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "FUNCTION_NAME", "ROUND2_FUNCTION_NAME", "STRICT_ENDPOINT", "STRICT_COMPLETIONS_ENDPOINT", "card_parameters_schema", "legacy_strict_function_definition", "strict_function_definition",
    "strict_tool_choice", "wire_to_controller_payload", "controller_payload_to_wire", "small_evidence_entity_schema",
    "small_evidence_assertion_schema", "small_card_parameters_schema", "small_card_function_definition",
    "unresolved_observation_schema", "small_card_with_observations_parameters_schema", "small_card_with_observations_function_definition",
    "small_card_schema_hash", "small_card_with_observations_schema_hash", "small_card_to_controller_card", "SMALL_ASSERTION_TYPES", "ROUND2_FACT_KINDS", "ROUND2_STATUS", "round2_resolution_parameters_schema", "round2_resolution_function_definition", "round2_tool_choice", "schema_hash",
]
