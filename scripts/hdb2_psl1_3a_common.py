#!/usr/bin/env python3
"""HDB2-PSL1.3A semantic pre-judgment adapter.

PSL1.3A is intentionally a boundary layer around the frozen PSL1.1/PSL1.3
implementation.  The old reference parser remains available for historical
replay, but this module does not use a suffix-derived structure as a final
semantic decision.  It produces a small set of Python hypotheses first and
accepts a model arbitration only when the hypotheses are genuinely
ambiguous.  The resulting structure is then handed back to the unchanged
PSL scorer, reviewer, and rescue code.

No function in this module allocates a production Person ID or writes a
canonical fact.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import hdb2_psl1_1_common as psl1_1
import hdb2_psl1_3_common as psl1_3
import hdb2_psl1_common as psl1


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data/generated/hdb2-psl1-3a"
RUN_VERSION = "hdb2-psl1-3a-v1"
PROMPT_VERSION = "hdb2-psl1-3a-reference-semantic-arbitration-v1"
MODEL = psl1.MODEL
STRICT_ENDPOINT = psl1.STRICT_ENDPOINT
FUNCTION_NAME = "submit_hdb2_reference_semantic_structure"

SURFACE_STRUCTURES = {
    "lexicalized_personal_form",
    "compositional_kinship",
    "office_holder_reference",
    "patron_plus_office",
    "surname_plus_title",
    "ruler_reference",
    "honorific_person_reference",
    "non_person",
    "uncertain",
}
REFERENT_TYPES = {"person", "ruler", "non_person", "uncertain"}
COMPONENT_ROLES = {
    "personal_form",
    "anchor_person",
    "kinship_marker",
    "office",
    "patron",
    "surname",
    "title",
}
CONFIDENCES = {"high", "medium", "low"}
KINSHIP_MARKERS = ("兒", "子", "女", "兄", "弟", "父", "母", "妻", "婿")
OFFICE_SURFACES = (
    "驃騎將軍",
    "車騎將軍",
    "衛將軍",
    "大將軍",
    "尚書令",
    "主簿",
    "太傅",
    "太守",
    "長史",
    "尚書",
    "將軍",
    "司空",
    "僕射",
    "廷尉",
    "侍中",
    "中丞",
    "尹",
)
IDENTITY_MARKERS = ("字", "名", "諱", "號", "号")
ROLE_VETOES = {
    "RoleMismatch",
    "PossessorVsHolderMismatch",
    "ActorObjectMismatch",
    "ExplicitDistinct",
}


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


def _text(case: Mapping[str, Any]) -> str:
    pieces = [str(case.get("story_context") or "")]
    pieces.extend(str(value or "") for value in case.get("annotation_context", []) or [])
    for row in case.get("evidence_items", []) or []:
        if not isinstance(row, Mapping):
            continue
        family = str(row.get("family") or "")
        if family in {"candidate_profile", "confirmed_story_profile", "known_participants", "era_chronology"}:
            continue
        pieces.append(str(row.get("text") or ""))
    return "\n".join(piece for piece in pieces if piece)


def _source_evidence(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expose source-facing evidence only; candidate dossiers are excluded."""
    result: list[dict[str, Any]] = []
    for row in case.get("evidence_items", []) or []:
        if not isinstance(row, Mapping):
            continue
        family = str(row.get("family") or "")
        if family in {"candidate_profile", "confirmed_story_profile", "known_participants", "era_chronology"}:
            continue
        evidence_id = str(row.get("evidence_id") or "")
        text = str(row.get("text") or "")
        if evidence_id and text:
            result.append({
                "evidence_id": evidence_id,
                "family": family,
                "source_ref": row.get("source_ref"),
                "text": text,
            })
    return sorted(result, key=lambda row: str(row.get("evidence_id")))


def _evidence_ids(case: Mapping[str, Any], needles: Sequence[str] = ()) -> list[str]:
    wanted = [str(value) for value in needles if value]
    result = [
        str(row.get("evidence_id"))
        for row in _source_evidence(case)
        if not wanted or all(value in str(row.get("text") or "") for value in wanted)
    ]
    return sorted(set(result))[:8]


def _local_names(case: Mapping[str, Any]) -> list[str]:
    names: set[str] = set()
    for row in [*(case.get("local_neighbors", []) or []), *(case.get("candidates", []) or [])]:
        if not isinstance(row, Mapping):
            continue
        for value in (row.get("display_name"), row.get("name")):
            if value:
                names.add(str(value))
        profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
        for field in ("canonical_name", "aliases", "courtesy_names", "titles"):
            values = profile.get(field, []) if field != "canonical_name" else [profile.get(field)]
            names.update(str(value) for value in values or [] if value)
    return sorted(names, key=lambda value: (-len(value), value))


def _component(text: str, role: str) -> dict[str, str]:
    return {"text": str(text), "role": role}


def _hypothesis(
    hypothesis_id: str,
    structure: str,
    referent_type: str,
    components: Sequence[Mapping[str, str]],
    *,
    basis: str,
    evidence_ids: Sequence[str] = (),
    deterministic: bool = False,
) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis_id,
        "surface_structure": structure,
        "referent_type": referent_type,
        "components": [dict(row) for row in components],
        "basis": basis,
        "evidence_ids": sorted(set(str(value) for value in evidence_ids if value)),
        "deterministic": bool(deterministic),
    }


def _preceding_anchor(text: str, marker: str, names: Sequence[str]) -> str:
    positions = [match.start() for match in re.finditer(re.escape(marker), text)]
    for position in positions:
        prefix = text[:position]
        for name in names:
            if prefix.endswith(name):
                return name
        nearby = [
            (prefix.rfind(name) + len(name), len(name), name)
            for name in names
            if prefix.rfind(name) >= max(0, len(prefix) - 80)
        ]
        if nearby:
            # Prefer the longest form when aliases end at the same location;
            # otherwise a one-character alias such as 敦 would hide 王敦.
            return max(nearby, key=lambda row: (row[0], row[1], row[2]))[2]
    return ""


def _office_hypotheses(case: Mapping[str, Any], target: str, text: str) -> list[dict[str, Any]]:
    office = next((value for value in OFFICE_SURFACES if target.endswith(value)), "")
    if not office:
        return []
    # X爲Y主簿 / X為Y主簿.  This is a complete local construction, so Python
    # can distinguish the holder from the patron without model arbitration.
    match = re.search(rf"(?P<holder>[\u3400-\u9fff]{{1,8}})[爲為]{re.escape(target)}", text)
    if match and len(target) > len(office):
        patron = target[:-len(office)]
        captured_holder = match.group("holder")
        holder = next(
            (name for name in _local_names(case) if captured_holder.endswith(name)),
            captured_holder,
        )
        return [_hypothesis(
            "h0",
            "patron_plus_office",
            "person",
            [_component(holder, "anchor_person"), _component(patron, "patron"), _component(office, "office")],
            basis="explicit_holder_patron_office_syntax",
            evidence_ids=_evidence_ids(case, (holder, patron, office)),
            deterministic=True,
        )]
    # X爲office, including forms such as 髙靈時為中丞.
    holder = _preceding_anchor(text, target, _local_names(case))
    if not holder:
        match = re.search(rf"(?P<holder>[\u3400-\u9fff]{{1,8}})[爲為]{re.escape(target)}", text)
        holder = match.group("holder") if match else ""
    if holder and target == office:
        return [_hypothesis(
            "h0",
            "office_holder_reference",
            "person",
            [_component(holder, "anchor_person"), _component(office, "office")],
            basis="explicit_holder_office_syntax",
            evidence_ids=_evidence_ids(case, (holder, office)),
            deterministic=True,
        )]
    if target == office or (
        len(target) == len(office)
        and str(case.get("occurrence_type") or "") in {"title_reference", "office_reference"}
    ):
        return [_hypothesis(
            "h0",
            "office_holder_reference",
            "person",
            [_component(office, "office")],
            basis="whole_office_surface",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        )]
    return []


def _kinship_hypothesis(case: Mapping[str, Any], target: str, text: str) -> dict[str, Any] | None:
    if target == "家兄":
        anchor = _preceding_anchor(text, "家兄", _local_names(case))
        # The common form is 王敦護其兄...家兄.  Retain an empty anchor if
        # the local packet does not prove one; the expression is still
        # compositional and cannot become its base person.
        return _hypothesis(
            "h0",
            "compositional_kinship",
            "person",
            ([_component(anchor, "anchor_person")] if anchor else []) + [_component("家兄", "kinship_marker")],
            basis="lexicalized_household_kinship_expression",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        )
    # The explicit ``X之子/兄/弟/女`` constructions carry their own anchor.
    # Parse the full construction rather than treating ``之`` as part of the
    # person's name.  This is a deterministic local syntax rule, not a
    # suffix-only guess.
    for marker in ("子", "兄", "弟", "女", "父", "母"):
        explicit_marker = f"之{marker}"
        if target.endswith(explicit_marker) and len(target) > len(explicit_marker):
            base = target[: -len(explicit_marker)]
            return _hypothesis(
                "explicit-kinship",
                "compositional_kinship",
                "person",
                [_component(base, "anchor_person"), _component(explicit_marker, "kinship_marker")],
                basis="explicit_compositional_kinship_syntax",
                evidence_ids=_evidence_ids(case, (target,)),
                deterministic=True,
            )
    marker = next((value for value in KINSHIP_MARKERS if target.endswith(value) and len(target) > len(value)), "")
    if not marker:
        return None
    base = target[:-len(marker)]
    # A full anchor is deterministic.  A bare suffix such as 武子 is not:
    # it may be a courtesy/personal form and is therefore only a hypothesis.
    # A one-character base is too common to count as a grounded anchor (武 in
    # 武帝 is not evidence that 武子 is a kinship construction).  It remains
    # a hypothesis and can be arbitrated against a whole-form reading.
    # Do not count the base merely because it is a substring of the target
    # occurrence (``庾亮`` inside ``庾亮兒``).  It must be separately present
    # in the local packet or supplied as a local name.  Otherwise the suffix
    # remains only a hypothesis for semantic arbitration.
    target_ranges = [
        (match.start(), match.end())
        for match in re.finditer(re.escape(target), text)
    ]
    base_is_separate = any(
        not any(start <= match.start() and match.end() <= end for start, end in target_ranges)
        for match in re.finditer(re.escape(base), text)
    )
    grounded_anchor = len(base) >= 2 and (base_is_separate or base in _local_names(case))
    return _hypothesis(
        "kinship",
        "compositional_kinship",
        "person",
        [_component(base, "anchor_person"), _component(marker, "kinship_marker")],
        basis="grounded_compositional_base" if grounded_anchor else "suffix_only_hypothesis",
        evidence_ids=_evidence_ids(case, (target,)),
        deterministic=grounded_anchor,
    )


def _whole_form_hypothesis(case: Mapping[str, Any], target: str, text: str) -> dict[str, Any] | None:
    # An office surface is parsed as office syntax below.  A profile title
    # equal to 主簿/尹/etc. is not a whole-person alias and must not create a
    # lexical-vs-office ambiguity.
    if any(target.endswith(office) for office in OFFICE_SURFACES):
        return None
    forms: set[str] = set()
    for row in case.get("candidates", []) or []:
        if not isinstance(row, Mapping):
            continue
        profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
        values = [row.get("display_name"), profile.get("canonical_name")]
        for field in ("aliases", "courtesy_names"):
            values.extend(profile.get(field, []) or [])
        forms.update(str(value) for value in values if value)
    if target in forms:
        return _hypothesis(
            "lexical",
            "lexicalized_personal_form",
            "person",
            [_component(target, "personal_form")],
            basis="exact_supplied_alias_or_courtesy_form",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        )
    # A short ``...子`` target may be a whole personal form when it is visibly
    # used as part of a named expression (王武子).  Restrict this fallback to
    # short 子-forms: applying it to 庾亮兒 or 家兄 would mistake a preceding
    # office/grammar character for a surname.
    if target == "家兄" or not target.endswith("子") or len(target) > 2:
        return None
    for match in re.finditer(rf"([\u3400-\u9fff]){re.escape(target)}", text):
        full = match.group(0)
        if full == target:
            continue
        return _hypothesis(
            "lexical",
            "lexicalized_personal_form",
            "person",
            [_component(full, "personal_form")],
            basis="visible_whole_personal_form_context",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=False,
        )
    return None


def _explicit_identity_hypothesis(case: Mapping[str, Any], target: str, text: str) -> dict[str, Any] | None:
    """Recognize a source-grounded name/courtesy statement as lexical form.

    This is a structure-only shortcut.  It does not resolve the form to a
    Person; it merely avoids asking the semantic arbiter to decide whether a
    plainly stated ``X字Y``/``X名Y`` construction is compositional kinship.
    """
    # A one-character surface is too frequent for a bounded cross-text
    # identity regex to be safe (``主`` can occur in an unrelated sentence).
    # Such forms remain available to the normal hypothesis/LLM boundary.
    if len(target) < 2:
        return None
    marker_pattern = "字名諱號号"
    escaped_target = re.escape(target)
    patterns = (
        rf"(?P<person>[\u3400-\u9fff]{{2,8}})[，,、\s]*[{marker_pattern}][：:，,、\s]*{escaped_target}",
        rf"{escaped_target}[，,、\s]*[{marker_pattern}][：:，,、\s]*(?P<person>[\u3400-\u9fff]{{2,8}})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        person = str(match.group("person") or "")
        if not person or person == target:
            continue
        return _hypothesis(
            "explicit-identity",
            "lexicalized_personal_form",
            "person",
            [_component(person, "personal_form"), _component(target, "personal_form")],
            basis="explicit_grounded_name_or_courtesy_statement",
            evidence_ids=_evidence_ids(case, (person, target)),
            deterministic=True,
        )
    return None


def build_reference_hypotheses(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return possible structures without treating any suffix as decisive."""
    target = str(case.get("target_surface") or "")
    text = _text(case)
    hypotheses: list[dict[str, Any]] = []

    # Complete syntax has priority over generic lexical hypotheses.
    hypotheses.extend(_office_hypotheses(case, target, text))
    if target == "主":
        marriage = re.search(r"(?P<actor>[\u3400-\u9fff]{1,8})(?:初)?尚主", text)
        if marriage:
            actor = marriage.group("actor")
            if actor.endswith("初"):
                actor = actor[:-1]
            hypotheses.append(_hypothesis(
                "h0",
                "non_person",
                "non_person",
                [_component(actor, "anchor_person"), _component("主", "title")],
                basis="explicit_marriage_object_syntax",
                evidence_ids=_evidence_ids(case, (actor, "尚主")),
                deterministic=True,
            ))
    if target in {"帝", "明帝", "武帝", "文帝", "元帝", "康帝", "晉武帝"}:
        hypotheses.append(_hypothesis(
            "h0",
            "ruler_reference",
            "ruler",
            [_component(target, "title")],
            basis="known_ruler_title_surface",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        ))
    elif target == "陛下":
        hypotheses.append(_hypothesis(
            "h0",
            "honorific_person_reference",
            "ruler",
            [_component(target, "title")],
            basis="honorific_ruler_reference",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        ))
    identity = _explicit_identity_hypothesis(case, target, text)
    if identity:
        hypotheses.append(identity)
    if (
        str(case.get("occurrence_type") or "") == "title_reference"
        and len(target) >= 2
        and not any(row.get("surface_structure") in {"office_holder_reference", "patron_plus_office"} for row in hypotheses)
    ):
        # Keep a title-shaped expression distinct from a name merely because
        # it shares a surname character.  This is a semantic hypothesis, not
        # a candidate identity.
        hypotheses.append(_hypothesis(
            "title",
            "surname_plus_title",
            "person",
            [_component(target[:1], "surname"), _component(target[1:], "title")],
            basis="title_surface_requires_holder_resolution",
            evidence_ids=_evidence_ids(case, (target,)),
            deterministic=True,
        ))
    if target == "家兄" or not hypotheses:
        kinship = _kinship_hypothesis(case, target, text)
        if kinship:
            hypotheses.append(kinship)
    elif target.endswith(KINSHIP_MARKERS):
        # A suffix-based possibility is still included alongside office/title
        # or lexical possibilities, but is never selected automatically.
        kinship = _kinship_hypothesis(case, target, text)
        if kinship:
            hypotheses.append(kinship)
    lexical = _whole_form_hypothesis(case, target, text)
    if lexical:
        hypotheses.append(lexical)
    if not hypotheses:
        hypotheses.append(_hypothesis(
            "uncertain",
            "uncertain",
            "uncertain",
            [],
            basis="no_reliable_local_structure",
        ))

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in hypotheses:
        key = (
            row.get("surface_structure"),
            row.get("referent_type"),
            tuple((component.get("text"), component.get("role")) for component in row.get("components", [])),
        )
        # The first occurrence preserves explicit deterministic priority.
        unique.setdefault(key, row)
    return list(unique.values())


def reference_hypotheses(case: Mapping[str, Any]) -> dict[str, Any]:
    hypotheses = build_reference_hypotheses(case)
    deterministic = [row for row in hypotheses if row.get("deterministic")]
    # Multiple deterministic hypotheses are still an ambiguity if they do not
    # describe the same surface structure.
    # Any more than one distinct hypothesis is an ambiguity, even if two
    # hypotheses happen to share the same broad structure.  Python must not
    # silently finalize one of them on the basis of a suffix or ordering.
    ambiguous = len(hypotheses) != 1 or len(deterministic) != 1
    return {
        "hypotheses": hypotheses,
        "ambiguous": ambiguous,
        "deterministic": len(deterministic) == 1 and not ambiguous,
        "deterministic_hypothesis": deterministic[0] if len(deterministic) == 1 and not ambiguous else None,
    }


def _known_alias_forms(case: Mapping[str, Any], target: str) -> list[str]:
    forms: set[str] = set()
    for row in case.get("candidates", []) or []:
        if not isinstance(row, Mapping):
            continue
        profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
        values = [row.get("display_name"), profile.get("canonical_name")]
        values.extend(profile.get("aliases", []) or [])
        values.extend(profile.get("courtesy_names", []) or [])
        forms.update(str(value) for value in values if value and str(value) == target)
    return sorted(forms)


def semantic_packet(case: Mapping[str, Any], hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build candidate-neutral input for the structure arbitration call."""
    target = str(case.get("target_surface") or "")
    source = _source_evidence(case)
    packet = {
        "task": "semantic arbitration of one historical reference surface",
        "mention": {
            "mention_id": case.get("mention_id"),
            "story_id": case.get("story_id"),
            "surface": target,
        },
        "target": {
            "surface": target,
            "story_id": case.get("story_id"),
            "occurrence_type": case.get("occurrence_type"),
        },
        "story_context": str(case.get("story_context") or ""),
        "annotation_context": [str(value) for value in case.get("annotation_context", []) or [] if value],
        "evidence_items": source,
        "known_alias_or_courtesy_forms": _known_alias_forms(case, target),
        "reference_hypotheses": [
            {
                "hypothesis_id": row.get("hypothesis_id"),
                "surface_structure": row.get("surface_structure"),
                "referent_type": row.get("referent_type"),
                "components": list(row.get("components", []) or []),
                "basis": row.get("basis"),
            }
            for row in hypotheses
        ],
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return psl1_3._provider_safe(packet)


def _object(properties: Mapping[str, Mapping[str, Any]], description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": {key: dict(value) for key, value in properties.items()},
        "required": list(properties),
        "additionalProperties": False,
    }


def semantic_tool() -> dict[str, Any]:
    component = _object({
        "text": {
            "type": "string",
            "description": "复制 supplied source/context 中实际出现的文字；不得改写、翻译或补造历史表面。",
        },
        "role": {
            "type": "string",
            "enum": sorted(COMPONENT_ROLES),
            "description": "该文字在当前指称结构中的局部角色，不是人物身份结论。",
        },
    }, "当前历史表达的文字组成部分。")
    properties = {
        "surface_structure": {
            "type": "string",
            "enum": sorted(SURFACE_STRUCTURES),
            "description": "当前 surface 的语义结构。后缀本身不能证明 compositional_kinship；需依据 supplied context 选择 lexicalized personal form、office/patron 结构、ruler/honorific 或其他结构。",
        },
        "referent_type": {
            "type": "string",
            "enum": sorted(REFERENT_TYPES),
            "description": "表达实际可能指向的人物、君主、非人物或不确定对象；office/title 仍可以 refer to person/ruler。",
        },
        "components": {
            "type": "array",
            "maxItems": 8,
            "items": component,
            "description": "只列出 supplied text 中能逐字核验的组成部分；不要把 anchor/patron 自动当成最终 referent。",
        },
        "supporting_evidence_ids": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "支持结构判断的 supplied evidence_id；不能发明 ID。",
        },
        "confidence": {
            "type": "string",
            "enum": sorted(CONFIDENCES),
            "description": "对 surface structure 判断的信心，不是人物身份概率；low 必须保留 unresolved/review。",
        },
    }
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "只仲裁一个历史表达的指称结构，不作人物解析、数据库决定或 canonical 写入。",
            "strict": True,
            "parameters": _object(properties, "candidate-neutral 的历史指称结构仲裁结果。"),
        },
    }


def semantic_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": FUNCTION_NAME}}


SEMANTIC_SYSTEM_PROMPT = (
    "只阅读 supplied 的历史原文、注释和 Python 提出的 hypotheses，判断当前 target surface 的语义结构。"
    "hypotheses 只是待检验的可能性，不是事实；尤其不要因为末字是子、兒、兄等就自动判为亲属。"
    "保留原文文字，components 只能复制 supplied context 中可见的表面。office/title/ruler/honorific 可以指向人物或君主；"
    "只在原文结构支持时选择 compositional、patron-plus-office 或 non-person。不要选择 Person，不要输出 ID，不要使用外部知识。"
    "如果无法排除歧义，返回 uncertain 或 low confidence。"
)


def _payload_keys(payload: Any) -> list[str]:
    return [str(key) for key in payload] if isinstance(payload, Mapping) else []


def _walk_forbidden(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    forbidden = {"person_id", "candidate_key", "candidate_id", "ruler_id", "production_id", "canonical_id"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            if str(key) in forbidden:
                found.append(current)
            found.extend(_walk_forbidden(child, current))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_forbidden(child, f"{path}[{index}]"))
    return found


def validate_semantic_arbitration(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors = [f"forbidden_id_field:{path}" for path in _walk_forbidden(payload)]
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": sorted(set(["payload_not_object", *errors]))}
    expected = {"surface_structure", "referent_type", "components", "supporting_evidence_ids", "confidence"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(_payload_keys(payload)) - expected))
    structure = payload.get("surface_structure")
    referent = payload.get("referent_type")
    confidence = payload.get("confidence")
    if not isinstance(structure, str) or structure not in SURFACE_STRUCTURES:
        errors.append("surface_structure_invalid")
    if not isinstance(referent, str) or referent not in REFERENT_TYPES:
        errors.append("referent_type_invalid")
    if not isinstance(confidence, str) or confidence not in CONFIDENCES:
        errors.append("confidence_invalid")
    evidence_rows = packet.get("evidence_items", []) if isinstance(packet, Mapping) else []
    evidence_ids = {str(row.get("evidence_id")) for row in evidence_rows if isinstance(row, Mapping) and row.get("evidence_id")}
    evidence_values = "\n".join(str(row.get("text") or "") for row in evidence_rows if isinstance(row, Mapping))
    supplied_context = "\n".join([
        str((packet.get("target") or {}).get("surface") or ""),
        str(packet.get("story_context") or ""),
        *(str(value or "") for value in packet.get("annotation_context", []) or []),
        evidence_values,
    ])
    ids = payload.get("supporting_evidence_ids")
    if not isinstance(ids, list) or not all(isinstance(value, str) and value for value in ids):
        errors.append("supporting_evidence_ids_invalid")
        ids = []
    elif len(ids) > 8:
        errors.append("supporting_evidence_ids_too_many")
    for evidence_id in ids:
        if evidence_id not in evidence_ids:
            errors.append(f"evidence_reference_invalid:{evidence_id}")
    if structure != "uncertain" and confidence in ("high", "medium") and not ids:
        errors.append("semantic_structure_requires_evidence")
    components = payload.get("components")
    if not isinstance(components, list):
        errors.append("components_invalid")
        components = []
    elif len(components) > 8:
        errors.append("components_too_many")
    for index, component in enumerate(components):
        if not isinstance(component, Mapping):
            errors.append(f"component_not_object:{index}")
            continue
        expected_component = {"text", "role"}
        errors.extend(
            f"unknown_component_field:{index}:{key}"
            for key in sorted(set(component) - expected_component)
        )
        text = component.get("text")
        role = component.get("role")
        if not isinstance(text, str):
            errors.append(f"component_text_invalid:{index}")
        elif text and text not in supplied_context:
            errors.append(f"component_text_not_grounded:{index}")
        if not isinstance(role, str) or role not in COMPONENT_ROLES:
            errors.append(f"component_role_invalid:{index}")
    # The model may only choose a structure proposed by Python.  This is a
    # semantic fail-closed boundary, not a scoring/tuning rule.
    proposed: set[tuple[str, str]] = set()
    for row in packet.get("reference_hypotheses", []) or []:
        if not isinstance(row, Mapping):
            continue
        proposed_structure = row.get("surface_structure")
        proposed_referent = row.get("referent_type")
        if isinstance(proposed_structure, str) and isinstance(proposed_referent, str):
            proposed.add((proposed_structure, proposed_referent))
    if (
        isinstance(structure, str)
        and isinstance(referent, str)
        and (structure, referent) not in proposed
        and structure != "uncertain"
    ):
        errors.append("surface_structure_not_in_hypotheses")
    if structure == "uncertain" and (
        not isinstance(referent, str)
        or referent not in {"uncertain", "person", "ruler", "non_person"}
    ):
        errors.append("uncertain_referent_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def _structure_reference_type(surface_structure: str, referent_type: str) -> str:
    if surface_structure == "compositional_kinship":
        return "kinship_compositional_reference"
    if surface_structure == "patron_plus_office" or surface_structure == "office_holder_reference":
        return "office_reference"
    if surface_structure == "ruler_reference":
        return "ruler_reference"
    if surface_structure == "honorific_person_reference":
        return "ruler_reference" if referent_type == "ruler" else "title_reference"
    if surface_structure == "surname_plus_title":
        return "title_reference"
    if surface_structure == "non_person":
        return "marriage_object_reference"
    if surface_structure == "lexicalized_personal_form":
        return "person_reference"
    return "unknown"


def _structure_fields(case: Mapping[str, Any], hypothesis: Mapping[str, Any], *, arbitration: Mapping[str, Any] | None = None) -> dict[str, Any]:
    target = str(case.get("target_surface") or "")
    structure = str(hypothesis.get("surface_structure") or "uncertain")
    components = [dict(row) for row in hypothesis.get("components", []) or []]
    fields = {
        "mention_id": case.get("mention_id"),
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "target_surface": target,
        "reference_head": target,
        "reference_type": _structure_reference_type(structure, str(hypothesis.get("referent_type") or "uncertain")),
        "holder": "",
        "anchor_person": "",
        "patron_or_possessor": "",
        "referent_candidate": None,
        "syntactic_role": "referent",
        "explicit_distinct_mentions": [],
        "evidence_ids": sorted(set(str(value) for value in hypothesis.get("evidence_ids", []) or [])),
        "derivation": "hdb2-psl1-3a-deterministic" if not arbitration else "hdb2-psl1-3a-semantic-arbitration",
        "surface_structure": structure,
        "referent_type": hypothesis.get("referent_type") or "uncertain",
        "components": components,
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "semantic_arbitration": dict(arbitration or {}),
        "semantic_arbitration_confidence": (arbitration or {}).get("confidence"),
        "finalized": structure != "uncertain",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    for component in components:
        text = str(component.get("text") or "")
        role = str(component.get("role") or "")
        if not text:
            continue
        if role == "anchor_person":
            fields["anchor_person"] = text
        elif role == "patron":
            fields["patron_or_possessor"] = text
        elif role == "office":
            fields["reference_head"] = text
        elif role == "kinship_marker":
            fields["syntactic_role"] = "kinship_referent"
        elif role == "title" and structure == "non_person":
            fields["syntactic_role"] = "marriage_object"
    if structure in {"office_holder_reference", "patron_plus_office"}:
        fields["holder"] = fields["anchor_person"]
    if structure == "patron_plus_office":
        fields["syntactic_role"] = "office_object_patron"
        fields["explicit_distinct_mentions"] = sorted(set(value for value in (fields["anchor_person"], fields["patron_or_possessor"]) if value))
    elif structure == "office_holder_reference":
        fields["syntactic_role"] = "office_holder"
    elif structure == "compositional_kinship":
        fields["syntactic_role"] = "kinship_referent"
        if fields["anchor_person"]:
            fields["explicit_distinct_mentions"] = [fields["anchor_person"], target]
    elif structure == "non_person":
        fields["explicit_distinct_mentions"] = sorted(set(value for value in (fields["anchor_person"], target) if value))
    # The model's evidence IDs are authoritative for semantic arbitration,
    # but only after packet validation.  They are still source IDs, never IDs
    # for people or database objects.
    if arbitration and isinstance(arbitration.get("supporting_evidence_ids"), list):
        fields["evidence_ids"] = sorted(set(str(value) for value in arbitration["supporting_evidence_ids"]))
    return fields


def _find_hypothesis(hypotheses: Sequence[Mapping[str, Any]], structure: str, referent_type: str) -> dict[str, Any] | None:
    for row in hypotheses:
        if row.get("surface_structure") == structure and row.get("referent_type") == referent_type:
            return dict(row)
    # A semantically equivalent person/ruler response can use the same
    # proposed structure with a more specific referent type.
    for row in hypotheses:
        if row.get("surface_structure") == structure and structure in {"lexicalized_personal_form", "office_holder_reference", "patron_plus_office"}:
            return dict(row)
    return None


def finalize_reference_structure(
    case: Mapping[str, Any],
    arbitration: Mapping[str, Any] | None = None,
    validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Finalize only a deterministic hypothesis or a validated arbitration."""
    info = reference_hypotheses(case)
    hypotheses = info["hypotheses"]
    chosen: dict[str, Any] | None = None
    if info["deterministic"]:
        chosen = dict(info["deterministic_hypothesis"])
    elif arbitration and (validation or {}).get("valid") is True:
        chosen = _find_hypothesis(
            hypotheses,
            str(arbitration.get("surface_structure") or "uncertain"),
            str(arbitration.get("referent_type") or "uncertain"),
        )
        if chosen and arbitration.get("confidence") in {"low", None}:
            chosen = None
        if chosen:
            chosen["components"] = [dict(row) for row in arbitration.get("components", []) or []]
            chosen["evidence_ids"] = list(arbitration.get("supporting_evidence_ids", []) or [])
            chosen["referent_type"] = arbitration.get("referent_type")
    if chosen is None:
        uncertain = _hypothesis(
            "uncertain",
            "uncertain",
            "uncertain",
            [],
            basis="ambiguous_without_accepted_semantic_arbitration",
        )
        return _structure_fields(case, uncertain, arbitration=arbitration)
    return _structure_fields(case, chosen, arbitration=arbitration)


def _semantic_occurrence_type(structure: Mapping[str, Any], original: str) -> str:
    surface_structure = str(structure.get("surface_structure") or "uncertain")
    return {
        "lexicalized_personal_form": "person_reference",
        "compositional_kinship": "kinship_compositional_reference",
        "office_holder_reference": "office_reference",
        "patron_plus_office": "office_reference",
        "surname_plus_title": "title_reference",
        "ruler_reference": "ruler_reference",
        "honorific_person_reference": "ruler_reference",
        "non_person": "generic_or_non_person_reference",
    }.get(surface_structure, "unclear")


def apply_reference_structures(graph: Mapping[str, Any], structures: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Use finalized structures while preserving the frozen PSL inputs.

    psl1.1's default graph builder remains untouched.  We strip only the old
    role-veto labels (which were calculated from its suffix decision), retain
    all base hard exclusions, then recompute those role vetoes against the
    semantic structure selected for this run.
    """
    result = copy.deepcopy(dict(graph))
    for case in result.get("cases", []) or []:
        key = str(case.get("mention_id"))
        structure = dict(structures.get(key) or {})
        if not structure:
            structure = psl1_1.build_reference_structure(case)
        case["reference_structure"] = structure
        original_occurrence_type = str(case.get("psl_occurrence_type") or case.get("occurrence_type") or "unclear")
        case["prejudgment_original_occurrence_type"] = original_occurrence_type
        case["psl_occurrence_type"] = _semantic_occurrence_type(structure, original_occurrence_type)

        old_vetoes = case.get("psl1_hard_vetoes") or {}
        vetoes: dict[str, list[str]] = {}
        for candidate_key, reasons in old_vetoes.items():
            kept = sorted(set(str(reason) for reason in reasons if str(reason) not in ROLE_VETOES))
            if kept:
                vetoes[str(candidate_key)] = kept
        # Reuse the existing deterministic predicate mutator, but with the
        # pre-judged structure.  It changes no weights.
        psl1_1._tighten_deterministic(case)
        for candidate in case.get("candidates", []) or []:
            reasons = psl1_1._role_vetoes(case, candidate)
            if reasons:
                candidate_key = str(candidate.get("candidate_key"))
                vetoes[candidate_key] = sorted(set(vetoes.get(candidate_key, []) + reasons))
        case["psl1_1_role_vetoes"] = vetoes
        case["psl1_hard_vetoes"] = vetoes
        case["reference_structure_direct_support"] = sorted(
            str(candidate.get("candidate_key"))
            for candidate in case.get("candidates", []) or []
            if psl1_1._direct_reference_support(
                {**case, "psl1_1_role_vetoes": vetoes},
                str(candidate.get("candidate_key")),
            )
        )
        case["candidate_only"] = True
        case["canonical_write_back"] = False
    result["schema"] = "hdb2-psl1-3a-graph-cases-v1"
    result["reference_structure_version"] = RUN_VERSION
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def clean_structural_decisions(decisions: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    """Never expose an anchor/patron as a structural target's final person."""
    result = copy.deepcopy(dict(decisions))
    cases = {str(row.get("mention_id")): row for row in graph.get("cases", []) or []}
    structural = {"compositional_kinship", "patron_plus_office", "surname_plus_title", "non_person"}
    for row in result.get("records", []) or []:
        case = cases.get(str(row.get("mention_id")), {})
        structure = case.get("reference_structure") or {}
        surface_structure = str(structure.get("surface_structure") or "")
        if surface_structure not in structural:
            if surface_structure == "uncertain" and row.get("result_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
                viable = [item for item in row.get("candidate_rankings", []) or [] if not item.get("hard_conflict")]
                row["result_state"] = "review_required" if viable else "genuinely_unresolved"
                row["reference_semantic_uncertain"] = True
                row["candidate_only"] = True
                row["canonical_write_back"] = False
            continue
        if structure.get("referent_candidate") is not None:
            continue
        for field in ("top_candidate", "top_candidate_key", "top_candidate_person_id"):
            row[field] = None
        row["final_candidate"] = None
        row["structural_reference_fields"] = {
            "anchor_person": structure.get("anchor_person") or None,
            "patron_or_possessor": structure.get("patron_or_possessor") or None,
            "holder": structure.get("holder") or None,
            "referent_candidate": structure.get("referent_candidate"),
        }
        row["structural_candidate_suppressed"] = True
        row["result_state"] = "structural_reference"
        row["candidate_only"] = True
        row["canonical_write_back"] = False
    result["schema"] = "hdb2-psl1-3a-decisions-v1"
    result["reference_structure_version"] = RUN_VERSION
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def arbitration_regression_payload(case: Mapping[str, Any], hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Return a test-only offline fixture for the known ambiguous 武子 case.

    This is never used by a live provider.  It makes deterministic replay
    useful in CI without pretending a fixture is a model response.
    """
    if str(case.get("target_surface") or "") != "武子":
        return None
    chosen = next((row for row in hypotheses if row.get("surface_structure") == "lexicalized_personal_form"), None)
    if not chosen:
        return None
    evidence_ids = list(chosen.get("evidence_ids", []) or [])
    return {
        "surface_structure": "lexicalized_personal_form",
        "referent_type": "person",
        "components": [{"text": "武子", "role": "personal_form"}],
        "supporting_evidence_ids": evidence_ids,
        "confidence": "high",
    }


def required_regression_cases() -> tuple[tuple[str, str], ...]:
    return (
        ("05-fangzheng-011", "武子"),
        ("05-fangzheng-028", "敦主簿"),
        ("05-fangzheng-028", "家兄"),
        ("34-pilou-001", "主"),
        ("02-yanyu-046", "謝豫章"),
    )


def reference_regression_records() -> dict[str, Any]:
    """Check the existing structural fixtures without making a provider call.

    The cases are drawn from the frozen PSL1.1/PSL1.3 artifacts.  ``武子`` is
    the one intentionally ambiguous case and uses the same validated offline
    arbitration fixture as the reproducible runner; all other structures are
    deterministic source-syntax checks.
    """
    expected = {
        ("05-fangzheng-011", "武子"): "lexicalized_personal_form",
        ("05-fangzheng-028", "敦主簿"): "patron_plus_office",
        ("05-fangzheng-028", "家兄"): "compositional_kinship",
        ("34-pilou-001", "主"): "non_person",
        ("02-yanyu-046", "謝豫章"): "surname_plus_title",
    }
    graphs = [psl1_3.build_graph(psl1_3.freeze_selection()), *psl1_1.load_psl1_graphs()]
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for graph in graphs:
        for case in graph.get("cases", []) or []:
            key = (str(case.get("story_id") or ""), str(case.get("target_surface") or ""))
            by_key.setdefault(key, case)
    records: list[dict[str, Any]] = []
    for key, expected_structure in expected.items():
        case = by_key.get(key)
        if not case:
            records.append({"story_id": key[0], "surface": key[1], "passed": False, "reason": "case_missing"})
            continue
        info = reference_hypotheses(case)
        arbitration = arbitration_regression_payload(case, info["hypotheses"])
        packet = semantic_packet(case, info["hypotheses"])
        validation = validate_semantic_arbitration(arbitration, packet) if arbitration else None
        structure = finalize_reference_structure(case, arbitration, validation)
        passed = structure.get("surface_structure") == expected_structure
        if key == ("05-fangzheng-028", "敦主簿"):
            passed = passed and structure.get("holder") == "何充" and structure.get("patron_or_possessor") == "敦"
        if key == ("05-fangzheng-028", "家兄"):
            passed = passed and structure.get("anchor_person") == "王敦"
        records.append({
            "story_id": key[0],
            "surface": key[1],
            "expected": expected_structure,
            "actual": structure.get("surface_structure"),
            "reference_type": structure.get("reference_type"),
            "anchor_person": structure.get("anchor_person"),
            "holder": structure.get("holder"),
            "patron_or_possessor": structure.get("patron_or_possessor"),
            "passed": bool(passed),
        })
    return {
        "schema": "hdb2-psl1-3a-reference-regressions-v1",
        "records": records,
        "all_pass": all(row.get("passed") for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def structure_summary(structures: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in structures.values():
        key = str(row.get("surface_structure") or "uncertain")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
