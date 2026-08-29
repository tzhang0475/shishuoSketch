"""L2 fail-closed exact-source mention validation."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .common import stable_hash, text
from .schemas import CONFIDENCES, ENTITY_KINDS, REFERENCE_FORMS
from .source_packets import evidence_index


def _resolve_offsets(source: str, surface: str, start: Any, end: Any) -> tuple[int | None, int | None, str | None]:
    if isinstance(start, int) or isinstance(end, int):
        if not isinstance(start, int) or not isinstance(end, int):
            return None, None, "partial_offsets"
        if start < 0 or end <= start or end > len(source):
            return None, None, "offset_range_invalid"
        if source[start:end] != surface:
            return None, None, "offset_surface_mismatch"
        return start, end, None
    position = source.find(surface)
    if position < 0:
        return None, None, "surface_not_in_source"
    return position, position + len(surface), None


def validate_mentions(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = evidence_index(packet)
    rows = payload.get("mentions") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {
            "story_id": packet.get("story_id"), "valid_mentions": [],
            "rejected_mentions": [{"reason": "provider_or_schema_failure"}],
            "overlaps": [], "provider_failure": True,
        }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int, str]] = set()
    local_ids: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "reason": "mention_not_object"})
            continue
        local_id = text(raw.get("mention_id_local"))
        surface = text(raw.get("surface"))
        evidence_id = text(raw.get("source_evidence_id"))
        kind = text(raw.get("entity_kind"))
        form = text(raw.get("reference_form"))
        confidence = text(raw.get("confidence"))
        reasons: list[str] = []
        if not local_id or local_id in local_ids:
            reasons.append("invalid_or_duplicate_local_id")
        if not surface:
            reasons.append("empty_surface")
        if evidence_id not in evidence:
            reasons.append("unknown_evidence_id")
        if kind not in ENTITY_KINDS:
            reasons.append("invalid_entity_kind")
        if form not in REFERENCE_FORMS:
            reasons.append("invalid_reference_form")
        if confidence not in CONFIDENCES:
            reasons.append("invalid_confidence")
        start = end = None
        if evidence_id in evidence and surface:
            start, end, offset_error = _resolve_offsets(
                text(evidence[evidence_id].get("text")),
                surface,
                raw.get("source_start"),
                raw.get("source_end"),
            )
            if offset_error:
                reasons.append(offset_error)
        if reasons:
            rejected.append({"index": index, "mention": dict(raw), "reasons": sorted(set(reasons))})
            continue
        assert start is not None and end is not None
        key = (evidence_id, surface, start, end, kind)
        local_ids.add(local_id)
        if key in seen:
            continue
        seen.add(key)
        mention_id = f"sfh1-mention-{stable_hash({'story_id': packet.get('story_id'), 'evidence_id': evidence_id, 'surface': surface, 'start': start, 'end': end, 'kind': kind})[:24]}"
        accepted.append({
            "mention_id": mention_id,
            "mention_id_local": local_id,
            "story_id": packet.get("story_id"),
            "surface": surface,
            "source_evidence_id": evidence_id,
            "source_start": start,
            "source_end": end,
            "entity_kind": kind,
            "reference_form": form,
            "confidence": confidence,
            "local_explanation": text(raw.get("local_explanation")),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    accepted.sort(key=lambda row: (row["source_evidence_id"], row["source_start"], -len(row["surface"]), row["mention_id"]))
    overlaps: list[dict[str, Any]] = []
    for left_index, left in enumerate(accepted):
        for right in accepted[left_index + 1:]:
            if left["source_evidence_id"] != right["source_evidence_id"]:
                continue
            if max(left["source_start"], right["source_start"]) < min(left["source_end"], right["source_end"]):
                overlaps.append({"left": left["mention_id"], "right": right["mention_id"]})
    return {
        "story_id": packet.get("story_id"),
        "valid_mentions": accepted,
        "rejected_mentions": rejected,
        "overlaps": overlaps,
        "provider_failure": False,
        "counts_by_entity_kind": dict(Counter(row["entity_kind"] for row in accepted)),
    }
