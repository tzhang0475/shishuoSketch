#!/usr/bin/env python3
"""HDA2: independently verify high-risk HDA1 identity findings.

HDA2 is an additive remediation overlay.  It deliberately does not rewrite
HDA1, HDB2-F, or the canonical Person registry.  The selection is bounded so
that a partially available provider cannot turn an audit backlog into an
uncontrolled production write; every unselected finding remains in the HDA1
review artifacts.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hda1_identity_audit as hda1  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import sfh2r_contract  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hda2"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hda2-identity-remediation-v1"
PROMPT_VERSION = "hda2-independent-remediation-v1"
SCHEMA = "hda2-identity-remediation-v1"
SELECTION_PATH = OUT / "remediation-selection.json"
MAX_REMEDIATION_CLAIMS = 32

VERDICTS = {
    "retain_existing",
    "reject_existing",
    "propose_alternative",
    "remain_ambiguous",
    "insufficient_evidence",
}
REASON_TYPES = {
    "explicit_identity",
    "different_named_person",
    "courtesy_name_assertion",
    "title_holder",
    "local_coreference",
    "comparison_distinctness",
    "source_context",
    "surface_only_match",
    "insufficient_context",
    "other",
}
IDENTITY_MARKERS = ("字", "名", "諱", "號", "号", "小字", "字曰", "姓")
KINSHIP_MARKERS = ("父", "子", "女", "兄", "弟", "母", "妻", "婿", "甥")
OFFICE_MARKERS = ("太守", "將軍", "将军", "丞相", "尚書", "尚书", "太傅", "司空", "僕射", "仆射", "中丞", "主簿", "主簿")
STORY_PATTERN = re.compile(r"\b\d{2}-[a-z]+-\d{3}\b")


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text(value: Any) -> str:
    return str(value or "").strip()


def story_index() -> dict[str, dict[str, Any]]:
    return hda1.story_index()


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _hda1_result_path() -> Path:
    pointer = read_json(ROOT / "data/generated/hda1/audit-results.json", {}) or {}
    relative = text(pointer.get("results_path"))
    if relative:
        candidate = ROOT / relative
        if candidate.is_file():
            return candidate
    candidates = sorted((ROOT / "data/generated/hda1/live").glob("*/audit-results.json"))
    return candidates[-1] if candidates else ROOT / "data/generated/hda1/audit-results.json"


def hda1_inputs() -> dict[str, str]:
    paths = {
        "hda1_claims": ROOT / "data/generated/hda1/claims.json",
        "hda1_audit_results": _hda1_result_path(),
        "person_registry": ROOT / "data/people.json",
        "hdb2_f_person_knowledge": ROOT / "data/derived/hdb2-f-person-knowledge.json",
        "hdb2_f_identity_summary": ROOT / "data/derived/hdb2-f-identity-summary.json",
        "hdb2_f_identity_claim_integrity": ROOT / "data/derived/hdb2-f-identity-claim-integrity-audit.json",
    }
    return {_relative(path): file_hash(path) for path in paths.values() if path.is_file()}


def _frozen_selection_inputs() -> dict[str, str]:
    """Return the old HDA2 snapshot only across the explicit SFH2R bridge.

    HDA2 is a completed, frozen remediation experiment.  Its selection and
    packet provenance refer to the pre-SFH2R derived profile projection.  The
    active projection is now repaired, so a reproducibility rebuild must use
    the recorded historical input snapshot while still rejecting any drift
    not covered by the SFH2R transition manifest.
    """
    current = hda1_inputs()
    selection = read_json(SELECTION_PATH, {}) or {}
    frozen = selection.get("hda1_input_hashes") if isinstance(selection, Mapping) else None
    if isinstance(frozen, Mapping) and sfh2r_contract.frozen_hashes_are_current_or_authorized(frozen, current):
        return {str(key): str(value) for key, value in frozen.items()}
    return current


def _load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    claims_doc = read_json(ROOT / "data/generated/hda1/claims.json", {}) or {}
    claims = [dict(row) for row in claims_doc.get("claims", []) or [] if isinstance(row, Mapping)]
    result_doc = read_json(_hda1_result_path(), {}) or {}
    results = [dict(row) for row in result_doc.get("results", []) or [] if isinstance(row, Mapping)]
    people_doc = read_json(ROOT / "data/people.json", {}) or {}
    people = {text(row.get("person_id")): dict(row) for row in people_doc.get("people", []) or [] if text(row.get("person_id"))}
    return claims, results, people, result_doc


def _hdb2_identity_rows() -> list[dict[str, Any]]:
    document = read_json(ROOT / "data/derived/hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    return [dict(row) for row in document.get("identity_observations", []) or [] if isinstance(row, Mapping)]


def _person_degree() -> collections.Counter[str]:
    counter: collections.Counter[str] = collections.Counter()
    graph = read_json(ROOT / "data/derived/hg0-graph-projection.json", {}) or {}
    for edge in graph.get("edges", []) or []:
        if not isinstance(edge, Mapping):
            continue
        for side in (edge.get("source"), edge.get("target")):
            if isinstance(side, Mapping) and text(side.get("node_type")) == "Person":
                counter[text(side.get("node_id"))] += 1
    return counter


def _risk_indexes(claims: Sequence[Mapping[str, Any]]) -> dict[str, collections.Counter[str]]:
    surface_frequency: collections.Counter[str] = collections.Counter(text(row.get("surface")) for row in claims)
    surface_stories: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
    candidate_uses: collections.Counter[str] = collections.Counter()
    for row in claims:
        surface = text(row.get("surface"))
        if surface and text(row.get("story_id")):
            surface_stories[surface].add(text(row.get("story_id")))
    for row in _hdb2_identity_rows():
        surface = text(row.get("surface"))
        if surface:
            candidate_uses[surface] += 1
    return {
        "surface_frequency": surface_frequency,
        "story_count": collections.Counter({key: len(value) for key, value in surface_stories.items()}),
        "candidate_uses": candidate_uses,
        "person_degree": _person_degree(),
    }


def _risk(claim: Mapping[str, Any], result: Mapping[str, Any], indexes: Mapping[str, collections.Counter[str]]) -> dict[str, Any]:
    surface = text(claim.get("surface"))
    pid = text(claim.get("person_id"))
    execution = text(result.get("execution_status"))
    verdict = text(result.get("verdict"))
    if verdict == "contradict":
        finding_rank = 0
    elif verdict == "ambiguous":
        finding_rank = 1
    elif execution == "validated":
        finding_rank = 2
    else:
        finding_rank = 3
    frequency = indexes["surface_frequency"][surface]
    story_count = indexes["story_count"][surface]
    candidate_uses = indexes["candidate_uses"][surface]
    degree = indexes["person_degree"][pid]
    identity_bearing = int(text(claim.get("identity_basis")) in {"catalogue_exact_match", "evidence_identity_assertion", "catalogue_source_evidence"} or text(claim.get("claim_type")) in {"catalogue_alias", "person_catalogue_source_evidence"})
    structural = int(any(marker in surface for marker in KINSHIP_MARKERS + OFFICE_MARKERS) or text(claim.get("reference_form")) in {"office_title_only", "title", "courtesy"})
    propagation = frequency + story_count + candidate_uses + degree + (2 * identity_bearing) + structural
    return {
        "finding_rank": finding_rank,
        "surface_frequency": frequency,
        "story_count": story_count,
        "candidate_generation_uses": candidate_uses,
        "person_degree": degree,
        "identity_bearing": bool(identity_bearing),
        "structural_hint": bool(structural),
        "propagation_risk": propagation,
    }


def build_selection() -> dict[str, Any]:
    claims, results, _, _ = _load_inputs()
    claims_by_id = {text(row.get("claim_id")): row for row in claims}
    indexes = _risk_indexes(claims)
    flagged: list[dict[str, Any]] = []
    for result in results:
        claim = claims_by_id.get(text(result.get("claim_id")))
        if not claim:
            continue
        if text(result.get("verdict")) == "support" and text(result.get("execution_status")) == "validated" and result.get("adequate_evidence") is not False:
            continue
        risk = _risk(claim, result, indexes)
        flagged.append({
            "claim_id": claim.get("claim_id"),
            "person_id": claim.get("person_id"),
            "canonical_name": claim.get("canonical_name"),
            "surface": claim.get("surface"),
            "story_id": claim.get("story_id"),
            "occurrence_id": claim.get("occurrence_id"),
            "claim_type": claim.get("claim_type"),
            "hda1_verdict": result.get("verdict"),
            "hda1_execution_status": result.get("execution_status"),
            "selection_reason": "HDA1 non-support finding prioritized by propagation risk; validated contradictions and validated insufficiency precede unavailable provider records",
            "risk": risk,
            "selection_key": stable_hash({"claim_id": claim.get("claim_id"), "risk": risk}),
        })
    flagged.sort(key=lambda row: (
        int((row.get("risk") or {}).get("finding_rank", 9)),
        -int((row.get("risk") or {}).get("propagation_risk", 0)),
        -int((row.get("risk") or {}).get("surface_frequency", 0)),
        text(row.get("claim_id")),
    ))
    selected = flagged[:MAX_REMEDIATION_CLAIMS]
    core = {
        "schema": "hda2-remediation-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "selected_claim_count": len(selected),
        "available_flagged_claim_count": len(flagged),
        "records": selected,
        "hda1_input_hashes": _frozen_selection_inputs(),
        "selection_method": "deterministic risk-ranked bounded remediation; no HDA2 model output used",
        "max_claims": MAX_REMEDIATION_CLAIMS,
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "selection_hash": None,
    }
    core["selection_hash"] = stable_hash({key: value for key, value in core.items() if key != "selection_hash"})
    return core


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    proposed = build_selection()
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hda2_remediation_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def _compact(text_value: str, needles: Sequence[str], radius: int = 520) -> str:
    if not text_value:
        return ""
    positions = [text_value.find(needle) for needle in needles if needle and text_value.find(needle) >= 0]
    position = min(positions) if positions else 0
    needle_length = max((len(needle) for needle in needles if needle and text_value.find(needle) >= 0), default=0)
    return text_value[max(0, position - radius):min(len(text_value), position + needle_length + radius)]


def _source_ref(story_id: str, layer: str, annotation_id: str = "") -> str:
    if layer == "liu_annotation":
        return f"hda2-shishuo-liu-{story_id}-{annotation_id}"
    return f"hda2-shishuo-main-{story_id}"


def _evidence_item(*, evidence_id: str, source_ref: str, work: str, layer: str, evidence_text: str, exact_span: str, story_id: str, locator: Mapping[str, Any] | None = None, source_hash: str | None = None, rank: int = 0) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_ref": source_ref,
        "source_work": work,
        "source_layer": layer,
        "evidence_text": evidence_text,
        "exact_span": exact_span,
        "exact_span_grounded": bool(exact_span and exact_span in evidence_text),
        "story_id": story_id,
        "locator": dict(locator or {}),
        "source_hash": source_hash,
        "rank": rank,
    }


def _search_windows(claim: Mapping[str, Any], result: Mapping[str, Any], stories: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    surface = text(claim.get("surface"))
    canonical = text(claim.get("canonical_name"))
    suggested = text(result.get("suggested_identity_surface"))
    terms = [term for term in dict.fromkeys((surface, canonical, suggested)) if term]
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    original_ref = text(claim.get("evidence_ref"))
    original_unit = hda1._source_unit(original_ref, stories)
    if original_unit:
        source_text = text(original_unit.get("evidence_text"))
        exact = text(claim.get("exact_span"))
        candidates.append(((-100, -int(bool(exact and exact in source_text)), 0, original_ref), _evidence_item(
            evidence_id=f"hda2-ev-{stable_hash({'claim': claim.get('claim_id'), 'ref': original_ref})[:20]}",
            source_ref=original_ref,
            work=text(original_unit.get("source_work")) or "registered source",
            layer=text(original_unit.get("source_layer")) or "source",
            evidence_text=_compact(source_text, terms),
            exact_span=exact,
            story_id=text(claim.get("story_id")),
            locator=original_unit.get("locator"),
            source_hash=text(original_unit.get("source_sha256")) or None,
            rank=0,
        )))
    detail = claim.get("source_detail") if isinstance(claim.get("source_detail"), Mapping) else {}
    registry_snippet = text(detail.get("evidence_snippet")) or text(detail.get("snippet"))
    if registry_snippet:
        exact = surface if surface in registry_snippet else (canonical if canonical in registry_snippet else "")
        ref = f"hda2-registered-{text(claim.get('claim_id'))}"
        candidates.append(((-90, -int(bool(exact)), 0, ref), _evidence_item(
            evidence_id=f"hda2-ev-{stable_hash({'claim': claim.get('claim_id'), 'ref': ref})[:20]}",
            source_ref=ref,
            work="registered source evidence",
            layer="registered_alias",
            evidence_text=_compact(registry_snippet, terms, 560),
            exact_span=exact,
            story_id=text(claim.get("story_id")),
            locator={"claim_id": claim.get("claim_id")},
            source_hash=text(claim.get("source_hash")) or None,
            rank=1,
        )))
    for story_id, story in sorted(stories.items()):
        main = text(story.get("main_text"))
        if not main or not any(term in main for term in terms):
            continue
        score = -sum(main.count(term) for term in terms)
        score -= 8 * int(any(marker in main for marker in IDENTITY_MARKERS))
        score -= 4 * int(any(marker in main for marker in KINSHIP_MARKERS))
        score -= 4 * int(any(marker in main for marker in OFFICE_MARKERS))
        exact = next((term for term in (suggested, surface, canonical) if term and term in main), "")
        ref = _source_ref(story_id, "main_text")
        item = _evidence_item(
            evidence_id=f"hda2-ev-{stable_hash({'claim': claim.get('claim_id'), 'ref': ref})[:20]}",
            source_ref=ref,
            work="世說正文",
            layer="main_text",
            evidence_text=_compact(main, terms),
            exact_span=exact,
            story_id=story_id,
            locator={"story_id": story_id, "chapter": story.get("chapter_heading")},
            source_hash=text(story.get("source_sha256")) or None,
            rank=2,
        )
        candidates.append(((score, 0, 1, ref), item))
        for annotation in story.get("liu_annotations", []) or []:
            if not isinstance(annotation, Mapping):
                continue
            annotation_text = text(annotation.get("text"))
            if not annotation_text or not any(term in annotation_text for term in terms):
                continue
            annotation_id = text(annotation.get("annotation_id"))
            exact = next((term for term in (suggested, surface, canonical) if term and term in annotation_text), "")
            ref = _source_ref(story_id, "liu_annotation", annotation_id)
            item = _evidence_item(
                evidence_id=f"hda2-ev-{stable_hash({'claim': claim.get('claim_id'), 'ref': ref})[:20]}",
                source_ref=ref,
                work="劉注",
                layer="liu_annotation",
                evidence_text=_compact(annotation_text, terms, 460),
                exact_span=exact,
                story_id=story_id,
                locator={"story_id": story_id, "annotation_id": annotation_id},
                source_hash=text(story.get("source_sha256")) or None,
                rank=3,
            )
            candidates.append(((score - 3, 0, 0, ref), item))
    candidates.sort(key=lambda pair: pair[0])
    result_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    chars = 0
    for _, item in candidates:
        ref = text(item.get("source_ref"))
        if not ref or ref in seen or not item.get("evidence_text"):
            continue
        remaining = 2000 - chars
        if remaining <= 0:
            break
        if len(text(item.get("evidence_text"))) > remaining:
            item["evidence_text"] = text(item.get("evidence_text"))[:remaining]
            item["exact_span_grounded"] = bool(item.get("exact_span") and item["exact_span"] in item["evidence_text"])
        seen.add(ref)
        result_items.append(item)
        chars += len(text(item.get("evidence_text")))
        if len(result_items) >= 4:
            break
    return result_items


def _local_participants(story_id: str, surface: str, people: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in _hdb2_identity_rows() if text(row.get("story_id")) == story_id and text(row.get("surface")) != surface and text(row.get("resolved_person_id")) in people]
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        pid = text(row.get("resolved_person_id"))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        result.append({"surface": row.get("surface"), "person_id": pid, "canonical_name": people[pid].get("canonical_name"), "evidence_ref": row.get("evidence_ref")})
    return result[:10]


def build_packets(selection: Mapping[str, Any] | None = None) -> dict[str, Any]:
    selection = selection or freeze_selection()
    claims, results, people, _ = _load_inputs()
    claims_by_id = {text(row.get("claim_id")): row for row in claims}
    results_by_id = {text(row.get("claim_id")): row for row in results}
    stories = story_index()
    packets: list[dict[str, Any]] = []
    for selected in selection.get("records", []) or []:
        claim = claims_by_id.get(text(selected.get("claim_id")), {})
        audit = results_by_id.get(text(selected.get("claim_id")), {})
        story_id = text(claim.get("story_id"))
        surface = text(claim.get("surface"))
        evidence = _search_windows(claim, audit, stories)
        main = text((stories.get(story_id) or {}).get("main_text"))
        annotations = hda1._relevant_annotations(story_id, surface, stories)
        packets.append({
            "packet_id": f"hda2-packet-{text(claim.get('claim_id')).removeprefix('hda1-claim-')}",
            "claim_id": claim.get("claim_id"),
            "person_id": claim.get("person_id"),
            "claimed_person": claim.get("canonical_name"),
            "target_surface": surface,
            "occurrence_id": claim.get("occurrence_id"),
            "story_id": story_id,
            "claim_type": claim.get("claim_type"),
            "current_claim": {
                "surface": surface,
                "canonical_name": claim.get("canonical_name"),
                "exact_span": claim.get("exact_span"),
                "evidence_ref": claim.get("evidence_ref"),
                "claim_type": claim.get("claim_type"),
            },
            "hda1_flagged_for_reevaluation": True,
            "hda1_verdict_for_audit": audit.get("verdict"),
            "candidate_alternative_surfaces": [audit.get("suggested_identity_surface")] if text(audit.get("suggested_identity_surface")) else [],
            "evidence_items": evidence,
            "short_story_context": _compact(main, [surface, text(claim.get("canonical_name"))], 520),
            "relevant_liu_annotation": annotations,
            "known_local_participants": _local_participants(story_id, surface, people),
            "source_evidence_ids": [item.get("evidence_id") for item in evidence],
        })
    packets.sort(key=lambda row: text(row.get("packet_id")))
    return {"schema": "hda2-remediation-packets-v1", "packet_count": len(packets), "packets": packets, "candidate_only": True, "canonical_write_back": False}


def remediation_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_hda2_remediation_verdict",
            "description": "Independently verify a flagged historical identity claim using only supplied evidence.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": sorted(VERDICTS)},
                    "alternative_surface": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "reason_types": {"type": "array", "items": {"type": "string", "enum": sorted(REASON_TYPES)}},
                    "explanation": {"type": "string"},
                },
                "required": ["verdict", "alternative_surface", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "explanation"],
                "additionalProperties": False,
            },
        },
    }


def remediation_prompt(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Build a blind-enough remediation prompt; prior verdict is not sent."""
    return {
        "task": "independent historical identity remediation",
        "instruction": "A historical identity claim was flagged for re-evaluation. Using only the supplied source passages, determine whether the target surface refers to the claimed person. Do not rely on a surface string alone, comparison, co-occurrence, or a nearby unrelated person. Return the forced function call only.",
        "claim": {
            "claimed_person": packet.get("claimed_person"),
            "target_surface": packet.get("target_surface"),
            "occurrence_id": packet.get("occurrence_id"),
            "story_id": packet.get("story_id"),
            "claim_type": packet.get("claim_type"),
            "flagged_for_reevaluation": True,
        },
        "short_story_context": packet.get("short_story_context", ""),
        "relevant_liu_annotation": packet.get("relevant_liu_annotation", []),
        "known_local_participants": packet.get("known_local_participants", []),
        "candidate_alternative_surfaces": packet.get("candidate_alternative_surfaces", []),
        "evidence_items": packet.get("evidence_items", []),
    }


def validate_remediation_payload(payload: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "payload": None}
    expected = {"verdict", "alternative_surface", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "explanation"}
    if set(payload) != expected:
        errors.append("field_set_mismatch")
    verdict = payload.get("verdict")
    if verdict not in VERDICTS:
        errors.append("invalid_verdict")
    known_ids = {text(value) for value in packet.get("source_evidence_ids", []) or []}
    for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
        value = payload.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            errors.append(f"{field}_invalid")
        elif not set(value).issubset(known_ids):
            errors.append(f"{field}_unknown_evidence_id")
    reasons = payload.get("reason_types")
    if not isinstance(reasons, list) or any(item not in REASON_TYPES for item in reasons):
        errors.append("reason_types_invalid")
    alternative = payload.get("alternative_surface")
    if alternative is not None and (not isinstance(alternative, str) or not alternative.strip()):
        errors.append("alternative_surface_invalid")
    explanation = payload.get("explanation")
    if not isinstance(explanation, str) or len(explanation) > 1000:
        errors.append("explanation_invalid")
    if verdict in {"retain_existing", "reject_existing"} and not (payload.get("supporting_evidence_ids") or payload.get("contradicting_evidence_ids")):
        errors.append("decision_without_evidence")
    if verdict == "propose_alternative" and not alternative:
        errors.append("alternative_required")
    if verdict == "propose_alternative" and not payload.get("supporting_evidence_ids"):
        errors.append("alternative_without_support")
    return {"valid": not errors, "errors": errors, "payload": dict(payload) if not errors else None}


def _usage(response: Mapping[str, Any] | None) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) and isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return None
    return text(choices[0].get("finish_reason")) or None


def _safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {"exception_class": type(exc).__name__, "exception_message": message, "http_status": getattr(exc, "http_status", None)}


def call_remediation(packet: Mapping[str, Any], raw_dir: Path, sequence: int, retry: bool = True) -> tuple[dict[str, Any], Mapping[str, Any] | None, list[dict[str, Any]]]:
    prompt = remediation_prompt(packet)
    transport: list[dict[str, Any]] = []
    attempts = 2 if retry else 1
    for attempt in range(attempts):
        started = time.monotonic()
        record: dict[str, Any] = {"sequence": sequence, "attempt": attempt + 1, "claim_id": packet.get("claim_id"), "model": MODEL, "prompt_version": PROMPT_VERSION, "input_hash": stable_hash(prompt), "start_time": utc_now()}
        try:
            response = call_deepseek(
                [{"role": "system", "content": "You are an independent historical identity verifier. Use only supplied evidence and return the forced function call."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)}],
                model=MODEL,
                temperature=0,
                thinking={"type": "disabled"},
                max_tokens=850,
                timeout=180,
                endpoint="https://api.deepseek.com/beta/chat/completions",
                tools=[remediation_tool()],
                tool_choice={"type": "function", "function": {"name": "submit_hda2_remediation_verdict"}},
            )
            raw_path = raw_dir / f"{sequence:04d}-attempt-{attempt + 1}-{text(packet.get('claim_id'))}.json"
            if raw_path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{raw_path.name}")
            write_json(raw_path, response)
            record.update({"classification": "response_truncated" if _finish_reason(response) == "length" else "response", "finish_reason": _finish_reason(response), "usage": _usage(response), "raw_path": _relative(raw_path)})
            if record["classification"] == "response_truncated":
                transport.append(record)
                continue
            payload, channel, error = controller.extract_strict_tool_payload(response, expected_function_name="submit_hda2_remediation_verdict")
            if error:
                record.update({"classification": "response_parse_failure", "response_channel": channel, "parse_error": error})
                transport.append(record)
                continue
            record.update({"classification": "parsed", "response_channel": channel, "retry_of_sequence": sequence if attempt else None, "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
            transport.append(record)
            return record, payload, transport
        except Exception as exc:
            record.update({"classification": "provider_request_failure", **_safe_error(exc)})
            transport.append(record)
        finally:
            record.setdefault("elapsed_seconds", round(time.monotonic() - started, 3))
            record.setdefault("end_time", utc_now())
    return transport[-1], None, transport


def preflight(timeout: int = 20) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {"model": MODEL, "start_time": utc_now()}
    try:
        response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, max_tokens=8, thinking={"type": "disabled"}, timeout=timeout)
        row.update({"status": "reachable", "usage": _usage(response), "response_model": response.get("model")})
    except Exception as exc:
        row.update({"status": "live_network_unavailable", **_safe_error(exc)})
    row.update({"elapsed_seconds": round(time.monotonic() - started, 3), "end_time": utc_now()})
    return row


def _identity_forms(people: Mapping[str, Mapping[str, Any]]) -> dict[str, set[str]]:
    forms: dict[str, set[str]] = collections.defaultdict(set)
    for pid, person in people.items():
        canonical = text(person.get("canonical_name"))
        if canonical:
            forms[canonical].add(pid)
    aliases = read_json(ROOT / "data/aliases.json", {}) or {}
    for row in aliases.get("aliases", []) or []:
        if not isinstance(row, Mapping):
            continue
        status = text(row.get("status"))
        if status not in {"resolved", "context_dependent", "contextual"}:
            continue
        pids = {text(value) for value in row.get("resolved_person_ids", []) or [] if text(value) in people}
        if len(pids) != 1:
            continue
        surface = text(row.get("surface"))
        if surface:
            forms[surface].update(pids)
    for row in _hdb2_identity_rows():
        pid = text(row.get("resolved_person_id"))
        surface = text(row.get("surface"))
        if pid.startswith("person-") and surface and text(row.get("identity_status")) == "resolved_existing" and text(row.get("identity_resolution_basis")) in {"evidence_identity_assertion", "catalogue_exact_match"}:
            forms[surface].add(pid)
    return dict(forms)


def _ground_alternative(surface: str, packet: Mapping[str, Any], people: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    surface = text(surface)
    if not surface:
        return {"surface": None, "grounded": False, "matches": [], "reason": "no_alternative_surface"}
    forms = _identity_forms(people)
    candidate_ids = sorted(forms.get(surface, set()))
    evidence_items = [item for item in packet.get("evidence_items", []) or [] if isinstance(item, Mapping)]
    visible = [item for item in evidence_items if surface in text(item.get("evidence_text"))]
    matches = [{"person_id": pid, "canonical_name": people[pid].get("canonical_name"), "basis": "existing_person_registry_or_valid_identity_evidence", "evidence_ids": [item.get("evidence_id") for item in visible]} for pid in candidate_ids if pid in people]
    return {"surface": surface, "grounded": bool(matches) and bool(visible or len(candidate_ids) == 1), "matches": matches, "evidence_ids": [item.get("evidence_id") for item in visible], "reason": "unique existing form with supplied source visibility" if matches else "no uniquely grounded existing entity"}


def _optional_surface(value: Any) -> str:
    """Return a real optional surface, never the provider's literal null token.

    The strict tool schema permits JSON null, but a few provider responses have
    historically serialized that value as the string ``"null"``.  It is not a
    historical surface and must therefore stay absent from candidate-grounding
    and overlay projections.
    """
    if value is None:
        return ""
    value_text = text(value).strip()
    return "" if value_text.casefold() == "null" else value_text


def build_grounded_alternatives(results: Sequence[Mapping[str, Any]], packets: Sequence[Mapping[str, Any]], people: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    packets_by_claim = {text(row.get("claim_id")): row for row in packets}
    output: list[dict[str, Any]] = []
    for result in results:
        payload = result.get("payload") if isinstance(result.get("payload"), Mapping) else {}
        alternative = _optional_surface(payload.get("alternative_surface"))
        if not alternative:
            continue
        grounded = _ground_alternative(alternative, packets_by_claim.get(text(result.get("claim_id")), {}), people)
        output.append({"claim_id": result.get("claim_id"), "alternative_surface": alternative, **grounded, "candidate_only": True, "canonical_write_back": False})
    return sorted(output, key=lambda row: text(row.get("claim_id")))


def build_overlay(results: Sequence[Mapping[str, Any]], grounded: Sequence[Mapping[str, Any]], packets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grounded_by_claim = {text(row.get("claim_id")): row for row in grounded}
    packet_by_claim = {text(row.get("claim_id")): row for row in packets}
    overlay: list[dict[str, Any]] = []
    for result in results:
        payload = result.get("payload") if isinstance(result.get("payload"), Mapping) else {}
        verdict = text(payload.get("verdict"))
        execution = text(result.get("execution_status"))
        action = "require_human_review"
        reason = "provider_or_schema_result_not independently usable"
        grounded_alt = grounded_by_claim.get(text(result.get("claim_id")), {})
        if execution == "validated" and verdict == "retain_existing" and payload.get("supporting_evidence_ids"):
            action, reason = "retain_claim", "independent remediation supports the existing claim"
        elif execution == "validated" and verdict == "propose_alternative" and grounded_alt.get("grounded") and len(grounded_alt.get("matches", []) or []) == 1:
            action, reason = "replace_with_existing_person_candidate", "alternative surface is independently grounded to one existing Person"
        elif execution == "validated" and verdict == "reject_existing" and payload.get("contradicting_evidence_ids"):
            action, reason = "suppress_claim", "independent remediation found source-grounded contradiction; canonical data remains untouched"
        elif execution == "validated" and verdict == "remain_ambiguous":
            action, reason = "preserve_ambiguous", "independent remediation does not justify a replacement"
        overlay.append({
            "claim_id": result.get("claim_id"),
            "person_id": packet_by_claim.get(text(result.get("claim_id")), {}).get("person_id"),
            "target_surface": packet_by_claim.get(text(result.get("claim_id")), {}).get("target_surface"),
            "story_id": packet_by_claim.get(text(result.get("claim_id")), {}).get("story_id"),
            "action": action,
            "reason": reason,
            "remediation_verdict": payload.get("verdict"),
            "alternative_surface": _optional_surface(payload.get("alternative_surface")) or None,
            "grounded_alternative": grounded_alt,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return sorted(overlay, key=lambda row: text(row.get("claim_id")))


def build_review_queue(results: Sequence[Mapping[str, Any]], overlay: Sequence[Mapping[str, Any]], packets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    overlay_by_claim = {text(row.get("claim_id")): row for row in overlay}
    packet_by_claim = {text(row.get("claim_id")): row for row in packets}
    queue: list[dict[str, Any]] = []
    for result in results:
        row = overlay_by_claim.get(text(result.get("claim_id")), {})
        if text(row.get("action")) == "retain_claim":
            continue
        verdict = text((result.get("payload") or {}).get("verdict")) if isinstance(result.get("payload"), Mapping) else ""
        priority = "P0" if verdict == "reject_existing" or verdict == "contradict" else ("P1" if verdict == "propose_alternative" else "P2")
        packet = packet_by_claim.get(text(result.get("claim_id")), {})
        queue.append({
            "review_id": f"hda2-review-{text(result.get('claim_id')).removeprefix('hda1-claim-')}",
            "priority": priority,
            "claim_id": result.get("claim_id"),
            "person_id": packet.get("person_id"),
            "canonical_name": packet.get("claimed_person"),
            "surface": packet.get("target_surface"),
            "story_id": packet.get("story_id"),
            "action": row.get("action"),
            "reason": row.get("reason"),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return sorted(queue, key=lambda row: (text(row.get("priority")), text(row.get("review_id"))))


def summarize(results: Sequence[Mapping[str, Any]], overlay: Sequence[Mapping[str, Any]], grounded: Sequence[Mapping[str, Any]], selection: Mapping[str, Any]) -> dict[str, Any]:
    valid = [row for row in results if text(row.get("execution_status")) == "validated"]
    verdicts = collections.Counter(text(row.get("payload", {}).get("verdict")) for row in valid if isinstance(row.get("payload"), Mapping))
    actions = collections.Counter(text(row.get("action")) for row in overlay)
    grounded_success = sum(bool(row.get("grounded")) for row in grounded)
    return {
        "schema": "hda2-remediation-metrics-v1",
        "hda1_flagged_claims_available": int(selection.get("available_flagged_claim_count") or 0),
        "hda1_flagged_claims_processed": len(results),
        "retained": actions["retain_claim"],
        "suppressed": actions["suppress_claim"],
        "alternative_proposed": verdicts["propose_alternative"],
        "alternative_grounded": grounded_success,
        "ambiguous": verdicts["remain_ambiguous"],
        "insufficient": verdicts["insufficient_evidence"] + sum(1 for row in results if text(row.get("execution_status")) != "validated"),
        "high_risk_claims_repaired": actions["suppress_claim"] + actions["replace_with_existing_person_candidate"],
        "existing_person_mappings_recovered": sum(len(row.get("matches", []) or []) == 1 and row.get("grounded") for row in grounded),
        "local_candidates_created": 0,
        "invalid_provider_payloads": sum(text(row.get("execution_status")) == "invalid_provider_payload" for row in results),
        "provider_failures": sum(text(row.get("classification")) == "provider_request_failure" for row in results),
        "candidate_only": True,
        "canonical_write_back": False,
        "verdicts_validated": dict(verdicts),
        "overlay_actions": dict(actions),
    }


def protected_hashes() -> dict[str, str]:
    paths = [
        "data/people.json",
        "data/relations.json",
        "data/personStory.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/kinship-h0b1.json",
        "data/annotation/marriages-h0b1.json",
        "data/annotation/office-tenures-h0b1.json",
        "data/derived/hdb2-f-person-knowledge.json",
        "data/derived/hdb2-f-identity-summary.json",
        "data/derived/hdb2-f-identity-claim-integrity-audit.json",
    ]
    current = {path: file_hash(ROOT / path) for path in paths if (ROOT / path).is_file()}
    # Preserve the completed HDA2 protection snapshot across the explicitly
    # authorized SFH2R derived-profile transition.  Canonical files remain
    # hashed from the current checkout; only the historical derived profile
    # value is allowed to use the recorded pre-repair hash.
    manifest = read_json(OUT / "manifest.json", {}) or {}
    frozen = manifest.get("protected_hashes_before") if isinstance(manifest, Mapping) else None
    if isinstance(frozen, Mapping) and sfh2r_contract.frozen_hashes_are_current_or_authorized(frozen, current):
        return {str(key): str(value) for key, value in frozen.items()}
    return current


def prepare() -> dict[str, Any]:
    selection = freeze_selection()
    packets = build_packets(selection)
    document = {"schema": SCHEMA, "run_version": RUN_VERSION, "prompt_version": PROMPT_VERSION, "model": MODEL, "selection_hash": selection.get("selection_hash"), "selection": selection, "packets": packets, "protected_hashes_before": protected_hashes(), "candidate_only": True, "canonical_write_back": False}
    write_json(OUT / "remediation-packets.json", packets)
    write_json(OUT / "manifest.json", {"schema": "hda2-remediation-manifest-v1", "run_version": RUN_VERSION, "prompt_version": PROMPT_VERSION, "selection_hash": selection.get("selection_hash"), "packet_count": packets.get("packet_count"), "hda1_input_hashes": selection.get("hda1_input_hashes"), "protected_hashes_before": document["protected_hashes_before"], "frozen_before_live": True, "candidate_only": True, "canonical_write_back": False})
    return document


def run(*, live: bool, run_id: str | None = None, retry_provider: bool = True) -> dict[str, Any]:
    prepared = prepare()
    selection = prepared["selection"]
    packets = list(prepared["packets"].get("packets", []) or [])
    run_name = run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") if live else "offline")
    base = OUT / "live" / run_name
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    preflight_row = preflight() if live else {"status": "offline_not_requested", "model": MODEL}
    results: list[dict[str, Any]] = []
    transport: list[dict[str, Any]] = []
    for sequence, packet in enumerate(packets, 1):
        if live and preflight_row.get("status") == "reachable":
            record, payload, attempts = call_remediation(packet, raw_dir, sequence, retry=retry_provider)
            transport.extend(attempts)
            if payload is None:
                results.append({"claim_id": packet.get("claim_id"), "execution_status": "invalid_provider_payload", "classification": record.get("classification"), "validation_errors": [record.get("parse_error") or record.get("classification")], "payload": None, "transport_sequence": sequence})
                continue
            validated = validate_remediation_payload(payload, packet)
            results.append({"claim_id": packet.get("claim_id"), "execution_status": "validated" if validated["valid"] else "invalid_provider_payload", "classification": "validated" if validated["valid"] else "invalid_schema", "validation_errors": validated["errors"], "payload": validated["payload"], "transport_sequence": sequence})
        else:
            results.append({"claim_id": packet.get("claim_id"), "execution_status": "not_executed", "classification": "live_network_unavailable" if live else "offline_fixture_not_used", "validation_errors": ["live_provider_unavailable"] if live else ["offline_run"], "payload": {"verdict": "insufficient_evidence", "alternative_surface": None, "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": ["insufficient_context"], "explanation": "No live remediation result was produced."}, "transport_sequence": sequence})
    people = _load_inputs()[2]
    grounded = build_grounded_alternatives(results, packets, people)
    overlay = build_overlay(results, grounded, packets)
    queue = build_review_queue(results, overlay, packets)
    metrics = summarize(results, overlay, grounded, selection)
    metrics.update({
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "run_id": run_name,
        "semantic_calls": len(transport),
        "retry_calls": sum(1 for row in transport if row.get("attempt", 1) > 1),
        "provider_failures": sum(text(row.get("classification")) == "provider_request_failure" for row in transport),
        "parse_failures": sum(text(row.get("classification")) == "response_parse_failure" for row in transport),
        "truncated_responses": sum(text(row.get("classification")) == "response_truncated" for row in transport),
        "prompt_tokens": sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in transport if isinstance(row.get("usage"), Mapping)),
        "completion_tokens": sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in transport if isinstance(row.get("usage"), Mapping)),
        "total_tokens": sum(int((row.get("usage") or {}).get("total_tokens") or 0) for row in transport if isinstance(row.get("usage"), Mapping)),
        "latency_median": statistics.median([float(row.get("elapsed_seconds") or 0) for row in transport]) if transport else 0,
        "latency_max": max([float(row.get("elapsed_seconds") or 0) for row in transport], default=0),
        "provider_preflight": preflight_row,
    })
    write_json(base / "manifest.json", {"schema": "hda2-remediation-live-manifest-v1", "run_id": run_name, "run_version": RUN_VERSION, "prompt_version": PROMPT_VERSION, "selection_hash": selection.get("selection_hash"), "preflight": preflight_row, "live_requested": live, "semantic_call_count_expected": len(packets), "protected_hashes_before": prepared.get("protected_hashes_before"), "candidate_only": True, "canonical_write_back": False})
    write_json(base / "remediation-results.json", {"schema": "hda2-remediation-results-v1", "results": results, "candidate_only": True, "canonical_write_back": False})
    write_json(base / "grounded-alternatives.json", grounded)
    write_json(base / "repair-overlay.json", overlay)
    write_json(base / "human-review-queue.json", {"items": queue, "candidate_only": True, "canonical_write_back": False})
    write_json(base / "metrics.json", metrics)
    write_json(base / "transport.json", transport)
    write_json(OUT / "remediation-results.json", {"schema": "hda2-remediation-results-pointer-v1", "run_id": run_name, "results_path": _relative(base / "remediation-results.json"), "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "grounded-alternatives.json", grounded)
    write_json(OUT / "repair-overlay.json", overlay)
    write_json(OUT / "human-review-queue.json", {"schema": "hda2-human-review-queue-v1", "run_id": run_name, "items": queue, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "metrics.json", metrics)
    return {"base": base, "selection": selection, "packets": packets, "results": results, "grounded": grounded, "overlay": overlay, "queue": queue, "metrics": metrics, "transport": transport}


def rebuild_from_run(run_id: str) -> dict[str, Any]:
    """Rebuild HDA2 projections from an immutable run without contacting DeepSeek.

    This is intentionally a projection-only operation.  Raw responses,
    transport records, selection, and packets remain untouched; the helper is
    useful when a presentation/normalization bug is fixed after a live run.
    """
    base = OUT / "live" / run_id
    if not base.is_dir():
        raise FileNotFoundError(base)
    prepared = prepare()
    selection = prepared["selection"]
    packets = list(prepared["packets"].get("packets", []) or [])
    result_doc = read_json(base / "remediation-results.json", {}) or {}
    results = list(result_doc.get("results", []) or [])
    people = _load_inputs()[2]
    grounded = build_grounded_alternatives(results, packets, people)
    overlay = build_overlay(results, grounded, packets)
    queue = build_review_queue(results, overlay, packets)
    metrics = summarize(results, overlay, grounded, selection)
    old_metrics = read_json(base / "metrics.json", {}) or {}
    for key in (
        "model", "prompt_version", "run_id", "semantic_calls", "retry_calls",
        "provider_failures", "parse_failures", "truncated_responses",
        "prompt_tokens", "completion_tokens", "total_tokens", "latency_median",
        "latency_max", "provider_preflight",
    ):
        if key in old_metrics:
            metrics[key] = old_metrics[key]
    write_json(base / "grounded-alternatives.json", grounded)
    write_json(base / "repair-overlay.json", overlay)
    write_json(base / "human-review-queue.json", {"items": queue, "candidate_only": True, "canonical_write_back": False})
    write_json(base / "metrics.json", metrics)
    write_json(OUT / "grounded-alternatives.json", grounded)
    write_json(OUT / "repair-overlay.json", overlay)
    write_json(OUT / "human-review-queue.json", {"schema": "hda2-human-review-queue-v1", "run_id": run_id, "items": queue, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "metrics.json", metrics)
    return {"base": base, "selection": selection, "packets": packets, "results": results, "grounded": grounded, "overlay": overlay, "queue": queue, "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--no-retry", action="store_true")
    args = parser.parse_args()
    if args.prepare or not args.live and not args.offline:
        prepared = prepare()
        print(json.dumps({"selection_hash": prepared["selection"].get("selection_hash"), "selected_claims": prepared["selection"].get("selected_claim_count"), "packets": prepared["packets"].get("packet_count"), "candidate_only": True, "canonical_write_back": False}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    result = run(live=args.live, run_id=args.run_id, retry_provider=not args.no_retry)
    print(json.dumps({"run_id": result["base"].name, "selected_claims": len(result["packets"]), "semantic_calls": result["metrics"].get("semantic_calls"), "metrics": result["metrics"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
