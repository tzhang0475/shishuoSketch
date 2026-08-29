"""LLM semantic temporal reading with deterministic source/chronology guards."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .common import StrictStageClient, stable_hash, text
from .schemas import CONFIDENCES, temporal_tool
from .source_packets import evidence_index

ROLES = {"scene_time", "background_context", "later_outcome", "quoted_precedent", "relative_person_time", "office_context", "uncertain"}
EXPLICIT_DATE_RE = re.compile(r"(?:元|[一二三四五六七八九十百千〇零兩]+)年(?:[一二三四五六七八九十]+月)?(?:[一二三四五六七八九十]+日)?")

SYSTEM = """Read temporal meaning in the supplied classical Chinese Story and annotations. Extract at most 12 of the most meaningful temporal assertions, including contextual phases, event-relative chronology, reign/ruler context, later outcomes, quotations and background. Copy exact source spans and cite supplied evidence IDs. Do not force every Story to have temporal evidence and do not assign canonical dates. Later outcomes, quoted precedents and background must remain distinct from scene time. Return only the forced structured function."""


def deterministic_visible_hints(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Literal recall hints only; no semantic role is assigned."""
    hints: list[dict[str, Any]] = []
    for evidence in packet.get("evidence", []) or []:
        value = text(evidence.get("text"))
        for match in EXPLICIT_DATE_RE.finditer(value):
            hints.append({
                "surface": match.group(0),
                "evidence_id": evidence.get("evidence_id"),
                "source_start": match.start(),
                "source_end": match.end(),
                "scope": "explicit_date_pattern",
            })
    return hints


def read_temporal(client: StrictStageClient, packet: Mapping[str, Any]) -> Mapping[str, Any] | None:
    tool = temporal_tool()
    payload = {
        "task": "semantic temporal reading",
        "story_id": packet.get("story_id"),
        "source_evidence": [
            {"evidence_id": row.get("evidence_id"), "source_layer": row.get("source_layer"), "text": row.get("text")}
            for row in packet.get("evidence", []) or []
        ],
        "mechanical_visible_hints": deterministic_visible_hints(packet),
        "hint_warning": "Literal recall hints are not historical conclusions and need not be emitted.",
    }
    return client.call(
        stage="temporal_semantics",
        unit_id=str(packet.get("story_id")),
        system=SYSTEM,
        payload=payload,
        function=tool,
        function_name=tool["function"]["name"],
        max_tokens=2600,
    )


def validate_temporal(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = evidence_index(packet)
    rows = payload.get("assertions") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"story_id": packet.get("story_id"), "assertions": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "reason": "assertion_not_object"})
            continue
        evidence_id = text(raw.get("evidence_id"))
        exact_span = text(raw.get("exact_span"))
        surface = text(raw.get("surface"))
        role = text(raw.get("semantic_role"))
        confidence = text(raw.get("confidence"))
        errors: list[str] = []
        if evidence_id not in evidence:
            errors.append("unknown_evidence_id")
        else:
            source = text(evidence[evidence_id].get("text"))
            if not exact_span or exact_span not in source:
                errors.append("exact_span_not_in_source")
            if surface and surface not in exact_span:
                errors.append("surface_not_in_exact_span")
        if role not in ROLES:
            errors.append("invalid_role")
        if confidence not in CONFIDENCES:
            errors.append("invalid_confidence")
        key = (evidence_id, exact_span, surface, role)
        if key in seen:
            continue
        if errors:
            rejected.append({"index": index, "assertion": dict(raw), "errors": sorted(set(errors))})
            continue
        seen.add(key)
        accepted.append({
            "temporal_id": f"sfh1-temporal-{stable_hash({'story_id': packet.get('story_id'), 'key': key})[:22]}",
            "story_id": packet.get("story_id"),
            "surface": surface,
            "evidence_id": evidence_id,
            "exact_span": exact_span,
            "semantic_role": role,
            "interpretation": text(raw.get("interpretation")),
            "confidence": confidence,
            "scene_projection_eligible": role == "scene_time",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {"story_id": packet.get("story_id"), "assertions": accepted, "rejected": rejected, "provider_failure": False}
