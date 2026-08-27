#!/usr/bin/env python3
"""Candidate-rescue helpers for HDB2-PSL1.2.

PSL1.2 is intentionally an additive layer around the frozen PSL1.1
occurrence resolver.  The diagnostic model call can say that a candidate may
be missing, but it cannot create an entity or change a decision.  Only
source-grounded Python resources can add a candidate, after which the frozen
PSL1.1 inference and reviewer are run again.
"""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import hdb2_lj0_common as lj0
import hdb2_p1_common as p1
import hdb2_psl1_common as psl1
import hdb2_psl1_1_common as psl1_1
import historical_entity_resolver as resolver


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
SELECTION_PATH = ANNOTATION / "hdb2-psl1-2-selection.json"
PSL0_SELECTION = ANNOTATION / "hdb2-psl0-selection.json"
PSL1_SELECTION = ANNOTATION / "hdb2-psl1-selection.json"
PSL1_1_SELECTION = ANNOTATION / "hdb2-psl1-1-selection.json"
PSL1_RUN = ROOT / "data/generated/hdb2-psl1/live/20260827T-HDB2-PSL1-02"
PSL1_1_RUN = ROOT / "data/generated/hdb2-psl1-1/live/20260827T-HDB2-PSL1-1-02"
MODEL = psl1.MODEL
STRICT_ENDPOINT = psl1.STRICT_ENDPOINT
RUN_VERSION = "hdb2-psl1-2-v1"
PROMPT_VERSION = "hdb2-psl1-2-candidate-rescue-v1"
RESCUE_FUNCTION_NAME = "submit_hdb2_candidate_rescue_diagnosis"

RESCUE_DIAGNOSES = {
    "candidate_set_sufficient",
    "candidate_missing_likely",
    "reference_not_person",
    "genuinely_ambiguous",
    "insufficient_evidence",
}
RESCUE_REFERENCE_TYPES = {"person", "office_holder", "ruler_title", "courtesy_name", "kinship", "other"}
RESCUE_STATES = {"review_required", "genuinely_unresolved"}
FORBIDDEN_ID_KEYS = {
    "person_id",
    "provisional_person_id",
    "canonical_person_id",
    "candidate_id",
    "production_person_id",
    "relation_id",
    "graph_id",
}
KINSHIP_SUFFIXES = ("兒", "子", "女", "兄", "弟", "父", "母", "妻", "婿")
OFFICE_SUFFIXES = (
    "主簿", "尹", "太守", "長史", "尚書", "將軍", "司空", "僕射", "廷尉", "侍中",
    "太傅", "中書令", "刺史", "令", "掾",
)
IDENTITY_MARKERS = ("字", "名", "諱", "號", "号")
SOURCE_IDENTITY_KINDS = {"identity_name", "name_identity", "identity"}
GROUND_IDENTITY_ATOM_PATHS = (
    ROOT / "data/generated/hdb2-p1/live/20260825T-HDB2-P1-03/evidence-atoms.json",
    ROOT / "data/generated/hdb2-f/live/20260826T-HDB2-F-02/rescue-evidence-atoms.json",
)


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
    return resolver.matching_normalize(str(value or ""))


def _walk_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key) in FORBIDDEN_ID_KEYS:
                found.append(key_path)
            found.extend(_walk_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_keys(child, f"{path}[{index}]"))
    return found


def _review_items() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("occurrence_id")): dict(row)
        for row in lj0.load_review_items()
        if row.get("occurrence_id")
    }


def _occurrence_ids(document: Mapping[str, Any], *fields: str) -> set[str]:
    values: set[str] = set()
    for field in fields:
        for row in document.get(field, []) or []:
            if isinstance(row, Mapping) and row.get("occurrence_id"):
                values.add(str(row.get("occurrence_id")))
            elif isinstance(row, str):
                values.add(row)
    return values


def previous_occurrence_ids() -> set[str]:
    """Return the complete prior PSL0/PSL1/PSL1.1 occurrence exclusion set."""
    result: set[str] = set()
    for path in (PSL0_SELECTION, PSL1_SELECTION, PSL1_1_SELECTION):
        document = read_json(path, {}) or {}
        result |= _occurrence_ids(document, "cases", "regression_cases", "holdout_cases", "independent_cases")
        result |= {str(value) for value in document.get("development_occurrence_ids", []) if value}
    # PSL1.1 development rows are surface/story labels.  Expand them against
    # the current frozen review projection rather than silently excluding just
    # one occurrence when a story has repeated mentions.
    psl1_1 = read_json(PSL1_1_SELECTION, {}) or {}
    for row in psl1_1.get("development_cases", []) or []:
        if not isinstance(row, Mapping):
            continue
        result |= {
            str(item.get("occurrence_id"))
            for item in _review_items().values()
            if str(item.get("story_id")) == str(row.get("story_id"))
            and str(item.get("target_surface")) == str(row.get("surface"))
            and item.get("occurrence_id")
        }
    return result


def _selection_category(item: Mapping[str, Any]) -> str:
    surface = str(item.get("target_surface") or "")
    typ = str(item.get("occurrence_type") or "")
    review_type = str(item.get("review_type") or "")
    if typ in {"kinship_reference", "kinship_compositional_reference"} or surface.endswith(KINSHIP_SUFFIXES):
        return "compositional_kinship"
    if typ == "ruler_reference" or surface in {"帝", "明帝", "武帝", "元帝", "文帝", "晉武帝"}:
        return "ruler_title"
    if review_type == "office_or_title_holder" or typ in {"title_reference", "office_reference"}:
        return "office_title"
    if typ in {"abbreviated_person_name", "courtesy_name_reference"}:
        return "abbreviated_courtesy"
    if review_type == "identity":
        return "ambiguous_identity"
    return "ordinary_unresolved"


def _selection_score(item: Mapping[str, Any]) -> tuple[int, int, int, str, str]:
    facts = item.get("affected_facts") or {}
    blocked = (
        10 * len(facts.get("marriage", []) or [])
        + 8 * len(facts.get("kinship", []) or [])
        + 4 * len(facts.get("relations", []) or [])
    )
    candidates = len(item.get("candidate_people", []) or [])
    return (
        -blocked,
        -candidates,
        -int(str(item.get("priority") or "") == "P1"),
        str(item.get("story_id") or ""),
        str(item.get("occurrence_id") or ""),
    )


def _selection_row(item: Mapping[str, Any], excluded: set[str]) -> dict[str, Any]:
    facts = item.get("affected_facts") or {}
    source_refs = sorted({
        str(row.get("evidence_ref"))
        for row in item.get("selected_evidence", []) or []
        if row.get("evidence_ref")
    })
    key_material = {
        "occurrence_id": item.get("occurrence_id"),
        "identity_observation_id": item.get("identity_observation_id"),
        "story_id": item.get("story_id"),
        "surface": item.get("target_surface"),
        "source_refs": source_refs,
    }
    return {
        "occurrence_id": item.get("occurrence_id"),
        "identity_observation_id": item.get("identity_observation_id"),
        "story_id": item.get("story_id"),
        "surface": item.get("target_surface"),
        "occurrence_type": item.get("occurrence_type"),
        "review_type": item.get("review_type"),
        "current_status": (item.get("current_state") or {}).get("status") or item.get("status"),
        "priority": item.get("priority"),
        "selection_category": _selection_category(item),
        "blocked_fact_counts": {
            key: len(facts.get(key, []) or []) for key in ("relations", "kinship", "marriage", "office")
        },
        "candidate_set": [
            {"display_name": row.get("display_name") or row.get("label"), "person_id": row.get("person_id")}
            for row in item.get("candidate_people", []) or []
            if row.get("display_name") or row.get("label")
        ],
        "source_refs": source_refs,
        "selection_key": stable_hash(key_material),
        "previous_hng2_excluded": str(item.get("occurrence_id")) in excluded,
    }


def build_selection(path: Path = SELECTION_PATH, *, limit: int = 12) -> dict[str, Any]:
    if limit != 12:
        raise ValueError("psl1_2_selection_must_have_exactly_12_cases")
    excluded = previous_occurrence_ids()
    items = _review_items()
    eligible = [item for item in items.values() if str(item.get("occurrence_id")) not in excluded]
    eligible.sort(key=_selection_score)
    selected = eligible[:limit]
    if len(selected) != limit:
        raise RuntimeError(f"psl1_2_independent_selection_count:{len(selected)}")
    rows = [_selection_row(item, excluded) for item in selected]
    rows.sort(key=lambda row: str(row.get("selection_key") or ""))
    result: dict[str, Any] = {
        "schema": "hdb2-psl1-2-selection-v1",
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
        "independent_cases": rows,
        "independent_count": len(rows),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != result:
            raise RuntimeError("hdb2_psl1_2_selection_changed")
        return existing
    write_json(path, result)
    return result


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    return build_selection(path)


def build_graph(selection: Mapping[str, Any]) -> dict[str, Any]:
    items = _review_items()
    cases = []
    for row in selection.get("independent_cases", []) or []:
        occurrence_id = str(row.get("occurrence_id"))
        if occurrence_id not in items:
            raise RuntimeError(f"psl1_2_selection_item_missing:{occurrence_id}")
        cases.append(items[occurrence_id])
    case_document = lj0.build_cases({
        "schema": "hdb2-psl1-2-independent-input-v1",
        "selection_hash": selection.get("selection_hash"),
        "cases": cases,
    })
    graph = psl1_1.augment_graph(psl1.build_graph_cases(case_document))
    graph["schema"] = "hdb2-psl1-2-graph-cases-v1"
    graph["candidate_only"] = True
    graph["canonical_write_back"] = False
    return graph


def rescue_tool() -> dict[str, Any]:
    properties = {
        "diagnosis": {
            "type": "string",
            "enum": sorted(RESCUE_DIAGNOSES),
            "description": "判断现有候选集是否足以覆盖当前历史指称；这不是人物身份决定，也不能创建人物。",
        },
        "proposed_identity_surface": {
            "type": ["string", "null"],
            "description": "如果怀疑候选缺失，复制原文或 supplied evidence 中出现的可能身份表面；无法提出时使用 JSON null，禁止字符串 null。",
        },
        "reference_type": {
            "type": "string",
            "enum": sorted(RESCUE_REFERENCE_TYPES),
            "description": "当前指称的历史语义类别；不得把 office/title/kinship 直接当作普通人物别名。",
        },
        "search_hints": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string"},
            "description": "仅复制 supplied passage 中可验证的文字检索提示；Python 才能决定是否使用它们。",
        },
        "supporting_evidence_ids": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "只能引用本次 packet 提供的 evidence_id；这些 ID 只解释诊断，不等于历史事实。",
        },
    }
    return {
        "type": "function",
        "function": {
            "name": RESCUE_FUNCTION_NAME,
            "description": "诊断当前候选集是否可能遗漏实体；不得选择 Person ID、创建人物、声明 canonical truth 或使用外部证据。",
            "strict": True,
            "parameters": {
                "type": "object",
                "description": "候选补救诊断，供 Python 做 grounded lookup；不是身份结论。",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def rescue_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": RESCUE_FUNCTION_NAME}}


RESCUE_SYSTEM_PROMPT = """只阅读 supplied occurrence、candidate context 和 evidence_items。判断当前候选集是否可能遗漏一个被原文支持的实体；不要回答谁是最终人物，不要创建 Person ID，不要使用外部知识。candidate_missing_likely 只能表示诊断，之后由 Python 在已登记且有原文依据的资源中查找。search_hints 必须是原文可验证的文字，supporting_evidence_ids 必须来自 packet。reference_not_person 用于结构性/非人物指称。信息不足时明确返回 insufficient_evidence 或 genuinely_ambiguous；JSON null 必须是真 null，不得返回字符串 null。"""


def rescue_trigger(decision: Mapping[str, Any]) -> bool:
    return (
        str(decision.get("result_state") or "") in RESCUE_STATES
        or bool(decision.get("reviewer_rejected_top_candidate"))
    )


def _safe_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "result_state": decision.get("result_state"),
        "top_candidate_key": decision.get("top_candidate_key"),
        "top_candidate": decision.get("top_candidate"),
        "margin": decision.get("margin"),
        "candidate_rankings": [
            {
                key: row.get(key)
                for key in ("candidate_key", "candidate", "link", "raw_score", "hard_conflict")
            }
            for row in decision.get("candidate_rankings", []) or []
        ],
        "reviewer_verdict": decision.get("reviewer_verdict"),
        "reviewer_reason_types": list(decision.get("reviewer_reason_types", []) or []),
    }


def rescue_packet(
    case: Mapping[str, Any],
    decision: Mapping[str, Any],
    graph: Mapping[str, Any],
    reviewer: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    packet = psl1_1.wire_packet(case, graph.get("cases", []), graph)
    packet["task"] = "diagnose whether the supplied candidate set is missing a grounded historical entity"
    packet["current_identity_decision"] = _safe_decision(decision)
    if reviewer:
        payload = reviewer.get("payload") or {}
        packet["last_reviewer"] = {
            "verdict": payload.get("verdict"),
            "reason_types": list(payload.get("reason_types", []) or []),
            "identity_contradictions": list(payload.get("identity_contradictions", []) or []),
        }
    packet["rescue_constraints"] = {
        "diagnosis_is_not_identity": True,
        "python_grounding_required": True,
        "no_production_identity_identifiers": True,
        "same_surface_is_not_identity": True,
        "candidate_only": True,
    }
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def validate_rescue_diagnosis(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors = [f"forbidden_id_field:{path}" for path in _walk_keys(payload)]
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": sorted(set(["payload_not_object", *errors]))}
    expected = {"diagnosis", "proposed_identity_surface", "reference_type", "search_hints", "supporting_evidence_ids"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    if payload.get("diagnosis") not in RESCUE_DIAGNOSES:
        errors.append("diagnosis_invalid")
    if payload.get("reference_type") not in RESCUE_REFERENCE_TYPES:
        errors.append("reference_type_invalid")
    proposed = payload.get("proposed_identity_surface")
    if proposed == "null":
        errors.append("literal_null_invalid:proposed_identity_surface")
    elif proposed is not None and (not isinstance(proposed, str) or not proposed.strip()):
        errors.append("proposed_identity_surface_invalid")
    hints = payload.get("search_hints")
    if not isinstance(hints, list) or not all(isinstance(value, str) and value.strip() for value in hints):
        errors.append("search_hints_invalid")
    elif len(hints) > 6:
        errors.append("search_hints_too_many")
    evidence = payload.get("supporting_evidence_ids")
    supplied = {str(row.get("evidence_id")) for row in packet.get("evidence_items", []) if row.get("evidence_id")}
    if not isinstance(evidence, list) or not all(isinstance(value, str) for value in evidence):
        errors.append("supporting_evidence_ids_invalid")
        evidence = []
    elif len(evidence) > 8:
        errors.append("supporting_evidence_ids_too_many")
    for evidence_id in evidence:
        if evidence_id not in supplied:
            errors.append(f"evidence_reference_invalid:{evidence_id}")
    if payload.get("diagnosis") == "candidate_missing_likely":
        if proposed is not None and not isinstance(proposed, str):
            errors.append("missing_candidate_surface_invalid")
        elif isinstance(proposed, str) and proposed.strip():
            visible_text = "\n".join(
                str(row.get("text") or "")
                for row in packet.get("evidence_items", [])
                if isinstance(row, Mapping)
            )
            # A rescue diagnosis may point Python at a missing candidate, but
            # it may not invent that candidate.  The proposed surface must be
            # visible in the packet that justified the diagnosis.  Python's
            # existing corpus resources decide whether it is an admissible
            # candidate afterwards.
            if proposed not in visible_text:
                errors.append("proposed_identity_surface_not_grounded")
    if payload.get("diagnosis") != "candidate_missing_likely" and proposed is not None:
        # A proposed surface is meaningful only for the missing-candidate
        # diagnosis.  Keeping this fail-closed prevents a stray model field
        # from being interpreted as a candidate hint for another diagnosis.
        errors.append("proposed_identity_surface_unexpected")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def _source_span(text: str, positions: Sequence[int], *, radius: int = 100) -> str:
    """Return a bounded source span around positions.

    The old rescue prototype used the distance between the first target and
    every name in a complete source unit.  That made a 20k-character
    biography/volume look like one identity assertion.  This helper is used
    only after a local relationship has already been established and callers
    reject pairs whose distance is too large.
    """
    positions = [int(value) for value in positions if int(value) >= 0]
    if not positions:
        return ""
    lo = max(0, min(positions) - radius)
    hi = min(len(text), max(positions) + radius)
    return text[lo:hi].strip()


def _local_span(text: str, left: int, right: int, *, before: int = 80, after: int = 120, max_distance: int = 420) -> str:
    if left < 0 or right < 0 or abs(left - right) > max_distance:
        return ""
    lo = max(0, min(left, right) - before)
    hi = min(len(text), max(left, right) + after)
    return text[lo:hi].strip()


def _source_unit_map(units: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(unit.get("ref")): unit for unit in units if unit.get("ref")}


def _candidate_info(candidate: str, inventory: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return dict(inventory.get(matching(candidate), {
        "candidate_surface": candidate,
        "person_id": None,
        "candidate_kind": "source_named_entity",
    }))


def _resource_row(
    *,
    target: str,
    candidate: str,
    info: Mapping[str, Any],
    basis: str,
    direct: bool,
    unit: Mapping[str, Any],
    span: str,
    atom_id: str | None = None,
) -> dict[str, Any] | None:
    source_text = str(unit.get("evidence_text") or "")
    if (
        not candidate
        or not span
        or not target
        or target not in source_text
        or candidate not in source_text
        or span not in source_text
    ):
        return None
    ref = str(unit.get("ref") or "")
    key = (target, candidate, ref, basis, span, atom_id or "")
    row = {
        "resource_id": f"rescue-resource-{stable_hash(key)[:20]}",
        "target_surface": target,
        "candidate_surface": candidate,
        "person_id": info.get("person_id"),
        "candidate_kind": info.get("candidate_kind") or "source_named_entity",
        "basis": basis,
        "direct_identity_support": bool(direct),
        "source_ref": ref,
        "exact_span": span,
        "source_work": unit.get("source_work"),
        "source_layer": unit.get("source_layer"),
        "source_locator": dict(unit.get("locator") or {}) if isinstance(unit.get("locator"), Mapping) else {},
        "source_sha256": unit.get("source_sha256"),
    }
    if atom_id:
        row["grounded_atom_id"] = atom_id
    return row


def _grounded_identity_atom_rows(
    units_by_ref: Mapping[str, Mapping[str, Any]],
    targets: set[str],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Load only already-grounded identity atoms from prior candidate runs.

    These files are frozen candidate evidence, not live model input.  The
    exact span is checked against the current source witness before reuse.
    Generic person-mention/office/kinship atoms are deliberately excluded:
    they are not identity mappings merely because two names co-occur.
    """
    rows: list[dict[str, Any]] = []
    for path in GROUND_IDENTITY_ATOM_PATHS:
        document = read_json(path, {}) or {}
        for atom in document.get("records", []) or []:
            if str(atom.get("atom_kind") or "") not in SOURCE_IDENTITY_KINDS:
                continue
            target = str(atom.get("subject_surface") or "")
            obj = str(atom.get("object_surface") or "")
            if not target or not obj:
                continue
            source_ref = str(atom.get("evidence_ref") or "")
            span = str(atom.get("exact_span") or "")
            unit = units_by_ref.get(source_ref)
            if not unit or not span or span not in str(unit.get("evidence_text") or ""):
                continue
            matched_target = next((wanted for wanted in targets if matching(wanted) in {matching(target), matching(obj)}), None)
            if not matched_target:
                continue
            candidate = obj if matching(matched_target) == matching(target) else target
            # A direct identity atom must actually express an identity/name
            # relationship.  Earlier HDB2 atom artifacts contain some rows
            # whose kind was overly broad; requiring a name marker or a
            # source-level identity phrase keeps those rows fail-closed.
            if not any(marker in span for marker in IDENTITY_MARKERS) and not re.search(r"即[^。；，,]{1,12}(?:一人|也)", span):
                continue
            info = _candidate_info(candidate, inventory)
            row = _resource_row(
                target=matched_target,
                candidate=candidate,
                info=info,
                basis="grounded_identity_atom",
                direct=True,
                unit=unit,
                span=span,
                atom_id=str(atom.get("atom_id") or "") or None,
            )
            if row:
                rows.append(row)
    return rows


def _explicit_identity_mapping_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Find short, explicit ``A字B``/``A名B`` mappings near a target.

    The two names must be the operands of the identity marker.  In
    particular, an ``即`` or ``字`` anywhere in a source volume is not enough
    to relate two nearby catalogue names.
    """
    target_positions = [match.start() for match in re.finditer(re.escape(target), text)]
    if not target_positions:
        return []
    rows: list[dict[str, Any]] = []
    # Use catalogue/HDB1 forms only as the candidate vocabulary.  A source
    # candidate not in the catalogue is admitted below only for the narrow
    # 司馬 title/name and surname-plus-字 patterns.
    for norm_candidate, info in sorted(inventory.items()):
        candidate = str(info.get("candidate_surface") or "")
        if not candidate or matching(candidate) == matching(target):
            continue
        candidate_positions = [match.start() for match in re.finditer(re.escape(candidate), text)]
        for target_pos in target_positions:
            for candidate_pos in candidate_positions:
                span = _local_span(text, target_pos, candidate_pos, max_distance=420)
                if not span:
                    continue
                # The marker must be in the bounded relation, not somewhere
                # else in a source volume.
                marker_pattern = (
                    rf"{re.escape(candidate)}[\s，,:：()（）〔〕「」『』]*"
                    rf"(?:字|名|諱|號)[\s，,:：()（）〔〕「」『』]*{re.escape(target)}"
                )
                reverse_pattern = (
                    rf"{re.escape(target)}[\s，,:：()（）〔〕「」『』]*"
                    rf"(?:字|名|諱|號)[\s，,:：()（）〔〕「」『』]*{re.escape(candidate)}"
                )
                explicit = bool(re.search(marker_pattern, span)) or bool(re.search(reverse_pattern, span))
                if not explicit:
                    continue
                row = _resource_row(
                    target=target,
                    candidate=candidate,
                    info=info,
                    basis="grounded_identity_statement",
                    direct=True,
                    unit=unit,
                    span=span,
                )
                if row:
                    rows.append(row)
                break
    return rows


def _explicit_title_mapping_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Find a title mention adjacent to a source's explicit ``A即B`` name map.

    Some Jianshu notes explain a title (for example 劉尹) in a sentence that
    identifies two name forms (劉恢即劉惔).  The title is not itself one of the
    operands, so this is kept separate from the direct alias parser and still
    requires the map and title to occur in one short note.
    """
    if not target or not _target_looks_office(target):
        return []
    target_positions = [match.start() for match in re.finditer(re.escape(target), text)]
    if not target_positions:
        return []
    rows: list[dict[str, Any]] = []
    for mapping in re.finditer(
        r"(?P<left>[\u3400-\u9fff]{1,8})(?:實)?即(?P<right>[\u3400-\u9fff]{1,8})(?P<tail>一人|也)",
        text,
    ):
        left, right = mapping.group("left"), mapping.group("right")
        for norm_candidate, info in sorted(inventory.items()):
            candidate = str(info.get("candidate_surface") or "")
            if not candidate or candidate not in {left, right}:
                continue
            for target_pos in target_positions:
                span = _local_span(text, target_pos, mapping.start(), max_distance=260)
                if not span:
                    continue
                row = _resource_row(
                    target=target,
                    candidate=candidate,
                    info=info,
                    basis="grounded_title_identity_statement",
                    direct=True,
                    unit=unit,
                    span=span,
                )
                if row:
                    rows.append(row)
                break
    return rows


def _surname_given_name_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Recover a titled surname reference followed by ``given字...``.

    This is a generic shape used by ``祖車騎 ... 逖字士稚``.  It does not
    contain a fixture identity map: the surname is taken from the target and
    the given name is copied from the source pattern.
    """
    if not target or len(target) < 2:
        return []
    surname = target[:1]
    target_pos = text.find(target)
    if target_pos < 0:
        return []
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"(?P<given>[\u3400-\u9fff]{1,2})字[\u3400-\u9fff]{1,4}", text):
        given = str(match.group("given"))
        candidate = surname + given
        if candidate == target or not candidate.startswith(surname):
            continue
        # Require the constructed full name to be independently visible in
        # the same source unit.  Without this guard ``祖車騎`` in one passage
        # could be paired with an unrelated ``敦小字`` elsewhere in the
        # passage and produce the false candidate 祖敦.
        if text.find(candidate) < 0:
            continue
        span = _local_span(text, target_pos, match.start(), max_distance=420)
        if not span:
            continue
        info = _candidate_info(candidate, inventory)
        row = _resource_row(
            target=target,
            candidate=candidate,
            info=info,
            basis="grounded_surname_name_context",
            direct=True,
            unit=unit,
            span=span,
        )
        if row:
            rows.append(row)
    return rows


def _ruler_title_name_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Recover an explicit ``司馬懿|司馬宣王``-style source title link."""
    if not target:
        return []
    title_positions = [match.start() for match in re.finditer(re.escape("司馬" + target), text)]
    if not title_positions:
        return []
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"司馬[\u3400-\u9fff]{1,2}(?![\u3400-\u9fff])", text):
        candidate = match.group(0)
        if candidate == "司馬" + target:
            continue
        for title_pos in title_positions:
            span = _local_span(text, title_pos, match.start(), max_distance=160)
            if not span:
                continue
            # The form must be in a source link/title construction, not just
            # two arbitrary 司馬 names in a large chronicle unit.
            between = text[min(title_pos, match.start()):max(title_pos, match.start()) + max(len(candidate), len(target) + 2) + 8]
            if "|" not in between and not re.search(r"司馬[\u3400-\u9fff]{1,2}(?:字|諱|名)", between):
                continue
            row = _resource_row(
                target=target,
                candidate=candidate,
                info=_candidate_info(candidate, inventory),
                basis="grounded_title_name_context",
                direct=True,
                unit=unit,
                span=span,
            )
            if row:
                rows.append(row)
            break
    return rows


def _title_holder_rows(
    text: str,
    target: str,
    unit: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Use a short title-holder construction, never arbitrary co-occurrence."""
    if not _target_looks_office(target):
        return []
    target_positions = [match.start() for match in re.finditer(re.escape(target), text)]
    rows: list[dict[str, Any]] = []
    for norm_candidate, info in sorted(inventory.items()):
        candidate = str(info.get("candidate_surface") or "")
        if not candidate or matching(candidate) == matching(target):
            continue
        # A title rescue is allowed to inspect a same-surname named person
        # (e.g. 孔廷尉 -> 孔坦).  A neighbouring unrelated catalogue name such
        # as 何充 is not an office-holder candidate merely because the source
        # paragraph also contains ``用`` or ``為``.
        if not candidate.startswith(target[:1]):
            continue
        for target_pos in target_positions:
            candidate_positions = [match.start() for match in re.finditer(re.escape(candidate), text)]
            for candidate_pos in candidate_positions:
                span = _local_span(text, target_pos, candidate_pos, max_distance=260)
                if not span:
                    continue
                # Require an explicit appointment/holder construction or a
                # source sentence that names the office-holder after the
                # title.  Plain same-window co-occurrence is insufficient.
                if not any(verb in span for verb in ("用", "為", "爲", "拜", "除", "任", "授")):
                    continue
                row = _resource_row(
                    target=target,
                    candidate=candidate,
                    info=info,
                    basis="grounded_title_holder_context",
                    direct=True,
                    unit=unit,
                    span=span,
                )
                if row:
                    rows.append(row)
                break
    return rows


def _catalogue_inventory() -> dict[str, dict[str, Any]]:
    catalog = hng02.person_catalog()
    inventory: dict[str, dict[str, Any]] = {}
    for person_id, person in sorted(catalog.items()):
        display = str(person.get("canonical_name") or "")
        if not display:
            continue
        forms = [display, *(person.get("forms") or [])]
        for form in forms:
            form = str(form or "")
            if form:
                inventory.setdefault(matching(form), {
                    "candidate_surface": display,
                    "person_id": str(person_id),
                    "candidate_kind": "existing_person",
                })
    return inventory


def _hdb1_inventory() -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for filename in ("hdb1-identity-candidates.json", "hdb1-wave2-identity-candidates.json"):
        document = read_json(ANNOTATION / filename, {}) or {}
        for row in document.get("records", []) or []:
            surface = str(row.get("surface") or "")
            if not surface:
                continue
            pid = str(row.get("resolved_person_id") or "")
            provisional = str(row.get("provisional_person_id") or "")
            if pid:
                inventory.setdefault(matching(surface), {
                    "candidate_surface": surface,
                    "person_id": pid,
                    "candidate_kind": "hdb1_existing_projection",
                })
            elif row.get("identity_status") == "resolved_new_candidate" or provisional:
                inventory.setdefault(matching(surface), {
                    "candidate_surface": surface,
                    "person_id": None,
                    "candidate_kind": "hdb1_new_candidate",
                    "provisional_label": provisional,
                })
    return inventory


def _ruler_inventory() -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    document = read_json(ANNOTATION / "ruler-identities-e0.json", {}) or {}
    for row in document.get("records", []) or []:
        personal = row.get("personal_name") or {}
        title = row.get("canonical_title") or {}
        person_surface = str(personal.get("original") or personal.get("simplified") or "")
        if not person_surface:
            continue
        for value in [title.get("original"), title.get("simplified"), *(row.get("aliases") or [])]:
            if isinstance(value, Mapping):
                value = value.get("original") or value.get("simplified")
            if value:
                inventory.setdefault(matching(value), {
                    "candidate_surface": person_surface,
                    "person_id": None,
                    "candidate_kind": "ruler_registry",
                })
    return inventory


def _target_looks_office(target: str) -> bool:
    return any(target.endswith(suffix) for suffix in OFFICE_SUFFIXES)


def build_grounded_resource_index(target_surfaces: Sequence[str]) -> list[dict[str, Any]]:
    """Search only registered local witnesses and return compact grounded rows.

    The returned index contains no model claims and no source-wide payloads;
    each row is an exact source span that can be attached to a rescue
    candidate.  The expensive source index is existing HDB2-P1 machinery.
    """
    targets = sorted({str(value) for value in target_surfaces if value})
    inventory = _catalogue_inventory()
    for key, value in _hdb1_inventory().items():
        inventory.setdefault(key, value)
    for key, value in _ruler_inventory().items():
        inventory.setdefault(key, value)
    units = p1.build_source_index()
    units_by_ref = _source_unit_map(units)
    resources: list[dict[str, Any]] = _grounded_identity_atom_rows(units_by_ref, set(targets), inventory)
    for unit in units:
        text = str(unit.get("evidence_text") or "")
        if not text:
            continue
        for target in targets:
            if target not in text:
                continue
            resources.extend(_explicit_identity_mapping_rows(text, target, unit, inventory))
            resources.extend(_explicit_title_mapping_rows(text, target, unit, inventory))
            resources.extend(_surname_given_name_rows(text, target, unit, inventory))
            resources.extend(_ruler_title_name_rows(text, target, unit, inventory))
            resources.extend(_title_holder_rows(text, target, unit, inventory))
            # Registry/title projection is deliberately limited to the
            # target's own visible ruler form.  It is not a person identity
            # assertion and therefore cannot create an identity candidate by
            # itself, but it can be retained as a grounded lookup resource.
            if target in {str(value.get("candidate_surface")) for value in _ruler_inventory().values()}:
                for info in _ruler_inventory().values():
                    candidate = str(info.get("candidate_surface") or "")
                    if candidate and candidate in text and matching(candidate) != matching(target):
                        target_pos, candidate_pos = text.find(target), text.find(candidate)
                        span = _local_span(text, target_pos, candidate_pos, max_distance=180)
                        if span:
                            row = _resource_row(
                                target=target,
                                candidate=candidate,
                                info=info,
                                basis="ruler_registry_projection",
                                direct=False,
                                unit=unit,
                                span=span,
                            )
                            if row:
                                resources.append(row)
    unique: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for row in resources:
        key = (
            str(row.get("target_surface")),
            str(row.get("candidate_surface")),
            str(row.get("source_ref")),
            str(row.get("basis")),
            str(row.get("exact_span")),
            str(row.get("grounded_atom_id") or ""),
        )
        unique.setdefault(key, row)
    resources = list(unique.values())
    resources.sort(key=lambda row: (
        str(row.get("target_surface")),
        0 if row.get("direct_identity_support") else 1,
        str(row.get("basis")),
        str(row.get("candidate_surface")),
        str(row.get("source_ref")),
        str(row.get("resource_id")),
    ))
    return resources


def find_grounded_rescue_candidates(
    case: Mapping[str, Any],
    diagnosis: Mapping[str, Any],
    resources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    target = str(case.get("target_surface") or "")
    proposed = str(diagnosis.get("proposed_identity_surface") or "")
    if diagnosis.get("diagnosis") != "candidate_missing_likely":
        return {"candidates": [], "evidence": [], "diagnosis_used": diagnosis.get("diagnosis")}
    current = {
        matching(str(row.get("display_name") or ""))
        for row in case.get("candidates", []) or []
    }
    selected: list[dict[str, Any]] = []
    for row in resources:
        if str(row.get("target_surface")) != target:
            continue
        candidate = str(row.get("candidate_surface") or "")
        if not candidate or matching(candidate) in current:
            continue
        # Registry projections and nearby title occurrences are useful audit
        # context, but they are not enough to add an identity candidate.
        # Rescue is deliberately source-grounded: only an identity-bearing
        # source construction can enter the second PSL pass.
        if not row.get("direct_identity_support"):
            continue
        locator = row.get("source_locator") if isinstance(row.get("source_locator"), Mapping) else {}
        if proposed and matching(proposed) not in {matching(candidate), matching(str(locator.get("title") or ""))}:
            continue
        selected.append(dict(row))
    # If the model did not propose a surface, the source-grounded search may
    # still return a candidate only when the exact source row itself supplied
    # an identity-bearing relation.  Do not return arbitrary co-occurrences.
    if not proposed:
        selected = [row for row in selected if row.get("direct_identity_support")]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in selected:
        key = (str(row.get("candidate_surface")), str(row.get("person_id") or ""))
        bucket = grouped.setdefault(key, {
            "candidate_surface": row.get("candidate_surface"),
            "person_id": row.get("person_id"),
            "candidate_kind": row.get("candidate_kind"),
            "basis": row.get("basis"),
            "direct_identity_support": bool(row.get("direct_identity_support")),
            "evidence": [],
        })
        bucket["direct_identity_support"] = bool(bucket["direct_identity_support"] or row.get("direct_identity_support"))
        bucket["evidence"].append(dict(row))
    candidates = sorted(grouped.values(), key=lambda row: (
        0 if row.get("direct_identity_support") else 1,
        str(row.get("candidate_surface")),
        str(row.get("person_id") or ""),
    ))
    for row in candidates:
        row["evidence"] = sorted(row["evidence"], key=lambda value: (str(value.get("source_ref")), str(value.get("resource_id"))))[:8]
    return {
        "candidates": candidates,
        "evidence": [evidence for row in candidates for evidence in row.get("evidence", [])],
        "diagnosis_used": diagnosis.get("diagnosis"),
    }


def _candidate_profile(person_id: str | None, display: str) -> dict[str, Any]:
    if person_id:
        try:
            knowledge = lj0.load_person_knowledge()
            return lj0._candidate_profile(person_id, display, knowledge)
        except (AttributeError, KeyError):
            pass
    return {"canonical_name": display, "aliases": [], "courtesy_names": [], "titles": []}


def add_rescue_candidates(
    graph: Mapping[str, Any],
    occurrence_id: str,
    grounded: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = copy.deepcopy(graph)
    provenance: list[dict[str, Any]] = []
    for case in result.get("cases", []):
        if str(case.get("occurrence_id")) != str(occurrence_id):
            continue
        existing = list(case.get("candidates", []) or [])
        for rescued in grounded.get("candidates", []) or []:
            display = str(rescued.get("candidate_surface") or "")
            if not display:
                continue
            if any(
                matching(str(row.get("display_name") or "")) == matching(display)
                and str(row.get("person_id") or "") == str(rescued.get("person_id") or "")
                for row in existing
            ):
                continue
            key_material = {
                "occurrence_id": occurrence_id,
                "display": display,
                "evidence": rescued.get("evidence", []),
            }
            local_id = f"local:psl1-2-rescue:{stable_hash(key_material)[:20]}"
            candidate = {
                "display_name": display,
                "person_id": rescued.get("person_id"),
                "source": "grounded_candidate_rescue",
                "semantic_type": "ruler_title" if str(case.get("occurrence_type")) == "ruler_reference" else "person",
                "profile": _candidate_profile(str(rescued.get("person_id")) if rescued.get("person_id") else None, display),
                "candidate_node_id": f"person:{rescued.get('person_id')}" if rescued.get("person_id") else local_id,
                "rescue_provenance": list(rescued.get("evidence", []) or []),
                "rescue_basis": rescued.get("basis"),
            }
            existing.append(candidate)
            provenance.append({
                "mention_id": case.get("mention_id"),
                "occurrence_id": occurrence_id,
                "candidate_surface": display,
                "person_id": rescued.get("person_id"),
                "candidate_node_id": candidate["candidate_node_id"],
                "basis": rescued.get("basis"),
                "direct_identity_support": bool(rescued.get("direct_identity_support")),
                "evidence": list(rescued.get("evidence", []) or []),
            })
        case["candidates"] = psl1_1._rekey_candidates(existing)
        case["candidate_keys"] = [row.get("candidate_key") for row in case["candidates"]]
        # Add compact source evidence to the reviewer packet.  The exact span
        # is the only text transferred; the source index itself is never sent.
        for item in provenance:
            if str(item.get("occurrence_id")) != str(occurrence_id):
                continue
            for evidence in item.get("evidence", []) or []:
                evidence_id = f"rescue:{evidence.get('resource_id')}"
                if any(str(row.get("evidence_id")) == evidence_id for row in case.get("evidence_items", []) or []):
                    continue
                case.setdefault("evidence_items", []).append({
                    "evidence_id": evidence_id,
                    "family": "rescue_grounded_evidence",
                    "kind": "source_identity_evidence",
                    "source_ref": evidence.get("source_ref"),
                    "text": evidence.get("exact_span"),
                    "source_work": evidence.get("source_work"),
                    "source_layer": evidence.get("source_layer"),
                })
        psl1_1._tighten_deterministic(case)
        vetoes = {str(key): list(value) for key, value in (case.get("psl1_hard_vetoes") or {}).items()}
        for candidate in case.get("candidates", []):
            reasons = psl1_1._role_vetoes(case, candidate)
            if reasons:
                key = str(candidate.get("candidate_key"))
                vetoes[key] = sorted(set(vetoes.get(key, []) + reasons))
        case["psl1_hard_vetoes"] = vetoes
        case["psl1_1_role_vetoes"] = vetoes
        case["candidate_only"] = True
        case["canonical_write_back"] = False
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    result["schema"] = "hdb2-psl1-2-rescue-graph-v1"
    return result, provenance


def rescue_predicates(graph: Mapping[str, Any], provenance: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    by_occurrence = {str(case.get("occurrence_id")): case for case in graph.get("cases", [])}
    for row in provenance:
        case = by_occurrence.get(str(row.get("occurrence_id")), {})
        candidate_key = next(
            (
                str(candidate.get("candidate_key"))
                for candidate in case.get("candidates", []) or []
                if str(candidate.get("display_name")) == str(row.get("candidate_surface"))
                and str(candidate.get("person_id") or "") == str(row.get("person_id") or "")
            ),
            None,
        )
        if not candidate_key or not row.get("direct_identity_support"):
            continue
        evidence_ids = [f"rescue:{evidence.get('resource_id')}" for evidence in row.get("evidence", []) or []]
        result.append({
            "mention_id": case.get("mention_id"),
            "predicate": "IdentityContextSupport",
            "candidate_key": candidate_key,
            "value": 1.0,
            "evidence_ids": evidence_ids[:8],
            "reason": "python_grounded_candidate_rescue",
            "rescue": True,
        })
    return result


def required_regression_records() -> dict[str, Any]:
    """Offline resource-backed checks for the four requested missed forms."""
    required = [
        ("宣王", "33-youhui-007", "司馬懿"),
        ("祖車騎", "08-shangyu-043", "祖逖"),
        ("孔廷尉", "05-fangzheng-037", "孔坦"),
        ("劉尹", "02-yanyu-054", "劉惔"),
    ]
    items = _review_items()
    resources = build_grounded_resource_index([surface for surface, _, _ in required])
    records: list[dict[str, Any]] = []
    for surface, story_id, expected in required:
        item = next((row for row in items.values() if str(row.get("target_surface")) == surface and str(row.get("story_id")) == story_id), None)
        if item is None:
            records.append({"surface": surface, "story_id": story_id, "expected": expected, "found": False, "passed": False, "reason": "source_case_missing"})
            continue
        case_doc = lj0.build_cases({"schema": "hdb2-psl1-2-required-regression-v1", "cases": [item]})
        graph = psl1_1.augment_graph(psl1.build_graph_cases(case_doc))
        case = graph.get("cases", [])[0] if graph.get("cases") else {}
        diagnosis = {"diagnosis": "candidate_missing_likely", "proposed_identity_surface": expected}
        grounded = find_grounded_rescue_candidates(case, diagnosis, resources)
        rescued_graph, provenance = add_rescue_candidates(graph, str(item.get("occurrence_id")), grounded)
        predicates = rescue_predicates(rescued_graph, provenance)
        decision = psl1_1.infer_graph(rescued_graph, predicates).get("records", [])
        row = decision[0] if decision else {}
        found = any(str(candidate.get("candidate")) == expected for candidate in row.get("candidate_rankings", []) or [])
        top = str(row.get("top_candidate") or "")
        records.append({
            "surface": surface,
            "story_id": story_id,
            "occurrence_id": item.get("occurrence_id"),
            "expected": expected,
            "found": found,
            "top_candidate": top,
            "rescued": [str(candidate.get("candidate_surface")) for candidate in grounded.get("candidates", []) or []],
            "provenance": provenance,
            "passed": bool(found and top == expected),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-2-required-regressions-v1",
        "records": records,
        "all_pass": all(bool(row.get("passed")) for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def false_resolution_regression() -> dict[str, Any]:
    false_cases = [("主", "34-pilou-001", "王敦"), ("謝豫章", "02-yanyu-046", "謝尚"), ("敦主簿", "05-fangzheng-028", "王敦")]
    items = _review_items()
    records: list[dict[str, Any]] = []
    for surface, story_id, wrong in false_cases:
        item = next((row for row in items.values() if str(row.get("target_surface")) == surface and str(row.get("story_id")) == story_id), None)
        if item is None:
            records.append({"surface": surface, "story_id": story_id, "passed": False, "reason": "source_case_missing"})
            continue
        graph = psl1_1.augment_graph(psl1.build_graph_cases(lj0.build_cases({"schema": "hdb2-psl1-2-false-regression-v1", "cases": [item]})))
        decision = psl1_1.infer_graph(graph, []).get("records", [])
        top = decision[0].get("top_candidate") if decision else None
        records.append({"surface": surface, "story_id": story_id, "wrong": wrong, "top_candidate": top, "passed": top != wrong, "candidate_only": True, "canonical_write_back": False})
    return {"schema": "hdb2-psl1-2-false-regressions-v1", "records": records, "all_pass": all(row.get("passed") for row in records), "candidate_only": True, "canonical_write_back": False}
